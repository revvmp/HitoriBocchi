import json
import os
import time
from functools import lru_cache, wraps
from math import isfinite

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, get_jwt_identity, jwt_required, set_access_cookies, set_refresh_cookies, unset_jwt_cookies, verify_jwt_in_request
from itsdangerous import SignatureExpired
from requests import RequestException
from waitress import serve

from database import schema
from database.database import AnimeDatabase
from instance.config import Config
from scrapers.manga.mangakatana import MangaKatanaError, MangaKatanaScraper
from scrapers.metadata.aniskip import AniSkipError, fetch_aniskip_skip_times
from scrapers.metadata.mal import scrape_anime_meta_data, scrape_manga_meta_data
from scrapers.providers import additional, common
from scrapers.providers.anidb import run_anidb_episode_availability, run_anidb_episode_stream
from scrapers.providers.anizone import run_anizone_episode_availability, run_anizone_episode_stream
from scrapers.providers.miruro import run_episode_stream, run_episode_stream_availability
from services import anime_importer, manga_importer
from services.chapter_sync import normalize_chapter_number, run_chapter_sync_for_manga
from services.episode_sync import run_episode_sync_for_anime
from streaming import additional_proxy, anidb_proxy, anizone_proxy, manga_image_proxy, miruro_proxy
from utils.logger import get_logger
from utils.password_hasher import verify_password


PORT = int(os.environ.get("PORT", 5000))
WAITRESS_THREADS = int(os.environ.get("WAITRESS_THREADS", 16))

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_EPISODE_SECONDS = 86400
MAX_COMMENT_LENGTH = 2000
CATALOG_SORTS = {"title", "latest", "popularity", "rating"}
MANGA_CHAPTER_PAGE_CACHE_TTL = 10 * 60
MANGA_CHAPTER_PAGE_RESPONSE_MAX_AGE = 5 * 60
COMPLETION_THRESHOLD = 0.9

DEFAULT_PLAYBACK_PROVIDER = "anizone"
PLAYBACK_CATEGORIES = {"sub", "dub"}
LABELLED_QUALITIES = {"1080", "720", "360"}
ANILIST_REQUIRED_PROVIDERS = {"reanime", "anibd"}

FORWARDED_MEDIA_HEADERS = ("Accept-Ranges", "Content-Length", "Content-Range", "ETag", "Last-Modified")
MEDIA_CACHE_CONTROL = "private, max-age=600"
HLS_CONTENT_TYPE = "application/vnd.apple.mpegurl"

MAX_USERNAME_LENGTH = 50
MAX_EMAIL_LENGTH = 254
MAX_PASSWORD_BYTES = 72

logger = get_logger(__name__)

app = Flask(__name__, instance_relative_config=True)
app.config.from_object(Config)
jwt = JWTManager(app)


class ApiError(Exception):
    """
    An expected request failure that becomes a JSON error response.
    """
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def to_response(self):
        return jsonify(message=self.message), self.status_code


app.register_error_handler(ApiError, ApiError.to_response)


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _set_access_token_cookie(response, access_token: str):
    max_age = int(app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds())
    set_access_cookies(response, access_token, max_age=max_age)
    response.headers["Cache-Control"] = "no-store"


def _set_refresh_token_cookie(response, refresh_token: str):
    max_age = int(app.config["JWT_REFRESH_TOKEN_EXPIRES"].total_seconds())
    set_refresh_cookies(response, refresh_token, max_age=max_age)
    response.headers["Cache-Control"] = "no-store"


def _clear_auth_cookies(response):
    unset_jwt_cookies(response)
    response.headers["Cache-Control"] = "no-store"


def _jwt_error_response(message: str):
    response = jsonify(message=message)

    if request.endpoint == "refresh":
        _clear_auth_cookies(response)

    response.headers["Cache-Control"] = "no-store"
    return response, 401


@jwt.expired_token_loader
def handle_expired_token(_jwt_header, _jwt_payload):
    return _jwt_error_response("Session has expired. Please sign in again.")


@jwt.invalid_token_loader
def handle_invalid_token(_error_message):
    return _jwt_error_response("Session is invalid. Please sign in again.")


@jwt.unauthorized_loader
def handle_missing_token(_error_message):
    return _jwt_error_response("Authentication required")


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        with AnimeDatabase() as db:
            user = db.fetch_user_by_id(_current_user_id())

        if user is None:
            return jsonify(message="User not found"), 401

        if user.is_admin != 1:
            return jsonify(message="Admin access required"), 403

        return fn(*args, **kwargs)

    return wrapper


def site_access_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with AnimeDatabase() as db:
            login_required = db.get_login_required()

        if login_required:
            verify_jwt_in_request()

        return fn(*args, **kwargs)

    return wrapper


def _query_text(name: str, default: str = "") -> str:
    return request.args.get(name, default).strip()


def _pagination() -> tuple[int, int]:
    try:
        limit = int(request.args.get("limit", DEFAULT_PAGE_SIZE))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        raise ApiError("limit and offset must be integers")

    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise ApiError(f"limit must be between 1 and {MAX_PAGE_SIZE}")

    if offset < 0:
        raise ApiError("offset must be 0 or greater")

    return limit, offset


def _json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _json_or_form():
    data = _json_body()
    return data if data is not None else request.form


def _json_field(name: str):
    data = _json_body()
    return data.get(name) if data is not None else None


def _is_number(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and isfinite(value)


def _require_episode_number(episode_number: int):
    if episode_number < 1:
        raise ApiError("Episode number must be 1 or greater")


def _require_positive_id(value: int, label: str):
    if value < 1:
        raise ApiError(f"{label} must be 1 or greater")


def _mal_id_from_json() -> int:
    mal_id = _json_field("mal_id")

    if not isinstance(mal_id, int) or isinstance(mal_id, bool) or mal_id < 1:
        raise ApiError("mal_id must be a positive integer")

    return mal_id


def _search_import_limit(default: int | None) -> int | None:
    raw_limit = request.args.get("limit")

    if raw_limit is None:
        return default

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        raise ApiError("limit must be an integer")

    if not 1 <= limit <= 20:
        raise ApiError("limit must be between 1 and 20")

    return limit


def _playback_position() -> tuple[float, float]:
    """
    Returns the reported playback time, capped at the duration, and the duration in seconds.
    """
    data = _json_body()

    if data is None:
        raise ApiError("A JSON request body is required")

    current_time_seconds = data.get("current_time_seconds")
    duration_seconds = data.get("duration_seconds")

    for field_name, field_value in (("current_time_seconds", current_time_seconds), ("duration_seconds", duration_seconds)):
        if not _is_number(field_value):
            raise ApiError(f"{field_name} must be a number")

    if current_time_seconds < 0:
        raise ApiError("current_time_seconds must be 0 or greater")

    if not 0 < duration_seconds <= MAX_EPISODE_SECONDS:
        raise ApiError(f"duration_seconds must be between 1 and {MAX_EPISODE_SECONDS}")

    return min(current_time_seconds, duration_seconds), duration_seconds


def _comment_text(data) -> str:
    text = data.get("comment_text")

    if not isinstance(text, str) or not text.strip():
        raise ApiError("comment_text is required")

    text = text.strip()

    if len(text) > MAX_COMMENT_LENGTH:
        raise ApiError(f"comment_text must be {MAX_COMMENT_LENGTH} characters or fewer")

    return text


def _no_store(response, status_code: int = 200):
    response.headers["Cache-Control"] = "no-store"
    return response, status_code


def _paginated(key: str, records: list, limit: int, offset: int):
    """
    Serializes one page of records fetched with limit + 1 rows to detect another page.
    """
    page = records[:limit]

    return jsonify({
        key: [record.to_dict() for record in page],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": len(page),
            "has_more": len(records) > limit,
        },
    }), 200


def _ndjson_stream(events, record_key: str):
    def generate_events():
        for event in events:
            serialized_event = event.copy()
            record = serialized_event.get(record_key)

            if record is not None and not isinstance(record, dict):
                serialized_event[record_key] = record.to_dict()

            yield json.dumps(serialized_event) + "\n"

    response = Response(stream_with_context(generate_events()), mimetype="application/x-ndjson")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


def _find_anime(db, slug: str):
    anime = db.fetch_anime_by_slug(slug)

    if anime is None:
        raise ApiError("Anime not found", 404)

    return anime


def _find_episode(db, anime, episode_number: int):
    episode = db.fetch_episode_by_anime_and_number(anime.id, episode_number)

    if episode is None:
        raise ApiError("Episode not found", 404)

    return episode


def _find_manga(db, slug: str):
    manga = db.fetch_manga_by_slug(slug)

    if manga is None:
        raise ApiError("Manga not found", 404)

    return manga


def _find_chapter(db, manga, chapter_number: str):
    chapter = db.fetch_chapter_by_manga_and_number(manga.id, chapter_number)

    if chapter is None:
        raise ApiError("Chapter not found", 404)

    return chapter


def _find_signed_in_user(db, user_id: int):
    user = db.fetch_user_by_id(user_id)

    if user is None:
        raise ApiError("User not found", 401)

    return user


def _sentence(name: str) -> str:
    return name[:1].upper() + name[1:]


def _reject_failed_upstream(upstream, name: str):
    """
    Rejects upstream redirects and error responses. `name` describes the resource, e.g. "AniDB stream".
    """
    if 300 <= upstream.status_code < 400:
        upstream.close()
        raise ApiError(f"{_sentence(name)} host redirect was rejected", 502)

    if upstream.status_code >= 400:
        status_code = upstream.status_code
        upstream.close()
        logger.warning("%s host returned HTTP %s", _sentence(name), status_code)
        raise ApiError(f"Unable to fetch {name} resource", 502)


def _read_limited(upstream, chunk_size: int, max_size: int, too_large_message: str) -> bytes:
    chunks = []
    size = 0

    try:
        for chunk in upstream.iter_content(chunk_size=chunk_size):
            size += len(chunk)

            if size > max_size:
                raise ApiError(too_large_message, 502)

            chunks.append(chunk)
    finally:
        upstream.close()

    return b"".join(chunks)


def _read_playlist(upstream, name: str, chunk_size: int, max_size: int) -> str:
    try:
        return _read_limited(upstream, chunk_size, max_size, f"{_sentence(name)} playlist is too large").decode("utf-8")
    except UnicodeDecodeError:
        raise ApiError(f"{_sentence(name)} playlist is invalid", 502)
    except ApiError as e:
        logger.warning("Unable to read %s playlist: %s", name, e.message)
        raise
    except Exception as e:
        logger.warning("Unable to read %s playlist: %s", name, e)
        raise ApiError(f"Unable to read {name} playlist", 502)


def _rewrite_playlist(rewrite, name: str, error_class, **options) -> str:
    try:
        return rewrite(secret_key=app.config["SECRET_KEY"], **options)
    except error_class as e:
        logger.warning("Unable to rewrite %s playlist: %s", name, e)
        raise ApiError(f"{_sentence(name)} playlist contains an invalid URL", 502)


def _playlist_response(playlist: str, status_code: int) -> Response:
    response = Response(playlist, status=status_code, content_type=HLS_CONTENT_TYPE)
    response.headers["Cache-Control"] = "no-store"
    return response


def _media_response(upstream, content_type: str, chunk_size: int) -> Response:
    def generate_media():
        try:
            for chunk in upstream.iter_content(chunk_size=chunk_size):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    response = Response(stream_with_context(generate_media()), status=upstream.status_code, content_type=content_type)

    for header_name in FORWARDED_MEDIA_HEADERS:
        header_value = upstream.headers.get(header_name)

        if header_value:
            response.headers[header_name] = header_value

    response.headers["Cache-Control"] = MEDIA_CACHE_CONTROL
    return response


def _is_playlist(resource_name: str, content_type: str) -> bool:
    return resource_name.lower().endswith(".m3u8") or "mpegurl" in content_type.lower()


@app.post("/register")
def register():
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")
    registration_key = request.form.get("registration_key")

    if not username or not password or not email or not registration_key:
        raise ApiError("All fields are required")

    if registration_key != app.config["REGISTRATION_KEY"]:
        raise ApiError("Invalid registration key", 403)

    with AnimeDatabase() as db:
        if db.fetch_user(username):
            raise ApiError("Username already exists", 409)

        db.create_user(username, email, password)

    return jsonify(status=201, message="User registered successfully"), 201


@app.post("/login")
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    logger.info("User %s is logging in", username)

    with AnimeDatabase() as db:
        user = db.fetch_user(username)

        if not user:
            logger.info("User %s does not exist", username)
            raise ApiError("User does not exist", 401)

        hashed_password = db.get_password_hash(username)

    if not verify_password(password, hashed_password):
        logger.info("User %s failed to login.", username)
        raise ApiError("Invalid Username or Password", 401)

    logger.info("User %s successfully logged in.", username)
    response = jsonify(status=200, message="Success")
    _set_access_token_cookie(response, create_access_token(identity=str(user.id)))
    _set_refresh_token_cookie(response, create_refresh_token(identity=str(user.id)))
    return response, 200


@app.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    response = jsonify(status=200, message="Access token refreshed")
    _set_access_token_cookie(response, create_access_token(identity=get_jwt_identity()))
    return response, 200


@app.post("/logout")
@jwt_required()
def logout():
    response = jsonify(status=200, message="Logged out successfully")
    _clear_auth_cookies(response)
    return response, 200


@app.post("/session/clear")
def clear_session():
    if request.headers.get("X-Session-Reset") != "1":
        raise ApiError("Session reset header is required")

    response = jsonify(status=200, message="Session cleared")
    _clear_auth_cookies(response)
    return response, 200


@app.get("/user")
@jwt_required()
def get_user():
    with AnimeDatabase() as db:
        user = db.fetch_user_by_id(_current_user_id())

    if user is None:
        raise ApiError("User not found", 404)

    return jsonify(user=user.to_dict()), 200


@app.get("/site-settings")
def get_site_settings():
    with AnimeDatabase() as db:
        login_required = db.get_login_required()

    return _no_store(jsonify(login_required=login_required))


def _fetch_anime_catalog_page(db, limit: int, offset: int, search_query: str, genre: str, status: str, sort: str):
    """
    Fetches one public catalog page. Every listing except latest requires stored episodes explicitly;
    the latest listing is ordered by stored episodes and therefore never includes anime without them.
    """
    if search_query:
        return db.search_anime(search_query, limit, offset, available_only=True)

    if genre:
        return db.fetch_animes_by_genre(genre, limit, offset, available_only=True)

    if status == "ongoing":
        return db.fetch_ongoing_animes(limit, offset, available_only=True)

    if sort == "latest":
        return db.fetch_animes_by_latest_episode(limit, offset)

    if sort == "popularity":
        return db.fetch_anime_by_popularity(limit, offset, available_only=True)

    if sort == "rating":
        return db.fetch_anime_by_rating(limit, offset, available_only=True)

    return db.fetch_all_animes(limit, offset, available_only=True)


@app.get("/anime")
@site_access_required
def get_animes():
    limit, offset = _pagination()
    search_query = _query_text("search")
    genre = _query_text("genre")
    status = _query_text("status").lower()
    sort = _query_text("sort", "title").lower()

    active_filters = sum(bool(value) for value in (search_query, genre, status))

    if active_filters > 1 or (active_filters and sort != "title"):
        raise ApiError("Use only one of search, genre, status, or sort at a time")

    if status and status != "ongoing":
        raise ApiError("status must be ongoing")

    if sort not in CATALOG_SORTS:
        raise ApiError("sort must be one of: title, latest, popularity, rating")

    with AnimeDatabase() as db:
        animes = _fetch_anime_catalog_page(db, limit + 1, offset, search_query, genre, status, sort)

    if animes is None:
        raise ApiError("Unable to fetch anime", 500)

    return _paginated("animes", animes, limit, offset)


@app.get("/anime/search-import")
@site_access_required
def import_anime_search():
    search_query = _query_text("search")

    if not search_query:
        raise ApiError("search is required")

    limit = _search_import_limit(default=None)

    if limit is None:
        events = anime_importer.iter_mal_anime_search_results(search_query)
    else:
        events = anime_importer.iter_mal_anime_search_results(search_query, limit=limit)

    return _ndjson_stream(events, "anime")


@app.post("/anime/import")
@site_access_required
def import_anime_from_navbar():
    mal_id = _mal_id_from_json()

    try:
        imported_anime, was_created = anime_importer.import_mal_anime(mal_id)
    except RequestException as e:
        logger.error("Unable to import MAL ID %s: %s", mal_id, e)
        raise ApiError("Unable to fetch anime from MyAnimeList", 502)
    except ValueError as e:
        raise ApiError(str(e))
    except Exception as e:
        logger.error("Unable to import MAL ID %s: %s", mal_id, e)
        raise ApiError("Unable to import anime", 502)

    return jsonify(anime=imported_anime.to_dict()), 201 if was_created else 200


@app.get("/anime/<string:slug>")
@site_access_required
def get_anime(slug):
    with AnimeDatabase() as db:
        anime = _find_anime(db, slug)

    return jsonify(anime=anime.to_dict()), 200


@app.get("/anime/<string:slug>/episodes")
@site_access_required
def get_anime_episodes(slug):
    with AnimeDatabase() as db:
        anime = _find_anime(db, slug)
        episodes = db.fetch_episodes_by_anime_id(anime.id)

    if episodes is None:
        raise ApiError("Unable to fetch episodes", 500)

    # Anime imported from navbar search start without episodes; synchronize them on first visit.
    if episodes == []:
        try:
            episode_sync = run_episode_sync_for_anime(anime.id, batch_episode_inserts=True)

            if episode_sync["animes_failed"]:
                logger.warning("Unable to sync every episode for anime %s", anime.id)
        except Exception as e:
            logger.error("Unable to lazily sync episodes for anime %s: %s", anime.id, e)

        with AnimeDatabase() as db:
            episodes = db.fetch_episodes_by_anime_id(anime.id)

        if episodes is None:
            raise ApiError("Unable to fetch episodes", 500)

    return jsonify(episodes=[episode.to_dict() for episode in episodes], count=len(episodes)), 200


@app.get("/anime/<string:slug>/episodes/<int:episode_number>")
@site_access_required
def get_anime_episode(slug, episode_number):
    _require_episode_number(episode_number)

    with AnimeDatabase() as db:
        anime = _find_anime(db, slug)
        episode = _find_episode(db, anime, episode_number)

    return jsonify(episode=episode.to_dict()), 200


@app.get("/anime/<string:slug>/episodes/<int:episode_number>/skip-times")
@site_access_required
def get_anime_episode_skip_times(slug, episode_number):
    _require_episode_number(episode_number)

    try:
        episode_length = float(request.args.get("episode_length", ""))
    except (TypeError, ValueError):
        raise ApiError("episode_length must be a number")

    if not isfinite(episode_length) or not 1 <= episode_length <= MAX_EPISODE_SECONDS:
        raise ApiError(f"episode_length must be between 1 and {MAX_EPISODE_SECONDS}")

    episode_length = round(episode_length, 3)

    with AnimeDatabase() as db:
        anime = _find_anime(db, slug)
        _find_episode(db, anime, episode_number)

    try:
        skip_times = fetch_aniskip_skip_times(mal_id=anime.id, episode_number=episode_number, episode_length=episode_length)
    except AniSkipError as e:
        logger.warning("Unable to fetch AniSkip times for MAL ID %s episode %s: %s", anime.id, episode_number, e)
        raise ApiError("Unable to fetch episode skip times", 502)

    response = jsonify(anime_id=anime.id, episode_number=episode_number, skip_times=skip_times)
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response, 200


@lru_cache(maxsize=256)
def _get_cached_manga_chapter_pages(provider_chapter_id: str, _cache_bucket: int):
    with MangaKatanaScraper(language="en") as scraper:
        return scraper.get_chapter_pages(provider_chapter_id)


def _load_manga_chapter_pages(provider_chapter_id: str):
    """
    Returns chapter page manifests cached per worker within ten-minute buckets.
    """
    cache_bucket = int(time.monotonic() // MANGA_CHAPTER_PAGE_CACHE_TTL)
    return _get_cached_manga_chapter_pages(provider_chapter_id, cache_bucket)


def _chapter_number(chapter_number: str) -> str:
    normalized_number = normalize_chapter_number(chapter_number)

    if normalized_number is None:
        raise ApiError("Chapter number must be a non-negative number")

    return normalized_number


def _fetch_manga_catalog_page(db, limit: int, offset: int, search_query: str, status: str, sort: str):
    if search_query:
        return db.search_manga(search_query, limit, offset, available_only=True)

    if status == "ongoing":
        return db.fetch_ongoing_mangas(limit, offset, available_only=True)

    if sort == "latest":
        return db.fetch_mangas_by_latest_chapter(limit, offset)

    if sort == "popularity":
        return db.fetch_manga_by_popularity(limit, offset, available_only=True)

    if sort == "rating":
        return db.fetch_manga_by_rating(limit, offset, available_only=True)

    return db.fetch_all_mangas(limit, offset, available_only=True)


@app.get("/manga")
@site_access_required
def get_mangas():
    limit, offset = _pagination()
    search_query = _query_text("search")
    status = _query_text("status").lower()
    sort = _query_text("sort", "title").lower()

    if search_query and (status or sort != "title"):
        raise ApiError("Use only one of search, status, or sort at a time")

    if status and (status != "ongoing" or sort != "title"):
        raise ApiError("status must be ongoing")

    if sort not in CATALOG_SORTS:
        raise ApiError("sort must be one of: title, latest, popularity, rating")

    with AnimeDatabase() as db:
        mangas = _fetch_manga_catalog_page(db, limit + 1, offset, search_query, status, sort)

    if mangas is None:
        raise ApiError("Unable to fetch manga", 500)

    return _paginated("mangas", mangas, limit, offset)


@app.get("/manga/search-import")
@site_access_required
def import_manga_search():
    search_query = _query_text("search")

    if not search_query:
        raise ApiError("search is required")

    limit = _search_import_limit(default=20)
    return _ndjson_stream(manga_importer.iter_mal_manga_search_results(search_query, limit=limit), "manga")


@app.post("/manga/import")
@site_access_required
def import_manga_from_navbar():
    mal_id = _mal_id_from_json()

    try:
        imported_manga, was_created = manga_importer.import_mal_manga(mal_id)
    except RequestException as e:
        logger.error("Unable to import manga MAL ID %s: %s", mal_id, e)
        raise ApiError("Unable to fetch manga from MyAnimeList", 502)
    except ValueError as e:
        raise ApiError(str(e))
    except Exception as e:
        logger.error("Unable to import manga MAL ID %s: %s", mal_id, e)
        raise ApiError("Unable to import manga", 502)

    return jsonify(manga=imported_manga.to_dict()), 201 if was_created else 200


@app.get("/manga/bookmarks")
@jwt_required()
def get_manga_bookmarks():
    limit, offset = _pagination()

    with AnimeDatabase() as db:
        mangas = db.fetch_manga_bookmarks(_current_user_id(), limit + 1, offset)

    if mangas is None:
        raise ApiError("Unable to fetch manga bookmarks", 500)

    return _paginated("mangas", mangas, limit, offset)


@app.get("/manga/<string:slug>")
@site_access_required
def get_manga(slug):
    with AnimeDatabase() as db:
        manga = _find_manga(db, slug)

    return jsonify(manga=manga.to_dict()), 200


@app.get("/manga/<string:slug>/chapters")
@site_access_required
def get_manga_chapters(slug):
    with AnimeDatabase() as db:
        manga = _find_manga(db, slug)
        chapters = db.fetch_chapters_by_manga_id(manga.id)

    if chapters is None:
        raise ApiError("Unable to fetch chapters", 500)

    # Imported manga start without resolved MangaKatana chapters; synchronize them on first visit.
    if not chapters or all(chapter.provider_chapter_id is None for chapter in chapters):
        try:
            chapter_sync = run_chapter_sync_for_manga(manga.id)

            if chapter_sync["mangas_failed"]:
                logger.warning("Unable to sync every chapter for manga %s", manga.id)
        except Exception as e:
            logger.error("Unable to lazily sync chapters for manga %s: %s", manga.id, e)

        with AnimeDatabase() as db:
            chapters = db.fetch_chapters_by_manga_id(manga.id)

        if chapters is None:
            raise ApiError("Unable to fetch chapters", 500)

    return jsonify(chapters=[chapter.to_dict() for chapter in chapters], count=len(chapters)), 200


@app.get("/manga/<string:slug>/chapters/<string:chapter_number>")
@site_access_required
def get_manga_chapter(slug, chapter_number):
    normalized_number = _chapter_number(chapter_number)

    with AnimeDatabase() as db:
        manga = _find_manga(db, slug)
        chapter = _find_chapter(db, manga, normalized_number)

    return jsonify(chapter=chapter.to_dict()), 200


@app.get("/manga/<string:slug>/chapters/<string:chapter_number>/pages")
@site_access_required
def get_manga_chapter_pages(slug, chapter_number):
    normalized_number = _chapter_number(chapter_number)

    with AnimeDatabase() as db:
        manga = _find_manga(db, slug)
        chapter = _find_chapter(db, manga, normalized_number)

    if chapter.provider_chapter_id is None:
        raise ApiError("Chapter pages are temporarily unavailable", 503)

    try:
        page_data = _load_manga_chapter_pages(chapter.provider_chapter_id)
        pages = [
            {
                "page": page["page"],
                "width": page.get("width"),
                "height": page.get("height"),
                "image_url": manga_image_proxy.build_manga_image_proxy_path(app.config["SECRET_KEY"], page["url"], fallback=f"page-{page['page']}.webp"),
            }
            for page in page_data["pages"]
        ]
    except MangaKatanaError as e:
        logger.warning("MangaKatana pages unavailable for MAL ID %s chapter %s: %s", manga.id, normalized_number, e)
        raise ApiError("Chapter pages are temporarily unavailable", 502)
    except manga_image_proxy.MangaImageProxyError as e:
        logger.warning("MangaKatana returned an invalid image URL: %s", e)
        raise ApiError("Chapter images are temporarily unavailable", 502)
    except Exception as e:
        logger.error("Unable to fetch pages for manga MAL ID %s chapter %s: %s", manga.id, normalized_number, e)
        raise ApiError("Unable to fetch chapter pages", 502)

    response = jsonify(manga=manga.to_dict(), chapter=chapter.to_dict(), pages=pages, count=len(pages))
    response.headers["Cache-Control"] = f"private, max-age={MANGA_CHAPTER_PAGE_RESPONSE_MAX_AGE}"
    return response, 200


@app.get("/manga/<string:slug>/bookmark")
@jwt_required(optional=True)
def get_manga_bookmark(slug):
    user_identity = get_jwt_identity()

    with AnimeDatabase() as db:
        manga = _find_manga(db, slug)
        is_bookmarked = db.is_manga_bookmarked(int(user_identity), manga.id) if user_identity is not None else False

    return jsonify(is_bookmarked=is_bookmarked), 200


@app.post("/manga/<string:slug>/bookmark")
@jwt_required()
def add_manga_bookmark(slug):
    with AnimeDatabase() as db:
        manga = _find_manga(db, slug)

        if not db.add_manga_bookmark(_current_user_id(), manga.id):
            raise ApiError("Unable to bookmark manga", 500)

    return jsonify(message="Manga bookmarked", is_bookmarked=True), 201


@app.delete("/manga/<string:slug>/bookmark")
@jwt_required()
def delete_manga_bookmark(slug):
    user_id = _current_user_id()

    with AnimeDatabase() as db:
        manga = _find_manga(db, slug)

        if db.is_manga_bookmarked(user_id, manga.id) and not db.delete_manga_bookmark(user_id, manga.id):
            raise ApiError("Unable to remove manga bookmark", 500)

    return jsonify(message="Manga bookmark removed", is_bookmarked=False), 200


@app.get("/watch-history")
@jwt_required()
def get_watch_history():
    limit, offset = _pagination()

    with AnimeDatabase() as db:
        history = db.fetch_watch_history_by_user_id(_current_user_id(), limit + 1, offset)

    if history is None:
        raise ApiError("Unable to fetch watch history", 500)

    return _paginated("watch_history", history, limit, offset)


@app.delete("/watch-history")
@jwt_required()
def delete_watch_history():
    with AnimeDatabase() as db:
        if not db.delete_watch_history_by_user_id(_current_user_id()):
            raise ApiError("Unable to clear watch history", 500)

    return jsonify(message="Watch history cleared successfully"), 200


@app.get("/watch-history/settings")
@jwt_required()
def get_watch_history_settings():
    user_id = _current_user_id()

    with AnimeDatabase() as db:
        _find_signed_in_user(db, user_id)
        tracking_enabled = db.get_watch_history_tracking_enabled(user_id)

    return jsonify(tracking_enabled=tracking_enabled), 200


@app.patch("/watch-history/settings")
@jwt_required()
def update_watch_history_settings():
    tracking_enabled = _json_field("tracking_enabled")

    if not isinstance(tracking_enabled, bool):
        raise ApiError("tracking_enabled must be true or false")

    user_id = _current_user_id()

    with AnimeDatabase() as db:
        _find_signed_in_user(db, user_id)

        if not db.set_watch_history_tracking_enabled(user_id, tracking_enabled):
            raise ApiError("Unable to update watch history setting", 500)

    return jsonify(message="Watch history setting updated successfully", tracking_enabled=tracking_enabled), 200


@app.get("/anime/<string:slug>/episodes/<int:episode_number>/watch-history")
@jwt_required()
def get_episode_watch_history(slug, episode_number):
    _require_episode_number(episode_number)
    user_id = _current_user_id()

    with AnimeDatabase() as db:
        _find_signed_in_user(db, user_id)

        if not db.get_watch_history_tracking_enabled(user_id):
            return jsonify(watch_history=None), 200

        anime = _find_anime(db, slug)
        episode = _find_episode(db, anime, episode_number)
        history = db.fetch_watch_history_by_user_and_episode(user_id, episode.id)

    return jsonify(watch_history=history.to_dict() if history else None), 200


@app.put("/anime/<string:slug>/episodes/<int:episode_number>/watch-history")
@jwt_required()
def save_episode_watch_history(slug, episode_number):
    _require_episode_number(episode_number)
    current_time_seconds, duration_seconds = _playback_position()
    current_time_seconds = round(current_time_seconds)
    duration_seconds = round(duration_seconds)
    user_id = _current_user_id()

    with AnimeDatabase() as db:
        _find_signed_in_user(db, user_id)

        if not db.get_watch_history_tracking_enabled(user_id):
            return jsonify(message="Watch history tracking is disabled", watch_history=None), 200

        anime = _find_anime(db, slug)
        episode = _find_episode(db, anime, episode_number)

        if not db.upsert_watch_history(user_id, episode.id, current_time_seconds, duration_seconds):
            raise ApiError("Unable to save watch history", 500)

        history = db.fetch_watch_history_by_user_and_episode(user_id, episode.id)

    if history is None:
        raise ApiError("Unable to fetch saved watch history", 500)

    return jsonify(message="Watch history saved successfully", watch_history=history.to_dict()), 200


@app.delete("/anime/<string:slug>/episodes/<int:episode_number>/watch-history")
@jwt_required()
def delete_episode_watch_history(slug, episode_number):
    _require_episode_number(episode_number)
    user_id = _current_user_id()

    with AnimeDatabase() as db:
        anime = _find_anime(db, slug)
        episode = _find_episode(db, anime, episode_number)

        if db.fetch_watch_history_by_user_and_episode(user_id, episode.id) is None:
            return jsonify(message="Watch history is already empty"), 200

        if not db.delete_watch_history_by_user_and_episode(user_id, episode.id):
            raise ApiError("Unable to delete watch history", 500)

    return jsonify(message="Watch history deleted successfully"), 200


@app.post("/anime/<string:slug>/episodes/<int:episode_number>/completion")
@jwt_required()
def complete_episode(slug, episode_number):
    """
    Records a unique episode completion once 90% has been watched, independently of history tracking.
    """
    _require_episode_number(episode_number)
    current_time_seconds, duration_seconds = _playback_position()

    if current_time_seconds < duration_seconds * COMPLETION_THRESHOLD:
        raise ApiError("Episode must be at least 90% watched")

    user_id = _current_user_id()

    with AnimeDatabase() as db:
        _find_signed_in_user(db, user_id)
        anime = _find_anime(db, slug)
        episode = _find_episode(db, anime, episode_number)
        was_created = db.mark_episode_completed(user_id, episode.id)

        if was_created is None:
            raise ApiError("Unable to mark episode completed", 500)

        episodes_completed = db.fetch_completed_episode_count(user_id)

    if episodes_completed is None:
        raise ApiError("Unable to fetch completed episode count", 500)

    message = "Episode marked completed" if was_created else "Episode was already completed"
    return jsonify(message=message, episodes_completed=episodes_completed), 201 if was_created else 200


def _load_episode(slug: str, episode_number: int):
    _require_episode_number(episode_number)

    with AnimeDatabase() as db:
        anime = _find_anime(db, slug)
        _find_episode(db, anime, episode_number)

    return anime


def _anime_titles(anime) -> tuple:
    return tuple(dict.fromkeys(title.strip() for title in (anime.title_english, anime.title) if isinstance(title, str) and title.strip()))


def _resolve_anilist_id(anime) -> int:
    """
    Returns the stored AniList ID, resolving and persisting it on demand.
    """
    try:
        with AnimeDatabase() as db:
            return anime_importer.ensure_anilist_id(anime, db)
    except Exception as e:
        logger.warning("Unable to resolve AniList ID for MAL ID %s: %s", anime.id, e)
        raise ApiError("Anime streaming source is temporarily unavailable", 503)


def _additional_anime_data(anime, provider: str) -> dict:
    anilist_id = anime.anilist_id

    if provider in ANILIST_REQUIRED_PROVIDERS and not anilist_id:
        with AnimeDatabase() as db:
            anilist_id = anime_importer.ensure_anilist_id(anime, db)

        if not anilist_id:
            raise ValueError("AniList mapping is unavailable")

    return {"mal_id": anime.id, "anilist_id": anilist_id, "titles": _anime_titles(anime)}


def _additional_stream(anime, episode_number: int, provider: str, category: str, quality: str | None):
    try:
        stream = additional.stream(provider, _additional_anime_data(anime, provider), episode_number, category, quality)
        proxy_options = {
            "secret_key": app.config["SECRET_KEY"],
            "provider": provider,
            "referer": stream["referer"],
            "category": category,
            "quality": quality,
            "manifest_key": stream.get("manifest_key"),
        }
        stream_url = additional_proxy.build_path(url=stream["url"], **proxy_options)
        subtitle_url = additional_proxy.build_path(url=stream["subtitle_url"], subtitle=True, **proxy_options) if stream.get("subtitle_url") else None
    except common.EpisodeNotFoundError as e:
        logger.warning("Playback unavailable for MAL ID %s episode %s provider %s: %s", anime.id, episode_number, provider, e)
        raise ApiError("This server is unavailable for the requested episode and version", 404)
    except (common.ProviderError, additional_proxy.PlaybackProxyError) as e:
        logger.warning("Playback failed for MAL ID %s episode %s provider %s: %s", anime.id, episode_number, provider, e)
        raise ApiError(f"{provider} could not load this episode from its upstream source", 502)
    except ValueError as e:
        raise ApiError(str(e))
    except Exception as e:
        logger.warning("Playback failed for MAL ID %s episode %s provider %s: %s", anime.id, episode_number, provider, e)
        raise ApiError("Unable to fetch episode stream", 502)

    return _no_store(jsonify(anime_id=anime.id, available_categories=stream["available_categories"], episode_number=episode_number, category=category, stream_url=stream_url, subtitle_url=subtitle_url))


def _anidb_stream(anime, episode_number: int, category: str, quality: str | None):
    stream = run_anidb_episode_stream(mal_id=anime.id, titles=_anime_titles(anime), episode_number=episode_number, category=category, quality=quality)
    stream_url = anidb_proxy.build_anidb_stream_proxy_path(secret_key=app.config["SECRET_KEY"], url=stream["url"], referer=stream["referer"], fallback="master.m3u8")
    return stream, stream_url, None


def _anizone_stream(anime, episode_number: int, category: str, quality: str | None):
    stream = run_anizone_episode_stream(mal_id=anime.id, titles=_anime_titles(anime), total_episodes=anime.total_episodes, episode_number=episode_number, category=category, quality=quality)
    proxy_options = {
        "secret_key": app.config["SECRET_KEY"],
        "referer": stream["referer"],
        "audio_language": stream["audio_language"],
        "quality": stream["quality"],
    }
    stream_url = anizone_proxy.build_anizone_stream_proxy_path(url=stream["url"], fallback="master.m3u8", **proxy_options)
    subtitle_url = anizone_proxy.build_anizone_stream_proxy_path(url=stream["subtitle_url"], resource_kind="subtitle", fallback="subtitles.vtt", **proxy_options) if stream["subtitle_url"] else None
    return stream, stream_url, subtitle_url


def _miruro_stream(anilist_id: int, episode_number: int, provider: str, category: str, quality: str | None):
    stream = run_episode_stream(anilist_id=anilist_id, episode_number=episode_number, category=category, provider=provider, quality=quality)
    secret_key = app.config["SECRET_KEY"]
    stream_url = miruro_proxy.build_stream_proxy_path(secret_key=secret_key, url=stream["url"], referer=stream["referer"], fallback="master.m3u8", resource_kind="playlist", category=category, quality=quality)
    subtitle_url = miruro_proxy.build_stream_proxy_path(secret_key=secret_key, url=stream["subtitle_url"], referer=stream["referer"], fallback="subtitles.vtt", resource_kind="subtitle") if stream.get("subtitle_url") else None
    return stream, stream_url, subtitle_url


@app.get("/anime/<string:slug>/episodes/<int:episode_number>/stream")
@site_access_required
def get_anime_episode_stream(slug, episode_number):
    _require_episode_number(episode_number)
    category = request.args.get("category", "sub").strip().lower()
    provider = request.args.get("provider", DEFAULT_PLAYBACK_PROVIDER).strip() or DEFAULT_PLAYBACK_PROVIDER
    quality = request.args.get("quality", "").strip() or None

    if category not in PLAYBACK_CATEGORIES:
        raise ApiError("category must be sub or dub")

    anime = _load_episode(slug, episode_number)

    if provider in additional.PROVIDERS:
        return _additional_stream(anime, episode_number, provider, category, quality)

    anilist_id = _resolve_anilist_id(anime) if provider not in {"anidb", "anizone"} else None

    try:
        if provider == "anidb":
            stream, stream_url, subtitle_url = _anidb_stream(anime, episode_number, category, quality)
        elif provider == "anizone":
            stream, stream_url, subtitle_url = _anizone_stream(anime, episode_number, category, quality)
        else:
            stream, stream_url, subtitle_url = _miruro_stream(anilist_id, episode_number, provider, category, quality)
    except ValueError as e:
        logger.warning("Stream unavailable for MAL ID %s episode %s provider %s category %s: %s", anime.id, episode_number, provider, category, e)
        raise ApiError(str(e), 404)
    except Exception as e:
        logger.error("Unable to fetch stream for MAL ID %s episode %s provider %s category %s: %s", anime.id, episode_number, provider, category, e)
        raise ApiError("Unable to fetch episode stream", 502)

    # Report the quality a fixed-quality source actually returned rather than the requested one.
    resolved_quality = str(stream.get("quality") or "").lower().removesuffix("p")

    return _no_store(jsonify(
        anime_id=anime.id,
        available_categories=stream["available_categories"],
        quality=f"{resolved_quality}p" if resolved_quality in LABELLED_QUALITIES else quality,
        episode_number=episode_number,
        category=category,
        stream_url=stream_url,
        subtitle_url=subtitle_url,
    ))


def _availability_response(anime, episode_number: int, available_categories: dict):
    return _no_store(jsonify(anime_id=anime.id, available_categories=available_categories, episode_number=episode_number))


@app.get("/anime/<string:slug>/episodes/<int:episode_number>/anidb/availability")
@site_access_required
def get_anidb_stream_availability(slug, episode_number):
    anime = _load_episode(slug, episode_number)

    try:
        categories = run_anidb_episode_availability(mal_id=anime.id, titles=_anime_titles(anime), episode_number=episode_number)
    except ValueError as e:
        logger.warning("AniDB availability unavailable for MAL ID %s episode %s: %s", anime.id, episode_number, e)
        raise ApiError(str(e), 404)
    except Exception as e:
        logger.error("Unable to fetch AniDB availability for MAL ID %s episode %s: %s", anime.id, episode_number, e)
        raise ApiError("Unable to fetch AniDB availability", 502)

    return _availability_response(anime, episode_number, {"anidb": categories})


@app.get("/anime/<string:slug>/episodes/<int:episode_number>/anizone/availability")
@site_access_required
def get_anizone_stream_availability(slug, episode_number):
    anime = _load_episode(slug, episode_number)

    try:
        categories = run_anizone_episode_availability(mal_id=anime.id, titles=_anime_titles(anime), total_episodes=anime.total_episodes, episode_number=episode_number)
    except ValueError as e:
        logger.warning("AniZone availability unavailable for MAL ID %s episode %s: %s", anime.id, episode_number, e)
        raise ApiError(str(e), 404)
    except Exception as e:
        logger.error("Unable to fetch AniZone availability for MAL ID %s episode %s: %s", anime.id, episode_number, e)
        raise ApiError("Unable to fetch AniZone availability", 502)

    return _availability_response(anime, episode_number, {"anizone": categories})


@app.get("/anime/<string:slug>/episodes/<int:episode_number>/miruro/availability")
@site_access_required
def get_miruro_stream_availability(slug, episode_number):
    anime = _load_episode(slug, episode_number)
    anilist_id = _resolve_anilist_id(anime)

    try:
        available_categories = run_episode_stream_availability(anilist_id=anilist_id, episode_number=episode_number)
    except ValueError as e:
        logger.warning("Miruro availability unavailable for MAL ID %s episode %s: %s", anime.id, episode_number, e)
        raise ApiError(str(e), 404)
    except Exception as e:
        logger.error("Unable to fetch Miruro availability for MAL ID %s episode %s: %s", anime.id, episode_number, e)
        raise ApiError("Unable to fetch Miruro availability", 502)

    return _availability_response(anime, episode_number, available_categories)


@app.get("/anime/<string:slug>/episodes/<int:episode_number>/playback/<string:provider>/availability")
@site_access_required
def get_additional_playback_availability(slug, episode_number, provider):
    if provider not in additional.PROVIDERS or episode_number < 1:
        raise ApiError("Invalid playback provider or episode")

    anime = _load_episode(slug, episode_number)

    try:
        categories = additional.availability(provider, _additional_anime_data(anime, provider), episode_number)
    except Exception as e:
        logger.warning("Playback availability failed for MAL ID %s episode %s provider %s: %s", anime.id, episode_number, provider, e)
        raise ApiError("Unable to fetch server availability", 502)

    return _no_store(jsonify(anime_id=anime.id, episode_number=episode_number, available_categories={provider: categories}))


@app.get("/streams/<string:token>/<path:resource_name>")
def proxy_stream_resource(token, resource_name):
    """
    Proxies Miruro server resources (AnimePahe, KickAssAnime, and AniWaves).
    """
    name = "stream"

    try:
        stream = miruro_proxy.decode_stream_proxy_token(app.config["SECRET_KEY"], token)
        upstream = miruro_proxy.fetch_stream_resource(url=stream["url"], referer=stream["referer"], range_header=request.headers.get("Range"), resource_kind=stream.get("resource_kind"))
    except SignatureExpired:
        raise ApiError("Stream URL has expired", 410)
    except miruro_proxy.StreamProxyError as e:
        logger.warning("Unable to proxy stream resource: %s", e)
        raise ApiError(str(e))

    _reject_failed_upstream(upstream, name)
    resource_kind = stream.get("resource_kind")
    content_type = upstream.headers.get("Content-Type", "application/octet-stream")
    upstream_resource_name = miruro_proxy.get_stream_resource_name(stream["url"], resource_name)

    if resource_kind == "subtitle" or upstream_resource_name.lower().endswith(".vtt"):
        try:
            subtitle = miruro_proxy.read_subtitle(upstream)
        except Exception as e:
            logger.warning("Unable to convert stream subtitle: %s", e)
            raise ApiError("Stream subtitle is unavailable", 502)

        response = Response(subtitle, content_type="text/vtt; charset=utf-8")
        response.headers["Cache-Control"] = "private, max-age=300"
        return response

    # AniWaves serves extensionless playlists as image/jpeg, so the signed kind takes precedence.
    if resource_kind == "playlist" or _is_playlist(upstream_resource_name, content_type):
        status_code = upstream.status_code
        playlist = _read_playlist(upstream, name, miruro_proxy.STREAM_PROXY_CHUNK_SIZE, miruro_proxy.STREAM_PROXY_MAX_PLAYLIST_SIZE)
        playlist = _rewrite_playlist(miruro_proxy.rewrite_hls_playlist, name, miruro_proxy.StreamProxyError, playlist=playlist, playlist_url=stream["url"], referer=stream["referer"], category=stream.get("category"), quality=stream.get("quality"))
        return _playlist_response(playlist, status_code)

    if resource_kind == "media" and content_type.lower().startswith("image/"):
        content_type = "application/octet-stream"

    return _media_response(upstream, content_type, miruro_proxy.STREAM_PROXY_CHUNK_SIZE)


@app.get("/anidb-streams/<string:token>/<path:resource_name>")
def proxy_anidb_stream_resource(token, resource_name):
    name = "AniDB stream"

    try:
        stream = anidb_proxy.decode_anidb_stream_proxy_token(app.config["SECRET_KEY"], token)
        upstream = anidb_proxy.fetch_anidb_stream_resource(url=stream["url"], referer=stream["referer"], range_header=request.headers.get("Range"))
    except SignatureExpired:
        raise ApiError("AniDB stream URL has expired", 410)
    except anidb_proxy.AniDBStreamProxyError as e:
        logger.warning("Unable to proxy AniDB stream resource: %s", e)
        raise ApiError(str(e))

    _reject_failed_upstream(upstream, name)
    content_type = anidb_proxy.get_anidb_stream_content_type(stream["url"], upstream.headers.get("Content-Type"))
    upstream_resource_name = anidb_proxy.get_anidb_stream_resource_name(stream["url"], resource_name)

    if _is_playlist(upstream_resource_name, content_type):
        status_code = upstream.status_code
        playlist = _read_playlist(upstream, name, anidb_proxy.ANIDB_STREAM_PROXY_CHUNK_SIZE, anidb_proxy.ANIDB_STREAM_PROXY_MAX_PLAYLIST_SIZE)
        playlist = _rewrite_playlist(anidb_proxy.rewrite_anidb_hls_playlist, name, anidb_proxy.AniDBStreamProxyError, playlist=playlist, playlist_url=stream["url"], referer=stream["referer"])
        return _playlist_response(playlist, status_code)

    return _media_response(upstream, content_type, anidb_proxy.ANIDB_STREAM_PROXY_CHUNK_SIZE)


@app.get("/anizone-streams/<string:token>/<path:resource_name>")
def proxy_anizone_stream_resource(token, resource_name):
    name = "AniZone stream"

    try:
        stream = anizone_proxy.decode_anizone_stream_proxy_token(app.config["SECRET_KEY"], token)
        upstream = anizone_proxy.fetch_anizone_stream_resource(url=stream["url"], referer=stream["referer"], resource_kind=stream["resource_kind"], range_header=request.headers.get("Range"))
    except SignatureExpired:
        raise ApiError("AniZone stream URL has expired", 410)
    except anizone_proxy.AniZoneStreamProxyError as e:
        logger.warning("Unable to proxy AniZone stream resource: %s", e)
        raise ApiError(str(e))

    _reject_failed_upstream(upstream, name)

    if stream["resource_kind"] == "subtitle":
        status_code = upstream.status_code

        try:
            payload = _read_limited(upstream, anizone_proxy.ANIZONE_STREAM_PROXY_CHUNK_SIZE, anizone_proxy.ANIZONE_STREAM_PROXY_MAX_SUBTITLE_SIZE, "AniZone subtitle file is too large")
            subtitle = anizone_proxy.convert_anizone_subtitle(payload, stream["url"])
        except ApiError as e:
            logger.warning("Unable to read AniZone subtitle file: %s", e.message)
            raise
        except anizone_proxy.AniZoneStreamProxyError as e:
            logger.warning("Unable to read AniZone subtitle file: %s", e)
            raise ApiError(str(e), 502)
        except Exception as e:
            logger.warning("Unable to read AniZone subtitle file: %s", e)
            raise ApiError("Unable to read AniZone subtitle file", 502)

        response = Response(subtitle, status=status_code, content_type="text/vtt; charset=utf-8")
        response.headers["Cache-Control"] = MEDIA_CACHE_CONTROL
        return response

    content_type = anizone_proxy.get_anizone_stream_content_type(stream["url"], upstream.headers.get("Content-Type"))
    upstream_resource_name = anizone_proxy.get_anizone_stream_resource_name(stream["url"], resource_name)

    if _is_playlist(upstream_resource_name, content_type):
        status_code = upstream.status_code
        playlist = _read_playlist(upstream, name, anizone_proxy.ANIZONE_STREAM_PROXY_CHUNK_SIZE, anizone_proxy.ANIZONE_STREAM_PROXY_MAX_PLAYLIST_SIZE)
        playlist = _rewrite_playlist(anizone_proxy.rewrite_anizone_hls_playlist, name, anizone_proxy.AniZoneStreamProxyError, playlist=playlist, playlist_url=stream["url"], referer=stream["referer"], audio_language=stream["audio_language"], quality=stream["quality"])
        return _playlist_response(playlist, status_code)

    return _media_response(upstream, content_type, anizone_proxy.ANIZONE_STREAM_PROXY_CHUNK_SIZE)


@app.get("/playback-streams/<string:token>/<path:resource_name>")
def proxy_additional_playback_resource(token, resource_name):
    """
    Proxies the additional providers, stripping image/XOR wrappers from media segments.
    """
    upstream = None

    try:
        payload = additional_proxy.decode_token(app.config["SECRET_KEY"], token)
        upstream = additional_proxy.fetch_resource(payload, request.headers.get("Range"))

        if upstream.status_code not in {200, 206}:
            raise ValueError(f"Playback upstream returned HTTP {upstream.status_code}")

        content_type = upstream.headers.get("Content-Type", "application/octet-stream")
        path = payload["url"].split("?", 1)[0].lower()

        if payload["subtitle"]:
            text = additional_proxy.convert_subtitle(additional_proxy.read_text(upstream, max_size=additional_proxy.MAX_SUBTITLE_SIZE))
            return Response(text, content_type="text/vtt", headers={"Cache-Control": "private, max-age=300"})

        if path.endswith(".m3u8") or "mpegurl" in content_type.lower():
            text = additional_proxy.read_text(upstream).decode("utf-8-sig")
            text = additional_proxy.rewrite_playlist(text, payload, app.config["SECRET_KEY"])
            return Response(text, content_type=HLS_CONTENT_TYPE, headers={"Cache-Control": "no-store"})

        for extension, media_type in additional_proxy.CONTENT_TYPES.items():
            if path.endswith(extension):
                content_type = media_type
                break

        chunks, stripped_bytes, detected_type = additional_proxy.prepare_media(upstream, payload)
        content_type = detected_type or content_type
    except SignatureExpired:
        raise ApiError("Playback URL has expired", 410)
    except Exception as e:
        if upstream is not None:
            upstream.close()

        logger.warning("Unable to proxy additional playback resource: %s", e)
        raise ApiError("Unable to fetch playback resource", 502)

    def generate_media():
        try:
            yield from chunks
        finally:
            upstream.close()

    response = Response(stream_with_context(generate_media()), status=upstream.status_code, content_type=content_type)

    for header_name in FORWARDED_MEDIA_HEADERS:
        if upstream.headers.get(header_name):
            response.headers[header_name] = upstream.headers[header_name]

    # Stripped wrappers change the byte layout, so upstream ranges and validators no longer apply.
    if stripped_bytes:
        if upstream.headers.get("Content-Length"):
            response.headers["Content-Length"] = str(int(upstream.headers["Content-Length"]) - stripped_bytes)

        for header_name in ("Content-Range", "Accept-Ranges", "ETag"):
            response.headers.pop(header_name, None)

    response.headers["Cache-Control"] = "private, max-age=300"
    response.call_on_close(upstream.close)
    return response


@app.get("/manga-images/<string:token>/<path:resource_name>")
def proxy_manga_image(token, resource_name):
    try:
        image_url = manga_image_proxy.decode_manga_image_proxy_token(app.config["SECRET_KEY"], token)
        upstream = manga_image_proxy.fetch_manga_image(image_url)
    except SignatureExpired:
        raise ApiError("Manga image URL has expired", 410)
    except manga_image_proxy.MangaImageProxyError as e:
        logger.warning("Unable to proxy manga image: %s", e)
        raise ApiError(str(e))

    if 300 <= upstream.status_code < 400:
        upstream.close()
        raise ApiError("Manga image host redirect was rejected", 502)

    if upstream.status_code >= 400:
        status_code = upstream.status_code
        upstream.close()
        logger.warning("Manga image host returned HTTP %s", status_code)
        raise ApiError("Unable to fetch manga image", 502)

    content_type = manga_image_proxy.get_manga_image_content_type(image_url, upstream.headers.get("Content-Type", ""))

    if not content_type.lower().startswith("image/"):
        upstream.close()
        raise ApiError("Manga image host returned invalid content", 502)

    try:
        content_length = int(upstream.headers.get("Content-Length", 0))
    except (TypeError, ValueError):
        content_length = 0

    if content_length > manga_image_proxy.MANGA_IMAGE_PROXY_MAX_SIZE:
        upstream.close()
        raise ApiError("Manga image is too large", 502)

    def generate_image():
        streamed_size = 0

        try:
            for chunk in upstream.iter_content(chunk_size=manga_image_proxy.MANGA_IMAGE_PROXY_CHUNK_SIZE):
                if not chunk:
                    continue

                streamed_size += len(chunk)

                if streamed_size > manga_image_proxy.MANGA_IMAGE_PROXY_MAX_SIZE:
                    logger.warning("Manga image exceeded the proxy size limit")
                    break

                yield chunk
        finally:
            upstream.close()

    response = Response(stream_with_context(generate_image()), status=upstream.status_code, content_type=content_type)

    for header_name in ("Content-Length", "ETag", "Last-Modified"):
        header_value = upstream.headers.get(header_name)

        if header_value:
            response.headers[header_name] = header_value

    response.headers["Cache-Control"] = "private, max-age=3600, immutable"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _parent_comment_id(data) -> int | None:
    parent_id = data.get("parent_id")

    if parent_id is None or parent_id == "":
        return None

    if isinstance(parent_id, bool):
        raise ApiError("parent_id must be a positive integer")

    try:
        parent_id = int(parent_id)
    except (TypeError, ValueError):
        raise ApiError("parent_id must be a positive integer")

    if parent_id < 1:
        raise ApiError("parent_id must be a positive integer")

    return parent_id


@app.get("/anime/<string:slug>/episodes/<int:episode_number>/comments")
@site_access_required
def get_episode_comments(slug, episode_number):
    _require_episode_number(episode_number)
    limit, offset = _pagination()

    with AnimeDatabase() as db:
        anime = _find_anime(db, slug)
        episode = _find_episode(db, anime, episode_number)
        episode_comments = db.fetch_comments_by_episode_id(episode.id, limit + 1, offset)

    if episode_comments is None:
        raise ApiError("Unable to fetch comments", 500)

    return _paginated("comments", episode_comments, limit, offset)


@app.post("/anime/<string:slug>/episodes/<int:episode_number>/comments")
@jwt_required()
def create_episode_comment(slug, episode_number):
    _require_episode_number(episode_number)
    data = _json_or_form()
    text = _comment_text(data)
    parent_id = _parent_comment_id(data)
    user_id = _current_user_id()

    with AnimeDatabase() as db:
        _find_signed_in_user(db, user_id)
        anime = _find_anime(db, slug)
        episode = _find_episode(db, anime, episode_number)

        if parent_id is not None:
            parent_comment = db.fetch_comment_by_id(parent_id)

            if parent_comment is None:
                raise ApiError("Parent comment not found", 404)

            if parent_comment.episode_id != episode.id:
                raise ApiError("Parent comment must belong to the same episode")

        comment_id = db.create_comment(user_id, episode.id, text, parent_id)

        if comment_id is None:
            raise ApiError("Unable to create comment", 500)

        comment = db.fetch_comment_by_id(comment_id)

    if comment is None:
        raise ApiError("Unable to fetch created comment", 500)

    return jsonify(status=201, message="Comment created successfully", comment=comment.to_dict()), 201


@app.patch("/comments/<int:comment_id>")
@jwt_required()
def edit_comment(comment_id):
    _require_positive_id(comment_id, "Comment ID")
    text = _comment_text(_json_or_form())
    user_id = _current_user_id()

    with AnimeDatabase() as db:
        comment = db.fetch_comment_by_id(comment_id)

        if comment is None:
            raise ApiError("Comment not found", 404)

        if comment.user_id != user_id:
            raise ApiError("You can only edit your own comments", 403)

        if not db.edit_comment(comment_id, text):
            raise ApiError("Unable to edit comment", 500)

        comment = db.fetch_comment_by_id(comment_id)

    if comment is None:
        raise ApiError("Unable to fetch edited comment", 500)

    return jsonify(message="Comment edited successfully", comment=comment.to_dict()), 200


@app.delete("/comments/<int:comment_id>")
@jwt_required()
def delete_comment(comment_id):
    _require_positive_id(comment_id, "Comment ID")
    user_id = _current_user_id()

    with AnimeDatabase() as db:
        comment = db.fetch_comment_by_id(comment_id)

        if comment is None:
            raise ApiError("Comment not found", 404)

        user = _find_signed_in_user(db, user_id)

        # Admins can moderate any comment; everyone else can only remove their own.
        if comment.user_id != user_id and user.is_admin != 1:
            raise ApiError("You can only delete your own comments", 403)

        if not db.delete_comment(comment_id):
            raise ApiError("Unable to delete comment", 500)

    return jsonify(message="Comment deleted successfully"), 200


def _mal_url() -> str:
    mal_url = request.form.get("mal_url", "").strip()

    if not mal_url:
        raise ApiError("MyAnimeList URL is required")

    return mal_url


def _scrape_mal_metadata(scrape, mal_url: str, media_label: str) -> dict:
    """
    Scrapes MyAnimeList metadata, translating failures into admin-facing errors.
    """
    log_label = "" if media_label == "anime" else f"{media_label} "

    try:
        return scrape(mal_url)
    except ValueError as e:
        raise ApiError(str(e))
    except RequestException as e:
        logger.error("Unable to scrape %sMyAnimeList URL %s: %s", log_label, mal_url, e)
        raise ApiError(f"Unable to fetch {media_label} from MyAnimeList", 502)
    except Exception as e:
        logger.error("Unable to parse %sMyAnimeList URL %s: %s", log_label, mal_url, e)
        raise ApiError(f"Unable to parse {media_label} from MyAnimeList", 502)


def _failed_sync_summary(record, prefix: str, unit: str, error: Exception) -> dict:
    return {
        f"{prefix}_found": 1,
        f"{prefix}_synced": 0,
        f"{prefix}_failed": 1,
        f"{unit}_added": 0,
        "failures": [{"mal_id": record.id, "title": record.title, "error": str(error)}],
    }


def _user_with_completions(user, episodes_completed: int) -> dict:
    return {**user.to_dict(), "episodes_completed": episodes_completed}


@app.get("/admin/users")
@admin_required
def get_users():
    with AnimeDatabase() as db:
        users = db.fetch_all_users()
        completed_episode_counts = db.fetch_completed_episode_counts()

    if users is None or completed_episode_counts is None:
        raise ApiError("Unable to fetch users", 500)

    return jsonify(users=[_user_with_completions(user, completed_episode_counts.get(user.id, 0)) for user in users]), 200


@app.patch("/admin/site-settings")
@admin_required
def update_site_settings():
    login_required = _json_field("login_required")

    if not isinstance(login_required, bool):
        raise ApiError("login_required must be true or false")

    with AnimeDatabase() as db:
        if not db.set_login_required(login_required):
            raise ApiError("Unable to update site settings", 500)

    return jsonify(message="Site settings updated successfully", login_required=login_required), 200


@app.patch("/admin/users/<int:user_id>")
@admin_required
def edit_admin_user(user_id):
    _require_positive_id(user_id, "User ID")
    data = _json_or_form()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password", "")
    is_admin = data.get("is_admin")

    if not isinstance(username, str) or not username.strip():
        raise ApiError("Username is required")

    if not isinstance(email, str) or not email.strip():
        raise ApiError("Email is required")

    if not isinstance(password, str):
        raise ApiError("Password must be a string")

    username = username.strip()
    email = email.strip()

    if len(username) > MAX_USERNAME_LENGTH:
        raise ApiError(f"Username must be {MAX_USERNAME_LENGTH} characters or fewer")

    if len(email) > MAX_EMAIL_LENGTH or "@" not in email:
        raise ApiError("Email must be valid")

    # bcrypt only uses the first 72 bytes of a password.
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ApiError(f"Password must be {MAX_PASSWORD_BYTES} bytes or fewer")

    if isinstance(is_admin, bool):
        is_admin = int(is_admin)
    elif not isinstance(is_admin, int) or is_admin not in {0, 1}:
        raise ApiError("is_admin must be true or false")

    if user_id == _current_user_id() and is_admin == 0:
        raise ApiError("You cannot remove your own admin access")

    with AnimeDatabase() as db:
        if db.fetch_user_by_id(user_id) is None:
            raise ApiError("User not found", 404)

        username_user = db.fetch_user(username)

        if username_user is not None and username_user.id != user_id:
            raise ApiError("Username already exists", 409)

        email_user = db.fetch_user_by_email(email)

        if email_user is not None and email_user.id != user_id:
            raise ApiError("Email already exists", 409)

        if not db.edit_user(user_id, username, email, is_admin, password):
            raise ApiError("Unable to update user", 500)

        user = db.fetch_user_by_id(user_id)
        episodes_completed = db.fetch_completed_episode_count(user_id)

    if user is None or episodes_completed is None:
        raise ApiError("Unable to fetch updated user", 500)

    return jsonify(status=200, message="User updated successfully", user=_user_with_completions(user, episodes_completed)), 200


@app.delete("/admin/users/<int:user_id>")
@admin_required
def delete_admin_user(user_id):
    _require_positive_id(user_id, "User ID")

    if user_id == _current_user_id():
        raise ApiError("You cannot delete your own account")

    with AnimeDatabase() as db:
        if db.fetch_user_by_id(user_id) is None:
            raise ApiError("User not found", 404)

        if not db.delete_user(user_id):
            raise ApiError("Unable to delete user", 500)

    return jsonify(status=200, message="User deleted successfully"), 200


@app.get("/admin/anime")
@admin_required
def get_admin_animes():
    """
    Lists the full library, including anime without stored episodes.
    """
    limit, offset = _pagination()
    search_query = _query_text("search")

    with AnimeDatabase() as db:
        animes = db.search_anime(search_query, limit + 1, offset) if search_query else db.fetch_all_animes(limit + 1, offset)

    if animes is None:
        raise ApiError("Unable to fetch anime", 500)

    return _paginated("animes", animes, limit, offset)


@app.post("/admin/anime")
@admin_required
def add_anime():
    anime_data = _scrape_mal_metadata(scrape_anime_meta_data, _mal_url(), "anime")

    with AnimeDatabase() as db:
        existing_anime = db.fetch_anime_by_id(anime_data["mal_id"])
        anime_importer.populate_anilist_id(anime_data, existing_anime.anilist_id if existing_anime is not None else None)

        if not db.upsert_anime(anime_data):
            raise ApiError("Unable to save anime", 500)

        anime = db.fetch_anime_by_id(anime_data["mal_id"])

    if anime is None:
        raise ApiError("Unable to fetch saved anime", 500)

    try:
        episode_sync = run_episode_sync_for_anime(anime.id, batch_episode_inserts=True)
    except Exception as e:
        logger.error("Unable to sync episodes for MAL ID %s: %s", anime.id, e)
        episode_sync = _failed_sync_summary(anime, "animes", "episodes", e)

    logger.info("Successfully scraped %s", anime.title)
    status_code = 200 if existing_anime else 201
    message = "Anime updated successfully" if existing_anime else "Anime added successfully"

    if episode_sync["animes_failed"]:
        message = f"{message}, but episodes could not be synced"

    return jsonify(status=status_code, message=message, anime=anime.to_dict(), episode_sync=episode_sync), status_code


@app.delete("/admin/anime/without-episodes")
@admin_required
def delete_animes_without_episodes():
    with AnimeDatabase() as db:
        deleted_count = db.delete_animes_without_episodes()

    if deleted_count is None:
        raise ApiError("Unable to delete anime without episodes", 500)

    return jsonify(status=200, message=f"Deleted {deleted_count} anime without episodes", deleted_count=deleted_count), 200


@app.delete("/admin/anime/<string:slug>")
@admin_required
def delete_anime(slug):
    with AnimeDatabase() as db:
        anime = _find_anime(db, slug)

        if not db.delete_anime(anime.id):
            raise ApiError("Unable to delete anime", 500)

    return jsonify(status=200, message="Anime deleted successfully"), 200


@app.get("/admin/manga")
@admin_required
def get_admin_mangas():
    """
    Lists the full library, including manga without stored chapters.
    """
    limit, offset = _pagination()
    search_query = _query_text("search")

    with AnimeDatabase() as db:
        mangas = db.search_manga(search_query, limit + 1, offset) if search_query else db.fetch_all_mangas(limit + 1, offset)

    if mangas is None:
        raise ApiError("Unable to fetch manga", 500)

    return _paginated("mangas", mangas, limit, offset)


@app.post("/admin/manga")
@admin_required
def add_manga():
    manga_data = _scrape_mal_metadata(scrape_manga_meta_data, _mal_url(), "manga")

    with AnimeDatabase() as db:
        existing_manga = db.fetch_manga_by_id(manga_data["mal_id"])
        manga_importer.populate_manga_anilist_id(manga_data, existing_manga.anilist_id if existing_manga is not None else None)

        if not db.upsert_manga(manga_data):
            raise ApiError("Unable to save manga", 500)

        manga = db.fetch_manga_by_id(manga_data["mal_id"])

    if manga is None:
        raise ApiError("Unable to fetch saved manga", 500)

    try:
        chapter_sync = run_chapter_sync_for_manga(manga.id)
    except Exception as e:
        logger.error("Unable to sync chapters for manga MAL ID %s: %s", manga.id, e)
        chapter_sync = _failed_sync_summary(manga, "mangas", "chapters", e)

    logger.info("Successfully scraped manga %s", manga.title)
    status_code = 200 if existing_manga else 201
    message = "Manga updated successfully" if existing_manga else "Manga added successfully"

    if chapter_sync["mangas_failed"]:
        message = f"{message}, but chapters could not be synced"

    return jsonify(status=status_code, message=message, manga=manga.to_dict(), chapter_sync=chapter_sync), status_code


@app.delete("/admin/manga/without-chapters")
@admin_required
def delete_mangas_without_chapters():
    with AnimeDatabase() as db:
        deleted_count = db.delete_mangas_without_chapters()

    if deleted_count is None:
        raise ApiError("Unable to delete manga without chapters", 500)

    return jsonify(status=200, message=f"Deleted {deleted_count} manga without chapters", deleted_count=deleted_count), 200


@app.delete("/admin/manga/<string:slug>")
@admin_required
def delete_manga(slug):
    with AnimeDatabase() as db:
        manga = _find_manga(db, slug)

        if not db.delete_manga(manga.id):
            raise ApiError("Unable to delete manga", 500)

    return jsonify(status=200, message="Manga deleted successfully"), 200


if __name__ == "__main__":
    schema.migrate()
    serve(app, host="0.0.0.0", port=PORT, threads=WAITRESS_THREADS)
