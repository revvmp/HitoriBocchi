import re
from functools import lru_cache
from html import unescape
from time import monotonic
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests


ANIDB_BASE_URL = "https://anidb.app"
ANIDB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
ANIDB_PROVIDER_TIMEOUT_SECONDS = 7
ANIDB_REQUEST_TIMEOUT = ANIDB_PROVIDER_TIMEOUT_SECONDS

ANIME_PATH_PATTERN = re.compile(r"^/anime/(?P<slug>[a-z0-9-]+)-(?P<id>\d+)/?$", re.IGNORECASE)
MAL_URL_PATTERN = re.compile(r"https?://(?:www\.)?myanimelist\.net/anime/(?P<id>\d+)(?:[/?#]|$)", re.IGNORECASE)
HLS_FILE_PATTERN = re.compile(r"[\"']?file[\"']?\s*:\s*['\"](?P<url>https://[^'\"]+\.m3u8(?:\?[^'\"]*)?)['\"]", re.IGNORECASE)
HLS_RESOLUTION_PATTERN = re.compile(r"\bRESOLUTION=\d+x(?P<height>\d+)\b", re.IGNORECASE)
LANGUAGE_CODES = {
    "sub": "jpn",
    "dub": "eng",
}


class AniDBScraperError(RuntimeError):
    pass


class AniDBClient:
    def __init__(self, deadline: float | None = None):
        self.deadline = deadline
        self.session = curl_requests.Session(impersonate="chrome136")

    def close(self):
        self.session.close()

    def _get(self, url: str, referer: str | None = None, accept: str | None = None):
        _validate_anidb_url(url)
        headers = dict(ANIDB_HEADERS)
        request_timeout = ANIDB_REQUEST_TIMEOUT

        if self.deadline is not None:
            remaining_seconds = self.deadline - monotonic()

            if remaining_seconds <= 0:
                raise AniDBScraperError("AniDB request timed out")

            request_timeout = min(request_timeout, remaining_seconds)

        if referer:
            headers["Referer"] = referer

        if accept:
            headers["Accept"] = accept

        try:
            response = self.session.get(
                url,
                headers=headers,
                timeout=request_timeout,
                allow_redirects=True
            )
        except Exception as e:
            if self.deadline is not None and monotonic() >= self.deadline:
                raise AniDBScraperError("AniDB request timed out") from e

            raise AniDBScraperError("Unable to reach AniDB") from e

        _validate_anidb_url(str(response.url))

        if response.status_code != 200:
            raise AniDBScraperError(f"AniDB returned HTTP {response.status_code}")

        if "just a moment" in response.text[:5000].lower():
            raise AniDBScraperError("AniDB blocked the request with a browser challenge")

        return response

    def get_text(self, url: str, referer: str | None = None, accept: str | None = None) -> str:
        return self._get(url, referer=referer, accept=accept).text

    def get_json(self, url: str, referer: str | None = None) -> dict:
        response = self._get(url, referer=referer, accept="application/json")

        try:
            data = response.json()
        except Exception as e:
            raise AniDBScraperError("AniDB returned an invalid JSON response") from e

        if not isinstance(data, dict):
            raise AniDBScraperError("AniDB returned an invalid JSON response")

        return data

    def search(self, title: str) -> list:
        response = self._get(
            f"{ANIDB_BASE_URL}/browse?{urlencode({'q': title})}"
        )

        expected_title = _normalize_title(title)
        results = []
        seen_ids = set()
        soup = BeautifulSoup(response.text, "html.parser")

        for anchor in soup.find_all("a", href=True):
            result_url = urljoin(ANIDB_BASE_URL, anchor["href"])
            parsed_url = urlsplit(result_url)
            match = ANIME_PATH_PATTERN.fullmatch(parsed_url.path)

            if match is None or (parsed_url.hostname or "").lower() != "anidb.app":
                continue

            anime_id = int(match.group("id"))

            if anime_id in seen_ids:
                continue

            image = anchor.find("img")
            result_title = image.get("alt", "") if image else ""
            result_title = unescape(result_title).strip() or anchor.get_text(" ", strip=True)
            seen_ids.add(anime_id)
            results.append({
                "id": anime_id,
                "is_exact_title": _normalize_title(result_title) == expected_title,
                "title": result_title,
                "url": result_url,
            })

        return sorted(results, key=lambda result: not result["is_exact_title"])

    def get_episodes(self, anime_id: int, referer: str) -> list:
        data = self.get_json(
            f"{ANIDB_BASE_URL}/api/frontend/anime/{anime_id}/episodes",
            referer=referer
        )
        episodes = data.get("episodes", [])
        return episodes if isinstance(episodes, list) else []

    def get_languages(self, episode_id: int, referer: str) -> list:
        data = self.get_json(
            f"{ANIDB_BASE_URL}/api/frontend/episode/{episode_id}/languages",
            referer=referer
        )
        languages = data.get("languages", [])
        return languages if isinstance(languages, list) else []


def _validate_anidb_url(url: str) -> str:
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise AniDBScraperError("AniDB returned an invalid URL")

    parsed_url = urlsplit(url)
    hostname = (parsed_url.hostname or "").lower().rstrip(".")

    if parsed_url.scheme != "https" or not hostname:
        raise AniDBScraperError("AniDB returned an invalid URL")

    if hostname != "anidb.app" and not hostname.endswith(".anidb.app"):
        raise AniDBScraperError("AniDB returned an unexpected media host")

    return url


def _normalize_title(title: str) -> str:
    if not isinstance(title, str):
        return ""

    return re.sub(r"[^a-z0-9]+", " ", unescape(title).casefold()).strip()


def _get_mal_id(page: str) -> int | None:
    match = MAL_URL_PATTERN.search(page)
    return int(match.group("id")) if match else None


def _get_standard_episode_number(value) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, float):
        return int(value) if value > 0 and value.is_integer() else None

    if not isinstance(value, str):
        return None

    normalized_value = value.strip()

    if re.fullmatch(r"\d+(?:\.0+)?", normalized_value) is None:
        return None

    episode_number = int(normalized_value.split(".", 1)[0])
    return episode_number if episode_number > 0 else None


def _find_episode(episodes: list, episode_number: int) -> dict:
    numbered_episodes = []

    for episode in episodes:
        if not isinstance(episode, dict):
            continue

        provider_episode_number = _get_standard_episode_number(
            episode.get("number")
        )

        if provider_episode_number is not None:
            numbered_episodes.append((provider_episode_number, episode))

    if numbered_episodes:
        first_provider_episode = min(
            provider_episode_number
            for provider_episode_number, _ in numbered_episodes
        )
        # AniDB can number sequel inventories cumulatively across the series.
        target_provider_episode = (
            episode_number
            if first_provider_episode == 1
            else first_provider_episode + episode_number - 1
        )

        for provider_episode_number, episode in numbered_episodes:
            if provider_episode_number == target_provider_episode:
                return episode

    raise ValueError(f"AniDB does not have episode {episode_number}")


def _get_available_categories(languages: list) -> list:
    available_codes = {
        str(language.get("code", "")).strip().lower()
        for language in languages
        if isinstance(language, dict)
    }
    return [
        category for category, language_code in LANGUAGE_CODES.items()
        if language_code in available_codes
    ]


def _get_embed_url(languages: list, category: str) -> str:
    language_code = LANGUAGE_CODES[category]

    for language in languages:
        if not isinstance(language, dict):
            continue

        if str(language.get("code", "")).strip().lower() != language_code:
            continue

        embed_url = language.get("embed_url")

        if embed_url:
            return _validate_anidb_url(embed_url)

    raise ValueError(f"AniDB does not have a {category} stream for this episode")


def _get_master_url(embed_page: str) -> str:
    match = HLS_FILE_PATTERN.search(unescape(embed_page).replace("\\/", "/"))

    if match is None:
        raise ValueError("AniDB did not provide an HLS stream")

    return _validate_anidb_url(match.group("url"))


def _get_hls_variants(master_playlist: str, master_url: str) -> list:
    variants = []
    pending_height = None

    for line in master_playlist.splitlines():
        stripped_line = line.strip()

        if stripped_line.startswith("#EXT-X-STREAM-INF:"):
            resolution_match = HLS_RESOLUTION_PATTERN.search(stripped_line)
            pending_height = int(resolution_match.group("height")) if resolution_match else 0
            continue

        if pending_height is None or not stripped_line or stripped_line.startswith("#"):
            continue

        variant_url = _validate_anidb_url(urljoin(master_url, stripped_line))
        variants.append({
            "height": pending_height,
            "url": variant_url,
        })
        pending_height = None

    return variants


def _select_stream_url(master_url: str, master_playlist: str, quality: str | None) -> str:
    variants = _get_hls_variants(master_playlist, master_url)

    if not variants:
        return master_url

    if quality:
        normalized_quality = quality.strip().lower().removesuffix("p")
        selected_variant = next(
            (
                variant for variant in variants
                if str(variant["height"]) == normalized_quality
            ),
            None
        )

        if selected_variant is None:
            raise ValueError(f"AniDB does not have a {quality} stream for this episode")

        return selected_variant["url"]

    preferred_variant = next(
        (variant for variant in variants if variant["height"] == 1080),
        None
    )
    return (preferred_variant or variants[0])["url"]


@lru_cache(maxsize=512)
def _resolve_anime(mal_id: int, titles: tuple) -> tuple:
    client = AniDBClient(
        deadline=monotonic() + ANIDB_PROVIDER_TIMEOUT_SECONDS
    )
    seen_ids = set()

    try:
        for title in titles:
            if not _normalize_title(title):
                continue

            for candidate in client.search(title):
                if candidate["id"] in seen_ids:
                    continue

                seen_ids.add(candidate["id"])
                detail_page = client.get_text(candidate["url"], referer=ANIDB_BASE_URL)

                if _get_mal_id(detail_page) == mal_id:
                    return candidate["id"], candidate["url"]

        raise ValueError("Anime was not found on AniDB")
    finally:
        client.close()


def _get_episode_languages(mal_id: int, titles: tuple, episode_number: int, deadline: float) -> tuple:
    anime_id, anime_url = _resolve_anime(mal_id, titles)
    client = AniDBClient(deadline=deadline)

    try:
        episode = _find_episode(client.get_episodes(anime_id, anime_url), episode_number)
        episode_id = episode.get("id")

        if not isinstance(episode_id, int) or isinstance(episode_id, bool) or episode_id <= 0:
            raise ValueError(f"AniDB episode {episode_number} does not have a valid id")

        return anime_url, client.get_languages(episode_id, anime_url)
    finally:
        client.close()


def get_anidb_episode_availability(mal_id: int, titles: tuple, episode_number: int) -> list:
    _validate_inputs(mal_id, titles, episode_number)
    deadline = monotonic() + ANIDB_PROVIDER_TIMEOUT_SECONDS
    _, languages = _get_episode_languages(mal_id, titles, episode_number, deadline)
    return _get_available_categories(languages)


def get_anidb_episode_stream(mal_id: int, titles: tuple, episode_number: int, category: str = "sub", quality: str | None = None) -> dict:
    _validate_inputs(mal_id, titles, episode_number)

    if category not in LANGUAGE_CODES:
        raise ValueError("category must be sub or dub")

    deadline = monotonic() + ANIDB_PROVIDER_TIMEOUT_SECONDS
    anime_url, languages = _get_episode_languages(mal_id, titles, episode_number, deadline)
    available_categories = _get_available_categories(languages)
    embed_url = _get_embed_url(languages, category)
    client = AniDBClient(deadline=deadline)

    try:
        embed_page = client.get_text(embed_url, referer=anime_url)
        master_url = _get_master_url(embed_page)
        master_playlist = client.get_text(
            master_url,
            referer=embed_url,
            accept="application/vnd.apple.mpegurl,application/x-mpegURL,*/*"
        )
        stream_url = _select_stream_url(master_url, master_playlist, quality)
    finally:
        client.close()

    return {
        "available_categories": {"anidb": available_categories},
        "referer": embed_url,
        "type": "hls",
        "url": stream_url,
    }


def _validate_inputs(mal_id: int, titles: tuple, episode_number: int) -> None:
    if not isinstance(mal_id, int) or isinstance(mal_id, bool) or mal_id <= 0:
        raise ValueError("mal_id must be a positive integer")

    if not isinstance(titles, tuple) or not any(_normalize_title(title) for title in titles):
        raise ValueError("At least one anime title is required")

    if not isinstance(episode_number, int) or isinstance(episode_number, bool) or episode_number <= 0:
        raise ValueError("episode_number must be a positive integer")


def run_anidb_episode_availability(mal_id: int, titles: tuple, episode_number: int) -> list:
    return get_anidb_episode_availability(mal_id, titles, episode_number)


def run_anidb_episode_stream(mal_id: int, titles: tuple, episode_number: int, category: str = "sub", quality: str | None = None) -> dict:
    return get_anidb_episode_stream(
        mal_id=mal_id,
        titles=titles,
        episode_number=episode_number,
        category=category,
        quality=quality
    )
