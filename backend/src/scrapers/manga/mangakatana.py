"""Browserless MangaKatana title, chapter, and image-page scraper."""

import ast
import re
import time
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests


BASE_URL = "https://mangakatana.com"
ANILIST_URL = "https://graphql.anilist.co"
TITLE_SEARCH_DELAY = 5.0

TITLE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*\.[1-9]\d*$", re.IGNORECASE)
TITLE_PATH_PATTERN = re.compile(
    r"^/manga/(?P<title_id>[a-z0-9][a-z0-9-]*\.[1-9]\d*)/?$",
    re.IGNORECASE
)
CHAPTER_PATH_PATTERN = re.compile(
    r"^/manga/(?P<title_id>[a-z0-9][a-z0-9-]*\.[1-9]\d*)/"
    r"c(?P<number>\d+(?:\.\d+)?)/?$",
    re.IGNORECASE
)

__all__ = [
    "MangaKatanaError",
    "MangaKatanaScraper",
    "get_available_chapter_count",
    "get_available_chapter_count_by_anilist_id",
    "get_chapter_images",
    "get_chapter_images_by_anilist_id",
    "scrape_manga_by_anilist_id",
    "scrape_manga_by_mal_id",
]


class MangaKatanaError(RuntimeError):
    """Raised when MangaKatana cannot be loaded or returns invalid data."""


def _validate_mal_id(mal_id: int) -> int:
    if not isinstance(mal_id, int) or isinstance(mal_id, bool) or mal_id <= 0:
        raise ValueError("mal_id must be a positive integer")
    return mal_id


def _validate_anilist_id(anilist_id: int) -> int:
    if (
        not isinstance(anilist_id, int)
        or isinstance(anilist_id, bool)
        or anilist_id <= 0
    ):
        raise ValueError("anilist_id must be a positive integer")
    return anilist_id


def _main_chapter_number_key(value: Any) -> str | None:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None

    if not number.is_finite() or number < 0:
        return None

    normalized = format(number.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _deduplicate_chapters(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}

    for chapter in chapters:
        key = _main_chapter_number_key(chapter.get("number"))

        if key is not None and key not in selected:
            selected[key] = chapter

    return list(selected.values())


def _normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in value if character.isalnum())


def _parse_release_date(value: str) -> str | None:
    normalized_value = value.strip()

    for date_format in ("%b-%d-%Y", "%b %d, %Y"):
        try:
            parsed_date = datetime.strptime(normalized_value, date_format)
        except ValueError:
            continue

        return parsed_date.replace(tzinfo=timezone.utc).isoformat().replace(
            "+00:00",
            "Z"
        )

    return None


def _parse_title_id(url: str) -> str | None:
    parsed_url = urlsplit(url)

    if parsed_url.hostname not in {"mangakatana.com", "www.mangakatana.com"}:
        return None

    title_match = TITLE_PATH_PATTERN.fullmatch(parsed_url.path)
    return title_match.group("title_id") if title_match is not None else None


def _parse_chapter_path(url: str) -> tuple[str, str, str] | None:
    parsed_url = urlsplit(url)

    if parsed_url.hostname not in {"mangakatana.com", "www.mangakatana.com"}:
        return None

    chapter_match = CHAPTER_PATH_PATTERN.fullmatch(parsed_url.path)

    if chapter_match is None:
        return None

    chapter_number = _main_chapter_number_key(chapter_match.group("number"))

    if chapter_number is None:
        return None

    title_id = chapter_match.group("title_id")
    return title_id, chapter_number, f"{title_id}/c{chapter_match.group('number')}"


def _parse_script_array(soup: BeautifulSoup, variable_name: str) -> list[Any]:
    array_pattern = re.compile(
        rf"\bvar\s+{re.escape(variable_name)}\s*=\s*(\[.*?\])\s*;",
        re.DOTALL
    )

    for script in soup.select("script"):
        script_text = script.get_text()
        array_match = array_pattern.search(script_text)

        if array_match is None:
            continue

        try:
            values = ast.literal_eval(array_match.group(1))
        except (SyntaxError, ValueError):
            return []

        return values if isinstance(values, list) else []

    return []


def _request_anilist_manga(query: str, variables: dict[str, int], identifier: str, timeout: float, retries: int) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    last_error = "unknown error"

    for attempt in range(1, retries + 1):
        try:
            response = curl_requests.post(
                ANILIST_URL,
                json={"query": query, "variables": variables},
                headers={"Accept": "application/json"},
                impersonate="chrome",
                timeout=timeout,
            )

            if response.status_code == 200:
                parsed_payload = response.json()

                if isinstance(parsed_payload, dict):
                    payload = parsed_payload
                    break

                last_error = "AniList returned an unexpected response"
            else:
                last_error = f"AniList returned HTTP {response.status_code}"

                if response.status_code not in {408, 425, 429} and response.status_code < 500:
                    break
        except Exception as error:
            last_error = str(error)

        if attempt < retries:
            time.sleep(min(2 ** (attempt - 1), 4))

    if payload is None:
        raise MangaKatanaError(
            f"Could not resolve {identifier} through AniList after "
            f"{retries} attempts: {last_error}"
        )

    if payload.get("errors"):
        message = payload["errors"][0].get("message", "unknown GraphQL error")
        raise MangaKatanaError(f"Could not resolve {identifier}: {message}")

    media = payload.get("data", {}).get("Media")

    if not isinstance(media, dict):
        raise MangaKatanaError(f"No manga was found for {identifier}")

    return media


def _build_manga_title_record(media: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    title_data = media.get("title")

    if isinstance(title_data, dict):
        candidates.extend(
            title_data.get(key) for key in ("english", "romaji", "native")
        )

    candidates.extend(media.get("synonyms") or [])
    titles = []
    seen = set()

    for title in candidates:
        if not isinstance(title, str) or not title.strip():
            continue

        normalized = _normalize_title(title)

        if normalized and normalized not in seen:
            seen.add(normalized)
            titles.append(title.strip())

    if not titles:
        raise MangaKatanaError("AniList returned no searchable manga titles")

    return {
        "mal_id": media.get("idMal"),
        "anilist_id": media.get("id"),
        "titles": titles,
    }


def get_mal_manga_titles(mal_id: int, timeout: float = 30.0, retries: int = 3) -> dict[str, Any]:
    """Resolve a MAL manga ID to AniList's canonical titles and synonyms."""
    mal_id = _validate_mal_id(mal_id)

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 1:
        raise ValueError("retries must be a positive integer")

    query = """
    query ($malId: Int!) {
        Media(idMal: $malId, type: MANGA) {
            id
            idMal
            title { romaji english native }
            synonyms
        }
    }
    """
    media = _request_anilist_manga(
        query,
        {"malId": mal_id},
        f"MAL manga ID {mal_id}",
        timeout,
        retries
    )

    if media.get("idMal") != mal_id:
        raise MangaKatanaError(
            f"No manga was found for MyAnimeList ID {mal_id}. "
            "Make sure this is a manga ID, not an anime ID."
        )

    return _build_manga_title_record(media)


def get_anilist_manga_titles(anilist_id: int, timeout: float = 30.0, retries: int = 3) -> dict[str, Any]:
    """Resolve an AniList manga ID to its MAL ID, titles, and synonyms."""
    anilist_id = _validate_anilist_id(anilist_id)

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 1:
        raise ValueError("retries must be a positive integer")

    query = """
    query ($anilistId: Int!) {
        Media(id: $anilistId, type: MANGA) {
            id
            idMal
            title { romaji english native }
            synonyms
        }
    }
    """
    media = _request_anilist_manga(
        query,
        {"anilistId": anilist_id},
        f"AniList manga ID {anilist_id}",
        timeout,
        retries
    )

    if media.get("id") != anilist_id:
        raise MangaKatanaError(f"No manga was found for AniList ID {anilist_id}")

    mal_id = media.get("idMal")

    if not isinstance(mal_id, int) or mal_id <= 0:
        raise MangaKatanaError(
            f"AniList manga ID {anilist_id} is not linked to MyAnimeList"
        )

    return _build_manga_title_record(media)


class MangaKatanaScraper:
    def __init__(self, language: str = "en", timeout: float = 30.0, delay: float = 0.35, retries: int = 3) -> None:
        if not isinstance(language, str) or language.casefold() != "en":
            raise ValueError("MangaKatana only supports the 'en' language")

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        if delay < 0:
            raise ValueError("delay cannot be negative")

        if not isinstance(retries, int) or isinstance(retries, bool) or retries < 1:
            raise ValueError("retries must be a positive integer")

        self.language = "en"
        self.timeout = timeout
        self.delay = delay
        self.retries = retries
        self._session: Any = None
        self._last_request_at = 0.0
        self._last_title_search_at = 0.0

    def __enter__(self) -> "MangaKatanaScraper":
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def open(self) -> None:
        """Open the reusable HTTP session if it is not already open."""
        if self._session is None:
            self._session = curl_requests.Session(impersonate="chrome")

    def close(self) -> None:
        """Close the reusable HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at

        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _rate_limit_title_search(self) -> None:
        elapsed = time.monotonic() - self._last_title_search_at

        if elapsed < TITLE_SEARCH_DELAY:
            time.sleep(TITLE_SEARCH_DELAY - elapsed)

    def _get_html(self, path: str, params: dict[str, Any] | None = None) -> BeautifulSoup:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("path must be an absolute path without a host")

        self.open()
        last_error = "unknown error"

        for attempt in range(1, self.retries + 1):
            self._rate_limit()

            try:
                response = self._session.get(
                    f"{BASE_URL}{path}",
                    params=params,
                    headers={
                        "Accept": "text/html,application/xhtml+xml",
                        "Referer": f"{BASE_URL}/",
                    },
                    timeout=self.timeout,
                )
                self._last_request_at = time.monotonic()
            except Exception as error:
                last_error = str(error)
                response = None

            if response is not None and response.status_code == 200:
                return BeautifulSoup(response.text, "html.parser")

            if response is not None:
                status = response.status_code
                body = response.text[:300]
                last_error = f"HTTP {status}: {body}".strip()

                if status not in {408, 425, 429} and status < 500:
                    break

            if attempt < self.retries:
                time.sleep(min(2 ** (attempt - 1), 4))

        raise MangaKatanaError(f"Request failed for {path}: {last_error}")

    def _parse_title_record(self, soup: BeautifulSoup, title_id: str) -> dict[str, Any]:
        title_element = soup.select_one("#single_book h1.heading")

        if title_element is None:
            raise MangaKatanaError(f"MangaKatana title '{title_id}' was not found")

        title = title_element.get_text(" ", strip=True)
        alternate_element = soup.select_one("#single_book .alt_name")
        alternate_titles = (
            re.split(r"\s*;\s*", alternate_element.get_text(" ", strip=True))
            if alternate_element is not None
            else []
        )
        titles = []
        seen_titles = set()

        for candidate in [title, *alternate_titles]:
            normalized_candidate = _normalize_title(candidate)

            if normalized_candidate and normalized_candidate not in seen_titles:
                seen_titles.add(normalized_candidate)
                titles.append(candidate.strip())

        status_element = soup.select_one("#single_book .status")

        return {
            "id": title_id,
            "title": title,
            "titles": titles,
            "genres": [
                element.get_text(" ", strip=True)
                for element in soup.select("#single_book .genres a")
                if element.get_text(" ", strip=True)
            ],
            "status": (
                status_element.get_text(" ", strip=True)
                if status_element is not None
                else ""
            ),
        }

    def search_titles(self, search_query: str) -> list[dict[str, str]]:
        """Search MangaKatana and return unique title records."""
        if not isinstance(search_query, str) or not search_query.strip():
            raise ValueError("search_query is required")

        self._rate_limit_title_search()

        try:
            soup = self._get_html(
                "/",
                {
                    "search": search_query.strip(),
                    "search_by": "book_name",
                }
            )
        finally:
            self._last_title_search_at = time.monotonic()
        results = []
        seen_ids = set()

        for title_link in soup.select("#book_list .item h3.title > a[href]"):
            title_id = _parse_title_id(title_link.get("href", ""))
            title = title_link.get_text(" ", strip=True)

            if title_id is None or not title or title_id in seen_ids:
                continue

            seen_ids.add(title_id)
            results.append({
                "id": title_id,
                "title": title,
                "url": f"{BASE_URL}/manga/{title_id}",
            })

        if not results and soup.select_one("#single_book") is not None:
            canonical_link = soup.select_one('link[rel="canonical"][href]')
            title_id = (
                _parse_title_id(canonical_link.get("href", ""))
                if canonical_link is not None
                else None
            )

            if title_id is not None:
                detail = self._parse_title_record(soup, title_id)
                results.append({
                    "id": title_id,
                    "title": detail["title"],
                    "url": f"{BASE_URL}/manga/{title_id}",
                })

        return results

    def get_title(self, title_id: str) -> dict[str, Any]:
        """Fetch a MangaKatana title and its aliases."""
        if not isinstance(title_id, str) or not TITLE_ID_PATTERN.fullmatch(title_id):
            raise ValueError("title_id must be a valid MangaKatana title ID")

        soup = self._get_html(f"/manga/{title_id}")
        return self._parse_title_record(soup, title_id)

    def _resolve_title_record(self, manga_record: dict[str, Any]) -> str:
        canonical_titles = manga_record["titles"]
        normalized_titles = {
            _normalize_title(title) for title in canonical_titles
        }
        checked_ids = set()

        for search_title in canonical_titles[:12]:
            search_results = self.search_titles(search_title)
            search_results.sort(
                key=lambda item: _normalize_title(item["title"]) not in normalized_titles
            )

            for search_result in search_results:
                title_id = search_result["id"]

                if title_id in checked_ids:
                    continue

                checked_ids.add(title_id)
                detail = self.get_title(title_id)
                candidate_titles = {
                    _normalize_title(title) for title in detail["titles"]
                }

                if normalized_titles & candidate_titles:
                    return title_id

        raise MangaKatanaError(
            "MangaKatana does not have a title matching MAL manga ID "
            f"{manga_record['mal_id']}"
        )

    def resolve_titles(self, titles: list[str], mal_id: int | None = None) -> str:
        """Resolve known canonical titles without requiring an AniList lookup."""
        canonical_titles = []
        seen_titles = set()

        for title in titles:
            if not isinstance(title, str) or not title.strip():
                continue

            normalized_title = _normalize_title(title)

            if not normalized_title or normalized_title in seen_titles:
                continue

            seen_titles.add(normalized_title)
            canonical_titles.append(title.strip())

        if not canonical_titles:
            raise ValueError("titles must contain at least one non-empty title")

        return self._resolve_title_record({
            "mal_id": mal_id if mal_id is not None else "unknown",
            "titles": canonical_titles,
        })

    def resolve_mal_id(self, mal_id: int) -> str:
        """Resolve a MyAnimeList manga ID to a MangaKatana title ID."""
        manga_record = get_mal_manga_titles(
            mal_id,
            timeout=self.timeout,
            retries=self.retries
        )
        return self._resolve_title_record(manga_record)

    def resolve_anilist_id(self, anilist_id: int) -> str:
        """Resolve an AniList manga ID to a MangaKatana title ID."""
        manga_record = get_anilist_manga_titles(
            anilist_id,
            timeout=self.timeout,
            retries=self.retries
        )
        return self._resolve_title_record(manga_record)

    def get_chapters(self, title_id: str, chapter_type: str | None = None, page_size: int = 100) -> list[dict[str, Any]]:
        """Fetch unique non-negative MangaKatana chapters."""
        if not isinstance(page_size, int) or isinstance(page_size, bool) or not 1 <= page_size <= 200:
            raise ValueError("page_size must be between 1 and 200")

        if chapter_type not in {None, "official", "unofficial"}:
            raise ValueError("chapter_type must be 'official', 'unofficial', or None")

        if not isinstance(title_id, str) or not TITLE_ID_PATTERN.fullmatch(title_id):
            raise ValueError("title_id must be a valid MangaKatana title ID")

        soup = self._get_html(f"/manga/{title_id}")
        chapters = []

        for chapter_row in soup.select("#single_book .chapters tr"):
            chapter_link = chapter_row.select_one(".chapter a[href]")

            if chapter_link is None:
                continue

            parsed_chapter = _parse_chapter_path(chapter_link.get("href", ""))

            if parsed_chapter is None or parsed_chapter[0] != title_id:
                continue

            _, chapter_number, chapter_id = parsed_chapter
            chapter_label = chapter_link.get_text(" ", strip=True)
            chapter_name = re.sub(
                rf"^Chapter\s+{re.escape(chapter_number)}\s*:?[ ]*",
                "",
                chapter_label,
                count=1,
                flags=re.IGNORECASE
            ).strip()
            date_element = chapter_row.select_one(".update_time")
            released_at = (
                _parse_release_date(date_element.get_text(" ", strip=True))
                if date_element is not None
                else None
            )
            chapters.append({
                "id": chapter_id,
                "number": chapter_number,
                "name": chapter_name,
                "language": self.language,
                "type": "official",
                "created_at": released_at,
            })

        if soup.select_one("#single_book") is None:
            raise MangaKatanaError("MangaKatana returned an invalid chapter list")

        return _deduplicate_chapters(chapters)

    def get_chapter_pages(self, chapter_id: str) -> dict[str, Any]:
        """Fetch a chapter's ordered image-page records."""
        if not isinstance(chapter_id, str):
            raise ValueError("chapter_id must be a valid MangaKatana chapter ID")

        parsed_chapter = _parse_chapter_path(
            f"{BASE_URL}/manga/{chapter_id.lstrip('/')}"
        )

        if parsed_chapter is None or parsed_chapter[2] != chapter_id:
            raise ValueError("chapter_id must be a valid MangaKatana chapter ID")

        _, chapter_number, normalized_chapter_id = parsed_chapter
        soup = self._get_html(f"/manga/{normalized_chapter_id}")
        image_urls = _parse_script_array(soup, "thzq")
        dimensions = _parse_script_array(soup, "cds")
        image_urls = [url for url in image_urls if isinstance(url, str) and url]

        if not image_urls:
            raise MangaKatanaError(
                f"MangaKatana chapter '{chapter_id}' did not contain page images"
            )

        pages = []

        for page_number, image_url in enumerate(image_urls, start=1):
            width = None
            height = None

            if page_number <= len(dimensions):
                dimension_match = re.fullmatch(
                    r"(\d+)x(\d+)",
                    str(dimensions[page_number - 1]).strip()
                )

                if dimension_match is not None:
                    width = int(dimension_match.group(1))
                    height = int(dimension_match.group(2))

            pages.append({
                "page": page_number,
                "url": image_url,
                "width": width,
                "height": height,
            })

        return {
            "id": normalized_chapter_id,
            "number": chapter_number,
            "name": "",
            "language": self.language,
            "type": "official",
            "pages": pages,
            "image_urls": image_urls,
        }

    def get_available_chapter_count(self, mal_id: int) -> int:
        """Return the number of unique chapters available in English."""
        title_id = self.resolve_mal_id(_validate_mal_id(mal_id))
        return len(self.get_chapters(title_id))

    def get_available_chapter_count_by_anilist_id(self, anilist_id: int) -> int:
        """Return the number of chapters available for an AniList manga ID."""
        title_id = self.resolve_anilist_id(_validate_anilist_id(anilist_id))
        return len(self.get_chapters(title_id))

    def _get_chapter_images_by_title_id(self, title_id: str, chapter_number: int | float | str) -> list[str]:
        requested_number = _main_chapter_number_key(chapter_number)

        if requested_number is None:
            raise ValueError("chapter_number must be a non-negative number")

        chapter = next(
            (
                item
                for item in self.get_chapters(title_id)
                if _main_chapter_number_key(item.get("number")) == requested_number
            ),
            None,
        )

        if chapter is None:
            raise MangaKatanaError(
                f"Chapter {chapter_number} is not available in English"
            )

        return self.get_chapter_pages(chapter["id"])["image_urls"]

    def get_chapter_images_by_mal_id(self, mal_id: int, chapter_number: int | float | str) -> list[str]:
        """Return image URLs for one chapter selected by MAL manga ID."""
        title_id = self.resolve_mal_id(_validate_mal_id(mal_id))
        return self._get_chapter_images_by_title_id(title_id, chapter_number)

    def get_chapter_images_by_anilist_id(self, anilist_id: int, chapter_number: int | float | str) -> list[str]:
        """Return image URLs for one chapter using an AniList manga ID."""
        title_id = self.resolve_anilist_id(_validate_anilist_id(anilist_id))
        return self._get_chapter_images_by_title_id(title_id, chapter_number)

    def _scrape_title_id(self, title_id: str, include_images: bool = True, max_chapters: int | None = None, chapter_type: str | None = None, continue_on_error: bool = True) -> dict[str, Any]:
        if max_chapters is not None and (
            not isinstance(max_chapters, int)
            or isinstance(max_chapters, bool)
            or max_chapters < 1
        ):
            raise ValueError("max_chapters must be a positive integer or None")

        chapters = self.get_chapters(title_id, chapter_type=chapter_type)
        total_chapter_count = len(chapters)

        if max_chapters is not None:
            chapters = chapters[:max_chapters]

        for chapter in chapters:
            chapter["pages"] = []
            chapter["image_urls"] = []

            if not include_images:
                continue

            try:
                page_data = self.get_chapter_pages(chapter["id"])
                chapter["pages"] = page_data["pages"]
                chapter["image_urls"] = page_data["image_urls"]
            except MangaKatanaError as error:
                if not continue_on_error:
                    raise

                chapter["error"] = str(error)

        return {
            "mangakatana_id": title_id,
            "language": self.language,
            "chapter_count": len(chapters),
            "total_chapter_count": total_chapter_count,
            "image_request_headers": {"Referer": f"{BASE_URL}/"},
            "chapters": chapters,
        }

    def scrape_mal_id(self, mal_id: int, include_images: bool = True, max_chapters: int | None = None, chapter_type: str | None = None, continue_on_error: bool = True) -> dict[str, Any]:
        """Resolve a MAL manga ID and fetch its chapters and page images."""
        mal_id = _validate_mal_id(mal_id)
        title_id = self.resolve_mal_id(mal_id)
        return {
            "mal_id": mal_id,
            **self._scrape_title_id(
                title_id,
                include_images=include_images,
                max_chapters=max_chapters,
                chapter_type=chapter_type,
                continue_on_error=continue_on_error
            ),
        }

    def scrape_anilist_id(self, anilist_id: int, include_images: bool = True, max_chapters: int | None = None, chapter_type: str | None = None, continue_on_error: bool = True) -> dict[str, Any]:
        """Resolve an AniList manga ID and fetch its chapters and page images."""
        manga_record = get_anilist_manga_titles(
            _validate_anilist_id(anilist_id),
            timeout=self.timeout,
            retries=self.retries
        )
        title_id = self._resolve_title_record(manga_record)
        return {
            "mal_id": manga_record["mal_id"],
            "anilist_id": anilist_id,
            **self._scrape_title_id(
                title_id,
                include_images=include_images,
                max_chapters=max_chapters,
                chapter_type=chapter_type,
                continue_on_error=continue_on_error
            ),
        }


def get_chapter_images(mal_id: int, chapter_number: int | float | str, timeout: float = 30.0, delay: float = 0.35, retries: int = 3) -> list[str]:
    """Return English image URLs for one MAL manga chapter."""
    with MangaKatanaScraper(
        language="en",
        timeout=timeout,
        delay=delay,
        retries=retries
    ) as scraper:
        return scraper.get_chapter_images_by_mal_id(mal_id, chapter_number)


def get_available_chapter_count(mal_id: int, timeout: float = 30.0, delay: float = 0.35, retries: int = 3) -> int:
    """Return the number of unique English chapters for one MAL manga."""
    with MangaKatanaScraper(
        language="en",
        timeout=timeout,
        delay=delay,
        retries=retries
    ) as scraper:
        return scraper.get_available_chapter_count(mal_id)


def get_chapter_images_by_anilist_id(anilist_id: int, chapter_number: int | float | str, timeout: float = 30.0, delay: float = 0.35, retries: int = 3) -> list[str]:
    """Return English image URLs for one chapter using an AniList ID."""
    with MangaKatanaScraper(
        language="en",
        timeout=timeout,
        delay=delay,
        retries=retries
    ) as scraper:
        return scraper.get_chapter_images_by_anilist_id(anilist_id, chapter_number)


def get_available_chapter_count_by_anilist_id(anilist_id: int, timeout: float = 30.0, delay: float = 0.35, retries: int = 3) -> int:
    """Return the number of English chapters for one AniList manga."""
    with MangaKatanaScraper(
        language="en",
        timeout=timeout,
        delay=delay,
        retries=retries
    ) as scraper:
        return scraper.get_available_chapter_count_by_anilist_id(anilist_id)


def scrape_manga_by_mal_id(mal_id: int, include_images: bool = True, max_chapters: int | None = None, timeout: float = 30.0, delay: float = 0.35, retries: int = 3) -> dict[str, Any]:
    """Scrape English MangaKatana chapters using a MyAnimeList manga ID."""
    with MangaKatanaScraper(
        language="en",
        timeout=timeout,
        delay=delay,
        retries=retries
    ) as scraper:
        return scraper.scrape_mal_id(mal_id, include_images=include_images, max_chapters=max_chapters)


def scrape_manga_by_anilist_id(anilist_id: int, include_images: bool = True, max_chapters: int | None = None, timeout: float = 30.0, delay: float = 0.35, retries: int = 3) -> dict[str, Any]:
    """Scrape English MangaKatana chapters using an AniList manga ID."""
    with MangaKatanaScraper(
        language="en",
        timeout=timeout,
        delay=delay,
        retries=retries
    ) as scraper:
        return scraper.scrape_anilist_id(anilist_id, include_images=include_images, max_chapters=max_chapters)
