from database.database import AnimeDatabase
from scrapers.metadata.mal import scrape_anime_meta_data
from scrapers.metadata.seasonal import get_current_season, scrape_seasonal_tv_anime
from services.anime_importer import populate_anilist_id
from utils.logger import get_logger


logger = get_logger(__name__)


def sync_seasonal_anime(year: int | None = None, season: str | None = None) -> dict:
    """
    Adds TV anime from a MyAnimeList season that are not already in the database.

    Defaults to the current calendar season and returns a summary of the sync.
    A failure for one anime is recorded without stopping the remaining anime.
    """
    current_year, current_season = get_current_season()
    year = current_year if year is None else year
    season = current_season if season is None else season
    seasonal_anime = scrape_seasonal_tv_anime(year, season)
    summary = {
        "year": year,
        "season": season.casefold(),
        "found": len(seasonal_anime),
        "added": 0,
        "skipped": 0,
        "failed": 0,
        "failures": [],
    }

    logger.info(
        f"Found {summary['found']} new TV anime for "
        f"{summary['season'].title()} {summary['year']}"
    )

    with AnimeDatabase() as db:
        for anime in seasonal_anime:
            mal_id = anime["mal_id"]
            title = anime["title"]

            if db.fetch_anime_by_id(mal_id) is not None:
                summary["skipped"] += 1
                continue

            try:
                anime_data = scrape_anime_meta_data(anime["mal_url"])
                populate_anilist_id(anime_data)

                if not db.upsert_anime(anime_data):
                    raise RuntimeError("Database upsert failed")

                summary["added"] += 1
                logger.info(f"Added {title} (MAL ID: {mal_id})")

            except Exception as error:
                summary["failed"] += 1
                summary["failures"].append({
                    "mal_id": mal_id,
                    "title": title,
                    "error": str(error),
                })
                logger.error(f"Failed to add {title} (MAL ID: {mal_id}): {error}")

    logger.info(
        f"Seasonal anime sync finished: {summary['added']} added, "
        f"{summary['skipped']} skipped, {summary['failed']} failed"
    )

    return summary


if __name__ == "__main__":
    sync_seasonal_anime()
