import time
from decimal import Decimal, InvalidOperation

from database.database import AnimeDatabase
from scrapers.manga.mangakatana import MangaKatanaError, MangaKatanaScraper
from utils.logger import get_logger
from services.manga_importer import ensure_manga_anilist_id


logger = get_logger(__name__)


def normalize_chapter_number(chapter_number) -> str | None:
    """Returns a stable non-negative decimal chapter number."""
    if isinstance(chapter_number, bool):
        return None

    try:
        number = Decimal(str(chapter_number).strip())
    except (InvalidOperation, ValueError):
        return None

    if not number.is_finite() or number < 0:
        return None

    normalized = format(number.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _record_failure(summary: dict, manga, error):
    summary["failures"].append({
        "mal_id": manga.id,
        "title": manga.title,
        "error": str(error),
    })
    logger.error(
        "Failed to sync %s (manga MAL ID: %s): %s",
        manga.title,
        manga.id,
        error
    )


def sync_manga_record(db, manga, scraper: MangaKatanaScraper) -> dict:
    """Synchronizes one stored manga using an existing database and scraper."""
    stored_chapters = db.fetch_chapters_by_manga_id(manga.id)

    if stored_chapters is None:
        raise RuntimeError("Failed to fetch stored chapters")

    stored_numbers = {
        chapter.chapter_number for chapter in stored_chapters
    }
    mangakatana_id = manga.mangakatana_id

    if not mangakatana_id:
        anilist_id = ensure_manga_anilist_id(manga, db)

        try:
            mangakatana_id = scraper.resolve_anilist_id(anilist_id)
        except MangaKatanaError as error:
            logger.warning(
                "AniList title matching failed for manga MAL ID %s; "
                "retrying with stored MAL titles: %s",
                manga.id,
                error
            )
            mangakatana_id = scraper.resolve_titles(
                [manga.title_english, manga.title],
                mal_id=manga.id
            )

        if not db.update_manga_mangakatana_id(manga.id, mangakatana_id):
            raise RuntimeError("Unable to save resolved MangaKatana ID")

        manga.mangakatana_id = mangakatana_id

    scraped_chapters = scraper.get_chapters(mangakatana_id)
    chapter_rows = []
    available_numbers = set()

    for chapter in scraped_chapters:
        chapter_number = normalize_chapter_number(chapter.get("number"))

        if chapter_number is None:
            continue

        available_numbers.add(chapter_number)
        chapter_rows.append({
            "manga_id": manga.id,
            "chapter_number": chapter_number,
            "provider_chapter_id": chapter["id"],
            "title": chapter.get("name") or "",
            "released_at": chapter.get("created_at"),
        })

    chapter_rows.sort(
        key=lambda chapter: Decimal(chapter["chapter_number"])
    )

    if chapter_rows and not db.upsert_chapters(chapter_rows):
        raise RuntimeError("Database chapter upsert failed")

    added_count = len(available_numbers - stored_numbers)
    stored_numbers.update(available_numbers)

    if not db.update_manga_chapter_counts(manga.id, len(stored_numbers)):
        raise RuntimeError("Failed to update chapter count")

    return {
        "chapters_added": added_count,
        "chapters_available": len(available_numbers),
        "mangakatana_id": mangakatana_id,
    }


def sync_manga_chapters(batch_size: int = 20, request_delay: float = 1.0, mal_id: int | None = None) -> dict:
    """Adds missing MangaKatana chapters for publishing manga."""
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    if not isinstance(request_delay, (int, float)) or isinstance(request_delay, bool) or request_delay < 0:
        raise ValueError("request_delay cannot be negative")

    summary = {
        "mangas_found": 0,
        "mangas_synced": 0,
        "mangas_failed": 0,
        "chapters_added": 0,
        "failures": [],
    }

    with AnimeDatabase() as db:
        manga_list = []

        if mal_id is not None:
            manga = db.fetch_manga_by_id(mal_id)

            if manga is None:
                raise ValueError(f"Manga with MAL ID {mal_id} was not found")

            manga_list.append(manga)
        else:
            offset = 0

            while True:
                manga_batch = db.fetch_ongoing_mangas(
                    limit=batch_size,
                    offset=offset
                )

                if manga_batch is None:
                    raise RuntimeError("Failed to fetch publishing manga from the database")

                manga_list.extend(manga_batch)

                if len(manga_batch) < batch_size:
                    break

                offset += batch_size

        summary["mangas_found"] = len(manga_list)
        logger.info("Found %s manga to check for chapters", len(manga_list))

        with MangaKatanaScraper(language="en") as scraper:
            for index, manga in enumerate(manga_list):
                try:
                    sync_result = sync_manga_record(db, manga, scraper)
                except Exception as error:
                    summary["mangas_failed"] += 1
                    _record_failure(summary, manga, error)
                    continue
                finally:
                    if request_delay > 0 and index < len(manga_list) - 1:
                        time.sleep(request_delay)

                summary["chapters_added"] += sync_result["chapters_added"]
                summary["mangas_synced"] += 1
                logger.info(
                    "Synced %s manga chapters for %s (MAL ID: %s)",
                    sync_result["chapters_available"],
                    manga.title,
                    manga.id
                )

    logger.info(
        "Manga chapter sync finished: %s chapters added, %s manga synced, %s failed",
        summary["chapters_added"],
        summary["mangas_synced"],
        summary["mangas_failed"]
    )
    return summary


def run_chapter_sync_for_manga(mal_id: int) -> dict:
    """Synchronous single-manga entry point for Flask routes."""
    return sync_manga_chapters(
        batch_size=1,
        request_delay=0,
        mal_id=mal_id
    )
