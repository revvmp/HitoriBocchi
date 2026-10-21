from requests import RequestException

from database.database import AnimeDatabase
from scrapers.metadata.anilist import AniListError, resolve_anilist_id
from scrapers.metadata.mal import scrape_anime_meta_data, search_mal_anime
from utils.logger import get_logger


logger = get_logger(__name__)


def populate_anilist_id(anime_data, current_anilist_id=None) -> bool:
    """
    Adds an AniList ID to scraped MAL metadata when AniList is available.
    Returns False without blocking the import when resolution fails.
    """
    if current_anilist_id is not None:
        anime_data["anilist_id"] = current_anilist_id
        return True

    try:
        anime_data["anilist_id"] = resolve_anilist_id(anime_data["mal_id"])
        return True

    except AniListError as error:
        anime_data["anilist_id"] = None
        logger.warning(
            "Saving MAL ID %s without an AniList ID: %s",
            anime_data["mal_id"],
            error
        )
        return False


def ensure_anilist_id(anime, db: AnimeDatabase) -> int:
    """
    Returns the stored AniList ID, resolving and saving it when it is missing.
    """
    if anime.anilist_id is not None:
        return anime.anilist_id

    anilist_id = resolve_anilist_id(anime.id)

    if not db.update_anime_anilist_id(anime.id, anilist_id):
        raise RuntimeError("Unable to save resolved AniList ID")

    anime.anilist_id = anilist_id
    logger.info(
        "Resolved MAL ID %s to AniList ID %s",
        anime.id,
        anilist_id
    )
    return anilist_id


def _serialize_transient_anime(anime_data):
    return {
        "id": anime_data["mal_id"],
        "title": anime_data["title"],
        "title_english": anime_data["title_english"],
        "slug": anime_data["slug"],
        "synopsis": anime_data["synopsis"],
        "image": anime_data["image"],
        "rating": anime_data["rating"],
        "genres": (
            anime_data["genres"].split(",")
            if anime_data["genres"]
            else []
        ),
        "status": anime_data["status"],
        "popularity": anime_data["popularity"],
        "current_episodes": 0,
        "latest_episode_number": 0,
        "total_episodes": anime_data["total_episodes"],
        "updated_at": "",
        "requires_import": True,
    }


def _fetch_anime_metadata(search_result):
    try:
        anime_data = scrape_anime_meta_data(search_result["mal_url"])
        return _serialize_transient_anime(anime_data)
    except RequestException as e:
        logger.error(
            "Unable to fetch MyAnimeList metadata for %s: %s",
            search_result["mal_url"],
            e
        )
    except Exception as e:
        logger.error(
            "Unable to parse MyAnimeList metadata for %s: %s",
            search_result.get("mal_url", "unknown result"),
            e
        )

    return None


def iter_mal_anime_search_results(search_query, limit=20):
    try:
        search_results = search_mal_anime(search_query, limit=limit)
    except RequestException as e:
        logger.error("Unable to search MyAnimeList for %s: %s", search_query, e)
        yield {"type": "start", "total": 0}
        yield {"type": "error", "message": "Unable to search MyAnimeList"}
        yield {"type": "complete"}
        return
    except Exception as e:
        logger.error("Unable to search MyAnimeList for %s: %s", search_query, e)
        yield {"type": "start", "total": 0}
        yield {"type": "error", "message": "Unable to search MyAnimeList"}
        yield {"type": "complete"}
        return

    results = []

    with AnimeDatabase() as db:
        for search_result in search_results:
            anime = db.fetch_anime_by_id(search_result["mal_id"])
            results.append((
                search_result,
                anime,
                (
                    bool(db.fetch_episodes_by_anime_id(anime.id))
                    if anime is not None
                    else False
                )
            ))

    transient_count = sum(anime is None for _, anime, _ in results)
    yield {"type": "start", "total": transient_count}

    for search_result, anime, has_stored_episodes in results:
        replaces_skeleton = anime is None

        if anime is None:
            anime = _fetch_anime_metadata(search_result)
        elif not has_stored_episodes:
            anime = anime.to_dict()
            anime["requires_import"] = True

        if anime is None:
            yield {
                "type": "error",
                "message": f"Unable to fetch {search_result['title']}",
                "replaces_skeleton": replaces_skeleton,
            }
            continue

        yield {
            "type": "anime",
            "anime": anime,
            "replaces_skeleton": replaces_skeleton,
        }

    yield {"type": "complete"}


def import_mal_anime(mal_id):
    with AnimeDatabase() as db:
        existing_anime = db.fetch_anime_by_id(mal_id)

    if existing_anime is not None:
        return existing_anime, False

    anime_data = scrape_anime_meta_data(
        f"https://myanimelist.net/anime/{mal_id}"
    )

    if anime_data["mal_id"] != mal_id:
        raise ValueError("MyAnimeList returned a different anime")

    populate_anilist_id(anime_data)

    with AnimeDatabase() as db:
        existing_anime = db.fetch_anime_by_id(mal_id)

        if existing_anime is not None:
            return existing_anime, False

        if not db.upsert_anime(anime_data):
            raise RuntimeError("Unable to save anime")

        anime = db.fetch_anime_by_id(mal_id)

    if anime is None:
        raise RuntimeError("Unable to fetch saved anime")

    logger.info("Added %s after its navbar card was opened", anime.title)
    return anime, True
