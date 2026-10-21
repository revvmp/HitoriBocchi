from requests import RequestException

from database.database import AnimeDatabase
from scrapers.metadata.anilist import AniListError, resolve_anilist_manga_id
from scrapers.metadata.mal import scrape_manga_meta_data, search_mal_manga
from utils.logger import get_logger


logger = get_logger(__name__)


def populate_manga_anilist_id(manga_data, current_anilist_id=None) -> bool:
    """
    Adds an AniList ID to scraped manga metadata when AniList is available.
    AniList failures do not block saving MyAnimeList metadata.
    """
    if current_anilist_id is not None:
        manga_data["anilist_id"] = current_anilist_id
        return True

    try:
        manga_data["anilist_id"] = resolve_anilist_manga_id(
            manga_data["mal_id"]
        )
        return True

    except AniListError as error:
        manga_data["anilist_id"] = None
        logger.warning(
            "Saving manga MAL ID %s without an AniList ID: %s",
            manga_data["mal_id"],
            error
        )
        return False


def ensure_manga_anilist_id(manga, db: AnimeDatabase) -> int:
    """Returns a manga's stored AniList ID, resolving and saving it if missing."""
    if manga.anilist_id is not None:
        return manga.anilist_id

    anilist_id = resolve_anilist_manga_id(manga.id)

    if not db.update_manga_anilist_id(manga.id, anilist_id):
        raise RuntimeError("Unable to save resolved manga AniList ID")

    manga.anilist_id = anilist_id
    logger.info(
        "Resolved manga MAL ID %s to AniList ID %s",
        manga.id,
        anilist_id
    )
    return anilist_id


def _serialize_transient_manga(manga_data):
    return {
        "id": manga_data["mal_id"],
        "title": manga_data["title"],
        "title_english": manga_data["title_english"],
        "slug": manga_data["slug"],
        "synopsis": manga_data["synopsis"],
        "image": manga_data["image"],
        "rating": manga_data["rating"],
        "genres": (
            manga_data["genres"].split(",")
            if manga_data["genres"]
            else []
        ),
        "status": manga_data["status"],
        "popularity": manga_data["popularity"],
        "media_type": manga_data["media_type"],
        "current_chapters": 0,
        "latest_chapter_number": "",
        "total_chapters": manga_data["total_chapters"],
        "updated_at": "",
        "requires_import": True,
    }


def _fetch_manga_metadata(search_result):
    try:
        manga_data = scrape_manga_meta_data(search_result["mal_url"])
        return _serialize_transient_manga(manga_data)
    except RequestException as e:
        logger.error(
            "Unable to fetch MyAnimeList manga metadata for %s: %s",
            search_result["mal_url"],
            e
        )
    except Exception as e:
        logger.error(
            "Unable to parse MyAnimeList manga metadata for %s: %s",
            search_result.get("mal_url", "unknown result"),
            e
        )

    return None


def iter_mal_manga_search_results(search_query, limit=20):
    try:
        search_results = search_mal_manga(search_query, limit=limit)
    except RequestException as e:
        logger.error("Unable to search MyAnimeList manga for %s: %s", search_query, e)
        yield {"type": "start", "total": 0}
        yield {"type": "error", "message": "Unable to search MyAnimeList"}
        yield {"type": "complete"}
        return
    except Exception as e:
        logger.error("Unable to search MyAnimeList manga for %s: %s", search_query, e)
        yield {"type": "start", "total": 0}
        yield {"type": "error", "message": "Unable to search MyAnimeList"}
        yield {"type": "complete"}
        return

    results = []

    with AnimeDatabase() as db:
        for search_result in search_results:
            manga = db.fetch_manga_by_id(search_result["mal_id"])
            results.append((
                search_result,
                manga,
                (
                    bool(db.fetch_chapters_by_manga_id(manga.id))
                    if manga is not None
                    else False
                )
            ))

    transient_count = sum(manga is None for _, manga, _ in results)
    yield {"type": "start", "total": transient_count}

    for search_result, manga, has_stored_chapters in results:
        replaces_skeleton = manga is None

        if manga is None:
            manga = _fetch_manga_metadata(search_result)
        elif not has_stored_chapters:
            manga = manga.to_dict()
            manga["requires_import"] = True

        if manga is None:
            yield {
                "type": "error",
                "message": f"Unable to fetch {search_result['title']}",
                "replaces_skeleton": replaces_skeleton,
            }
            continue

        yield {
            "type": "manga",
            "manga": manga,
            "replaces_skeleton": replaces_skeleton,
        }

    yield {"type": "complete"}


def import_mal_manga(mal_id):
    with AnimeDatabase() as db:
        existing_manga = db.fetch_manga_by_id(mal_id)

    if existing_manga is not None:
        return existing_manga, False

    manga_data = scrape_manga_meta_data(
        f"https://myanimelist.net/manga/{mal_id}"
    )

    if manga_data["mal_id"] != mal_id:
        raise ValueError("MyAnimeList returned a different manga")

    populate_manga_anilist_id(manga_data)

    with AnimeDatabase() as db:
        existing_manga = db.fetch_manga_by_id(mal_id)

        if existing_manga is not None:
            return existing_manga, False

        if not db.upsert_manga(manga_data):
            raise RuntimeError("Unable to save manga")

        manga = db.fetch_manga_by_id(mal_id)

    if manga is None:
        raise RuntimeError("Unable to fetch saved manga")

    logger.info("Added %s after its manga navbar card was opened", manga.title)
    return manga, True
