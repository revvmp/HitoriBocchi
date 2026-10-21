import asyncio

from database.database import AnimeDatabase
from scrapers import episode_catalog
from scrapers.providers import miruro
from services.anime_importer import ensure_anilist_id
from utils.logger import get_logger


logger = get_logger(__name__)


def _normalize_episode_number(episode_number) -> int | None:
    if isinstance(episode_number, bool):
        return None

    if isinstance(episode_number, int):
        return episode_number if episode_number > 0 else None

    if isinstance(episode_number, float):
        return int(episode_number) if episode_number.is_integer() and episode_number > 0 else None

    if isinstance(episode_number, str) and episode_number.strip().isdigit():
        episode_number = int(episode_number.strip())
        return episode_number if episode_number > 0 else None

    return None


def _record_failure(summary: dict, anime, error, episode_number: int | None = None):
    failure = {
        "mal_id": anime.id,
        "title": anime.title,
        "error": str(error),
    }

    if episode_number is not None:
        failure["episode_number"] = episode_number

    summary["failures"].append(failure)
    logger.error(
        f"Failed to sync {anime.title} (MAL ID: {anime.id})"
        f"{f', episode {episode_number}' if episode_number is not None else ''}: "
        f"{error}"
    )


async def sync_anime_episodes(batch_size: int = 20, category: str = "sub", provider: str | None = None, request_delay: float = 1.0, mal_id: int | None = None, batch_episode_inserts: bool = True) -> dict:
    """
    Adds missing episodes and refreshes episode counts.
   """
    if not isinstance(category, str) or category.casefold() not in {"sub", "dub"}:
        raise ValueError("category must be sub or dub")

    category = category.casefold()
    summary = {
        "animes_found": 0,
        "animes_synced": 0,
        "animes_failed": 0,
        "episodes_added": 0,
        "failures": [],
    }

    with AnimeDatabase() as db:
        anime_list = []

        if mal_id is not None:
            anime = db.fetch_anime_by_id(mal_id)

            if anime is None:
                raise ValueError(f"Anime with MAL ID {mal_id} was not found")

            anime_list.append(anime)
        else:
            offset = 0

            while True:
                anime_batch = db.fetch_ongoing_animes(limit=batch_size, offset=offset)

                if anime_batch is None:
                    raise RuntimeError("Failed to fetch ongoing anime from the database")

                anime_list.extend(anime_batch)

                if len(anime_batch) < batch_size:
                    break

                offset += batch_size

        summary["animes_found"] = len(anime_list)
        logger.info(f"Found {summary['animes_found']} anime to check for episodes")

        for anime in anime_list:
            stored_episodes = db.fetch_episodes_by_anime_id(anime.id)

            if stored_episodes is None:
                summary["animes_failed"] += 1
                _record_failure(summary, anime, "Failed to fetch stored episodes")
                continue

            stored_episode_numbers = {
                episode_number for episode in stored_episodes
                if (episode_number := _normalize_episode_number(episode.episode_number)) is not None
            }

            anime_failed = False

            try:
                if episode_catalog.requires_anilist_id():
                    anilist_id = ensure_anilist_id(anime, db)
                    scraped_episodes = await episode_catalog.get_anime_episodes(anilist_id, category=category, provider=provider)
                else:
                    scraped_episodes = await episode_catalog.get_catalog_episodes(anime, category=category, provider=provider)

            except miruro.PartialEpisodeInventoryError as error:
                scraped_episodes = error.episodes
                anime_failed = True

                for failure in error.failures:
                    _record_failure(summary, anime, failure["error"], failure["episode_number"])

            except Exception as error:
                summary["animes_failed"] += 1
                _record_failure(summary, anime, error)
                continue

            finally:
                if request_delay > 0:
                    await asyncio.sleep(request_delay)

            available_episodes = {}

            for episode in scraped_episodes:
                episode_number = _normalize_episode_number(episode.get("episode_number"))

                if episode_number is None:
                    continue

                available_episodes[episode_number] = (episode.get("title") or "Untitled")

            missing_episodes = []

            for episode_number, title in sorted(available_episodes.items()):
                if episode_number in stored_episode_numbers:
                    continue

                missing_episodes.append({
                    "anime_id": anime.id,
                    "episode_number": episode_number,
                    "provider_episode_id": None,
                    "title": title,
                })

            if batch_episode_inserts and missing_episodes:
                if db.upsert_episodes(missing_episodes):
                    missing_episode_numbers = {
                        episode["episode_number"] for episode in missing_episodes
                    }
                    stored_episode_numbers.update(missing_episode_numbers)
                    summary["episodes_added"] += len(missing_episodes)
                    logger.info(
                        f"Added {len(missing_episodes)} {anime.title} episodes "
                        f"in one transaction (MAL ID: {anime.id})"
                    )
                else:
                    anime_failed = True
                    _record_failure(
                        summary,
                        anime,
                        "Database batch upsert failed"
                    )
            else:
                for episode_data in missing_episodes:
                    episode_number = episode_data["episode_number"]

                    if db.upsert_episode(episode_data):
                        stored_episode_numbers.add(episode_number)
                        summary["episodes_added"] += 1
                        logger.info(
                            f"Added {anime.title} episode {episode_number} "
                            f"(MAL ID: {anime.id})"
                        )
                    else:
                        anime_failed = True
                        _record_failure(
                            summary,
                            anime,
                            "Database upsert failed",
                            episode_number
                        )

            if not db.update_anime_episode_counts(anime.id, len(stored_episode_numbers)):
                anime_failed = True
                _record_failure(summary, anime, "Failed to update episode count")

            if anime_failed:
                summary["animes_failed"] += 1
            else:
                summary["animes_synced"] += 1

    logger.info(
        f"Anime episode sync finished: {summary['episodes_added']} episodes added, "
        f"{summary['animes_synced']} anime synced, "
        f"{summary['animes_failed']} failed"
    )

    return summary


def run_episode_sync_for_anime(mal_id: int, category: str = "sub", provider: str | None = None, batch_episode_inserts: bool = True) -> dict:
    """
    Synchronous single-anime entry point for Flask routes and schedulers.
    """
    return asyncio.run(
        sync_anime_episodes(
            batch_size=1,
            category=category,
            provider=provider,
            request_delay=0,
            mal_id=mal_id,
            batch_episode_inserts=batch_episode_inserts
        )
    )


def run_anime_episode_sync(batch_size: int = 20, category: str = "sub", provider: str | None = None, request_delay: float = 1.0) -> dict:
    """
    Synchronous entry point for schedulers that cannot await a coroutine.
    """
    return asyncio.run(
        sync_anime_episodes(
            batch_size=batch_size,
            category=category,
            provider=provider,
            request_delay=request_delay
        )
    )
