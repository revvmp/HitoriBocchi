from time import sleep

from database.database import AnimeDatabase
from scrapers.metadata.mal import scrape_anime_meta_data
from utils.logger import get_logger


logger = get_logger(__name__)


def sync_anime_metadata(batch_size: int = 20, request_delay: float = 1.0, status: str | None = None) -> dict:
    """
    Refreshes MAL-managed metadata for anime currently in the database.
    Optionally limits the refresh to anime with an exact status.
    """
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    if (not isinstance(request_delay, (int, float)) or isinstance(request_delay, bool) or request_delay < 0):
        raise ValueError("request_delay must be a non-negative number")

    if status is not None:
        if not isinstance(status, str) or not status.strip():
            raise ValueError("status must be a non-empty string")

        status = status.strip()

    summary = {
        "found": 0,
        "updated": 0,
        "failed": 0,
        "failures": [],
    }

    with AnimeDatabase() as db:
        anime_list = []
        offset = 0

        while True:
            if status is None:
                anime_batch = db.fetch_all_animes(limit=batch_size, offset=offset)
            else:
                anime_batch = db.fetch_animes_by_status(status, limit=batch_size, offset=offset)

            if anime_batch is None:
                raise RuntimeError("Failed to fetch anime from the database")

            anime_list.extend(anime_batch)

            if len(anime_batch) < batch_size:
                break

            offset += batch_size

        summary["found"] = len(anime_list)
        metadata_scope = "anime" if status is None else f"{status} anime"
        logger.info(f"Found {summary['found']} {metadata_scope} with metadata to update")

        for index, anime in enumerate(anime_list, start=1):
            mal_url = f"https://myanimelist.net/anime/{anime.id}"

            try:
                anime_data = scrape_anime_meta_data(mal_url)

                if not db.upsert_anime(anime_data):
                    raise RuntimeError("Database upsert failed")

                summary["updated"] += 1
                logger.info(f"Updated {anime.title} (MAL ID: {anime.id})")

            except Exception as error:
                summary["failed"] += 1
                summary["failures"].append({
                    "mal_id": anime.id,
                    "title": anime.title,
                    "error": str(error),
                })
                logger.error(
                    f"Failed to update {anime.title} "
                    f"(MAL ID: {anime.id}): {error}"
                )

            if request_delay > 0 and index < len(anime_list):
                sleep(request_delay)

    logger.info(
        f"{metadata_scope.capitalize()} metadata sync finished: "
        f"{summary['updated']} updated, "
        f"{summary['failed']} failed"
    )

    return summary


if __name__ == "__main__":
    sync_anime_metadata()
