"""Seed the local catalog with popular Manga and Manhwa from MangaKatana."""

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from database.database import AnimeDatabase
from services.chapter_sync import sync_manga_record
from scrapers.metadata.mal import HEADERS, scrape_manga_meta_data
from scrapers.manga.mangakatana import MangaKatanaError, MangaKatanaScraper
from utils.logger import get_logger
from services.manga_importer import populate_manga_anilist_id


MAL_POPULAR_MANGA_URL = "https://myanimelist.net/topmanga.php"
MAL_POPULAR_MANGA_PAGE_SIZE = 50
SUPPORTED_MEDIA_TYPES = {"manga", "manhwa"}
DEFAULT_CHECKPOINT_PATH = Path("instance/manga_seed_checkpoint.json")

logger = get_logger(__name__)


def _is_supported_media_type(media_type: object) -> bool:
    return isinstance(media_type, str) and media_type.casefold() in SUPPORTED_MEDIA_TYPES


def _parse_popular_manga_page(page_html: str) -> list[dict]:
    """Parses one MyAnimeList popularity-ranking page."""
    soup = BeautifulSoup(page_html, "html.parser")
    manga_list = []
    seen_mal_ids = set()

    for ranking_row in soup.select("tr.ranking-list"):
        title_link = ranking_row.select_one("h3.manga_h3 a[href]")
        rank_element = ranking_row.select_one("td.rank span")
        information_element = ranking_row.select_one(".information")

        if title_link is None or rank_element is None:
            continue

        mal_url = title_link.get("href", "")
        parsed_url = urlparse(mal_url)
        manga_path = re.fullmatch(
            r"/manga/(\d+)(?:/[^/]+)?/?",
            parsed_url.path
        )

        try:
            rank = int(rank_element.get_text(" ", strip=True).replace(",", ""))
        except ValueError:
            continue

        if (
            parsed_url.scheme not in {"http", "https"}
            or parsed_url.hostname not in {
                "myanimelist.net",
                "www.myanimelist.net"
            }
            or manga_path is None
        ):
            continue

        mal_id = int(manga_path.group(1))
        title = title_link.get_text(" ", strip=True)

        if not title or mal_id in seen_mal_ids:
            continue

        information_lines = (
            [
                line.strip()
                for line in information_element.get_text("\n").splitlines()
                if line.strip()
            ]
            if information_element is not None
            else []
        )
        media_type_match = (
            re.match(r"^([^()]+?)\s*(?:\(|$)", information_lines[0])
            if information_lines
            else None
        )
        media_type = (
            media_type_match.group(1).strip()
            if media_type_match is not None
            else ""
        )
        seen_mal_ids.add(mal_id)
        manga_list.append({
            "rank": rank,
            "mal_id": mal_id,
            "title": title,
            "media_type": media_type,
            "mal_url": f"https://myanimelist.net{parsed_url.path.rstrip('/')}",
        })

    return manga_list


def fetch_popular_manga_page(offset: int) -> list[dict]:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("offset must be a non-negative integer")

    page = requests.get(
        MAL_POPULAR_MANGA_URL,
        params={"type": "bypopularity", "limit": offset},
        headers=HEADERS,
        timeout=30
    )
    page.raise_for_status()
    return _parse_popular_manga_page(page.text)


def iter_popular_manga(max_pages: int = 100):
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        raise ValueError("max_pages must be a positive integer")

    for page_number in range(max_pages):
        manga_list = fetch_popular_manga_page(
            page_number * MAL_POPULAR_MANGA_PAGE_SIZE
        )

        if not manga_list:
            break

        yield from manga_list

        if len(manga_list) < MAL_POPULAR_MANGA_PAGE_SIZE:
            break


def _empty_checkpoint() -> dict:
    return {
        "version": 1,
        "mangas": {},
        "unsupported_mal_ids": [],
    }


def _load_checkpoint(checkpoint_path: Path) -> dict:
    if not checkpoint_path.exists():
        return _empty_checkpoint()

    try:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Unable to read manga seed checkpoint {checkpoint_path}: {error}"
        ) from error

    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("version") != 1
        or not isinstance(checkpoint.get("mangas"), dict)
        or not isinstance(checkpoint.get("unsupported_mal_ids"), list)
    ):
        raise RuntimeError(f"Invalid manga seed checkpoint: {checkpoint_path}")

    return checkpoint


def _save_checkpoint(checkpoint_path: Path, checkpoint: dict) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = checkpoint_path.with_suffix(
        f"{checkpoint_path.suffix}.tmp"
    )
    temporary_path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    temporary_path.replace(checkpoint_path)


def _checkpoint_entry_is_complete(entry: dict | None, sync_chapters: bool) -> bool:
    if not isinstance(entry, dict) or not entry.get("mangakatana_id"):
        return False

    return not sync_chapters or entry.get("chapters_synced") is True


def _resolve_mangakatana_id(scraper: MangaKatanaScraper, manga_data: dict, ranking_entry: dict) -> str:
    titles = [
        manga_data.get("title_english", ""),
        manga_data.get("title", ""),
        ranking_entry.get("title", ""),
    ]
    anilist_id = manga_data.get("anilist_id")

    if anilist_id is not None:
        try:
            return scraper.resolve_anilist_id(anilist_id)
        except MangaKatanaError as error:
            logger.warning(
                "AniList title matching failed for manga MAL ID %s; "
                "retrying with MAL titles: %s",
                manga_data["mal_id"],
                error
            )

    return scraper.resolve_titles(titles, mal_id=manga_data["mal_id"])


def seed_manga_catalog(limit: int = 500, sync_chapters: bool = False, request_delay: float = 1.0, checkpoint_path: str | Path = DEFAULT_CHECKPOINT_PATH, max_ranking_pages: int = 100) -> dict:
    """
    Seeds popular MAL manga and manhwa that are available on MangaKatana.

    The limit is the desired total number of successfully handled titles in
    the checkpoint, making interrupted runs safe to resume.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    if (
        not isinstance(request_delay, (int, float))
        or isinstance(request_delay, bool)
        or request_delay < 0
    ):
        raise ValueError("request_delay cannot be negative")

    if (
        not isinstance(max_ranking_pages, int)
        or isinstance(max_ranking_pages, bool)
        or max_ranking_pages < 1
    ):
        raise ValueError("max_ranking_pages must be a positive integer")

    checkpoint_path = Path(checkpoint_path)
    checkpoint = _load_checkpoint(checkpoint_path)
    checkpoint_mangas = checkpoint["mangas"]
    unsupported_mal_ids = {
        int(mal_id) for mal_id in checkpoint["unsupported_mal_ids"]
    }
    summary = {
        "requested_limit": limit,
        "already_handled": sum(
            _checkpoint_entry_is_complete(entry, sync_chapters)
            for entry in checkpoint_mangas.values()
        ),
        "candidates_examined": 0,
        "added": 0,
        "existing": 0,
        "unsupported_type": 0,
        "unavailable": 0,
        "failed": 0,
        "chapters_added": 0,
        "handled": 0,
        "failures": [],
    }
    completed_count = summary["already_handled"]

    if completed_count >= limit:
        summary["handled"] = completed_count
        return summary

    with AnimeDatabase() as db:
        with MangaKatanaScraper(language="en") as scraper:
            for ranking_entry in iter_popular_manga(max_ranking_pages):
                mal_id = ranking_entry["mal_id"]
                checkpoint_entry = checkpoint_mangas.get(str(mal_id))

                if _checkpoint_entry_is_complete(checkpoint_entry, sync_chapters):
                    continue

                if mal_id in unsupported_mal_ids:
                    continue

                if not _is_supported_media_type(ranking_entry.get("media_type")):
                    unsupported_mal_ids.add(mal_id)
                    checkpoint["unsupported_mal_ids"] = sorted(unsupported_mal_ids)
                    summary["unsupported_type"] += 1
                    _save_checkpoint(checkpoint_path, checkpoint)
                    continue

                summary["candidates_examined"] += 1
                manga = db.fetch_manga_by_id(mal_id)
                was_existing = manga is not None

                try:
                    if manga is None:
                        manga_data = scrape_manga_meta_data(
                            ranking_entry["mal_url"]
                        )

                        if not _is_supported_media_type(manga_data.get("media_type")):
                            unsupported_mal_ids.add(mal_id)
                            checkpoint["unsupported_mal_ids"] = sorted(
                                unsupported_mal_ids
                            )
                            summary["unsupported_type"] += 1
                            _save_checkpoint(checkpoint_path, checkpoint)
                            continue

                        populate_manga_anilist_id(manga_data)
                        mangakatana_id = _resolve_mangakatana_id(
                            scraper,
                            manga_data,
                            ranking_entry
                        )
                        manga_data["mangakatana_id"] = mangakatana_id

                        if not db.upsert_manga(manga_data):
                            raise RuntimeError("Database manga upsert failed")

                        manga = db.fetch_manga_by_id(mal_id)

                        if manga is None:
                            raise RuntimeError("Unable to fetch saved manga")
                    else:
                        if not _is_supported_media_type(manga.media_type):
                            unsupported_mal_ids.add(mal_id)
                            checkpoint["unsupported_mal_ids"] = sorted(
                                unsupported_mal_ids
                            )
                            summary["unsupported_type"] += 1
                            _save_checkpoint(checkpoint_path, checkpoint)
                            continue

                        mangakatana_id = manga.mangakatana_id

                        if not mangakatana_id:
                            manga_data = {
                                "mal_id": manga.id,
                                "title": manga.title,
                                "title_english": manga.title_english,
                                "anilist_id": manga.anilist_id,
                            }
                            mangakatana_id = _resolve_mangakatana_id(
                                scraper,
                                manga_data,
                                ranking_entry
                            )

                            if not db.update_manga_mangakatana_id(
                                manga.id,
                                mangakatana_id
                            ):
                                raise RuntimeError(
                                    "Unable to save resolved MangaKatana ID"
                                )

                            manga.mangakatana_id = mangakatana_id

                    chapters_synced = False

                    if sync_chapters:
                        sync_result = sync_manga_record(db, manga, scraper)

                        if sync_result["chapters_available"] < 1:
                            raise MangaKatanaError(
                                "MangaKatana returned no readable chapters"
                            )

                        summary["chapters_added"] += sync_result["chapters_added"]
                        chapters_synced = True

                    checkpoint_mangas[str(mal_id)] = {
                        "mal_rank": ranking_entry["rank"],
                        "mangakatana_id": manga.mangakatana_id,
                        "media_type": manga.media_type,
                        "chapters_synced": chapters_synced,
                    }
                    _save_checkpoint(checkpoint_path, checkpoint)

                    if was_existing:
                        summary["existing"] += 1
                    else:
                        summary["added"] += 1

                    completed_count += 1
                    logger.info(
                        "Seeded %s (MAL ID: %s, MAL popularity rank: %s)",
                        manga.title,
                        manga.id,
                        ranking_entry["rank"]
                    )

                    if completed_count >= limit:
                        break

                except MangaKatanaError as error:
                    summary["unavailable"] += 1
                    logger.warning(
                        "Skipping %s (MAL ID: %s): %s",
                        ranking_entry["title"],
                        mal_id,
                        error
                    )
                except Exception as error:
                    summary["failed"] += 1
                    summary["failures"].append({
                        "mal_id": mal_id,
                        "title": ranking_entry["title"],
                        "error": str(error),
                    })
                    logger.error(
                        "Failed to seed %s (MAL ID: %s): %s",
                        ranking_entry["title"],
                        mal_id,
                        error
                    )
                finally:
                    if request_delay > 0 and completed_count < limit:
                        time.sleep(request_delay)

    summary["handled"] = completed_count
    logger.info(
        "Manga catalog seed finished: %s handled, %s added, %s existing, "
        "%s unavailable, %s failed",
        summary["handled"],
        summary["added"],
        summary["existing"],
        summary["unavailable"],
        summary["failed"]
    )
    return summary


def _parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Seed popular MyAnimeList manga and manhwa that are available "
            "on MangaKatana."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="desired total number of checkpointed manga and manhwa (default: 500)"
    )
    parser.add_argument(
        "--sync-chapters",
        action="store_true",
        help="also store every currently available MangaKatana chapter"
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=1.0,
        help="seconds to wait between ranking candidates (default: 1.0)"
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=DEFAULT_CHECKPOINT_PATH,
        help=(
            "checkpoint path relative to backend/src "
            "(default: instance/manga_seed_checkpoint.json)"
        )
    )
    parser.add_argument(
        "--max-ranking-pages",
        type=int,
        default=100,
        help="maximum MAL ranking pages to inspect (default: 100)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_arguments()
    result = seed_manga_catalog(
        limit=arguments.limit,
        sync_chapters=arguments.sync_chapters,
        request_delay=arguments.request_delay,
        checkpoint_path=arguments.checkpoint,
        max_ranking_pages=arguments.max_ranking_pages
    )
    print(json.dumps(result, indent=2))
