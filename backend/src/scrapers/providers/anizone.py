import json
import re
import unicodedata
from collections import OrderedDict
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from functools import lru_cache
from html import unescape
from threading import Lock
from time import monotonic
from urllib.parse import urlencode, urlsplit

from curl_cffi import requests as curl_requests

from scrapers.metadata import anilist


ANIZONE_BASE_URL = "https://anizone.to"
ANIZONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
ANIZONE_PROVIDER_TIMEOUT_SECONDS = 7
ANIZONE_REQUEST_TIMEOUT = ANIZONE_PROVIDER_TIMEOUT_SECONDS
ANIZONE_MEDIA_CACHE_SECONDS = 10 * 60
ANIZONE_MEDIA_CACHE_SIZE = 512
ANIZONE_MEDIA_HOSTNAMES = {
    "vid-cdn.xyz",
    "xin-cdn.xyz",
}

ANIZONE_SLUG_PATTERN = re.compile(r"^[a-z0-9]+$", re.IGNORECASE)
SEASON_SUFFIX_PATTERN = re.compile(r"^(?P<base>.+) (?:season [1-9]\d*|[1-9]\d*(?:st|nd|rd|th)? season)$")
PART_MARKER_PATTERN = re.compile(r"\b(?:part|cour|bu)\b")
COUR_SUFFIX_PATTERN = re.compile(r"^(?P<base>.+?)(?: (?:season [1-9]\d*|[1-9]\d*(?:st|nd|rd|th)? season))? (?:part (?P<part>[1-9]\d*)|(?P<cour>[1-9]\d*)(?:st|nd|rd|th)? cour)$")
YEAR_ALIAS_SUFFIX_PATTERN = re.compile(r" \(\d{4}(?: [1-9]\d* Cour)?\)$")
SEARCH_ITEMS_PATTERN = re.compile(r"items:\s*JSON\.parse\('(?P<data>.*?)'\)", re.DOTALL)
EMPTY_SEARCH_ITEMS_PATTERN = re.compile(r'''\bx-data\s*=\s*["']\s*\{\s*items:\s*\[\s*\]\s*,''')
PLAYER_DATA_PATTERN = re.compile(r"vidstackPlayer\(JSON\.parse\('(?P<data>.*?)'\)\)", re.DOTALL)
HLS_AUDIO_TYPE_PATTERN = re.compile(r"(?:^|[:,])TYPE=AUDIO(?:,|$)", re.IGNORECASE)
HLS_LANGUAGE_PATTERN = re.compile(r'(?:^|,)LANGUAGE=(?:"(?P<quoted>[^"]+)"|(?P<plain>[^,]+))', re.IGNORECASE)
HLS_RESOLUTION_PATTERN = re.compile(r"\bRESOLUTION=\d+x(?P<height>\d+)\b", re.IGNORECASE)
AUDIO_CATEGORIES = {
    "ja": "sub",
    "en": "dub",
}

_episode_media_cache = OrderedDict()
_episode_media_cache_lock = Lock()
_episode_requests = {}
_episode_requests_lock = Lock()


class AniZoneScraperError(RuntimeError):
    pass


class AniZoneNotFoundError(AniZoneScraperError):
    pass


class AniZoneClient:
    def __init__(self, deadline: float | None = None):
        self.deadline = deadline
        self.session = curl_requests.Session(impersonate="chrome136")

    def close(self):
        self.session.close()

    def _get(self, url: str, validator, referer: str | None = None, accept: str | None = None):
        validator(url)
        headers = dict(ANIZONE_HEADERS)
        request_timeout = ANIZONE_REQUEST_TIMEOUT

        if self.deadline is not None:
            remaining_seconds = self.deadline - monotonic()

            if remaining_seconds <= 0:
                raise AniZoneScraperError("AniZone request timed out")

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
                allow_redirects=False
            )
        except Exception as e:
            if self.deadline is not None and monotonic() >= self.deadline:
                raise AniZoneScraperError("AniZone request timed out") from e

            raise AniZoneScraperError(f"Unable to reach AniZone ({urlsplit(url).hostname}): {e}") from e

        if 300 <= response.status_code < 400:
            raise AniZoneScraperError("AniZone returned an unexpected redirect")

        validator(str(response.url))

        if response.status_code == 404:
            raise AniZoneNotFoundError("AniZone page was not found")

        if response.status_code != 200:
            raise AniZoneScraperError(f"AniZone returned HTTP {response.status_code} for {urlsplit(url).path}: {response.text[:120]}")

        if "just a moment" in response.text[:5000].lower():
            raise AniZoneScraperError("AniZone blocked the request with a browser challenge")

        return response

    def get_page_text(self, url: str, referer: str | None = None) -> str:
        return self._get(url, _validate_anizone_page_url, referer=referer).text

    def get_media_text(self, url: str, referer: str) -> str:
        return self._get(
            url,
            _validate_anizone_media_url,
            referer=referer,
            accept="application/vnd.apple.mpegurl,application/x-mpegURL,*/*"
        ).text

    def search(self, title: str) -> list:
        page = self.get_page_text(
            f"{ANIZONE_BASE_URL}/anime?{urlencode({'search': title})}",
            referer=ANIZONE_BASE_URL
        )
        return _get_search_items(page)


def _validate_url(url: str, hostnames: set, label: str) -> str:
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise AniZoneScraperError(f"AniZone returned an invalid {label}")

    try:
        parsed_url = urlsplit(url)
        port = parsed_url.port
    except ValueError as e:
        raise AniZoneScraperError(f"AniZone returned an invalid {label}") from e

    actual_hostname = (parsed_url.hostname or "").lower().rstrip(".")

    if parsed_url.scheme != "https" or not actual_hostname or port not in {None, 443}:
        raise AniZoneScraperError(f"AniZone returned an invalid {label}")

    if parsed_url.username or parsed_url.password:
        raise AniZoneScraperError(f"AniZone returned an invalid {label}")

    if not any(
        actual_hostname == hostname or actual_hostname.endswith(f".{hostname}")
        for hostname in hostnames
    ):
        raise AniZoneScraperError(f"AniZone returned an unexpected {label} host")

    return url


def _validate_anizone_page_url(url: str) -> str:
    return _validate_url(url, {"anizone.to"}, "page URL")


def _validate_anizone_media_url(url: str) -> str:
    return _validate_url(url, ANIZONE_MEDIA_HOSTNAMES, "media URL")


def _decode_json_parse_argument(value: str, label: str):
    try:
        decoded_value = json.loads(f'"{value}"')
        return json.loads(decoded_value)
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        raise AniZoneScraperError(f"AniZone returned invalid {label} data") from e


def _get_search_items(page: str) -> list:
    match = SEARCH_ITEMS_PATTERN.search(page)

    if match is None:
        if EMPTY_SEARCH_ITEMS_PATTERN.search(page):
            return []

        raise AniZoneScraperError("AniZone did not provide its anime index")

    items = _decode_json_parse_argument(match.group("data"), "anime index")
    return items if isinstance(items, list) else []


def _get_player_data(page: str) -> dict:
    match = PLAYER_DATA_PATTERN.search(page)

    if match is None:
        raise ValueError("AniZone did not provide an HLS stream for this episode")

    data = _decode_json_parse_argument(match.group("data"), "player")

    if not isinstance(data, dict):
        raise AniZoneScraperError("AniZone returned invalid player data")

    return data


def _normalize_title(title: str) -> str:
    if not isinstance(title, str):
        return ""

    normalized_title = unicodedata.normalize("NFKD", unescape(title))
    # Fold Latin accents (Fiancé/Fiance) without stripping Japanese voicing marks.
    normalized_title = "".join(char for index, char in enumerate(normalized_title) if not (unicodedata.combining(char) and index and normalized_title[index - 1].isascii()))
    normalized_title = unicodedata.normalize("NFKC", normalized_title).casefold()
    normalized_title = re.sub(r"[\W_]+", " ", normalized_title).strip()
    normalized_title = re.sub(r"\bdai ([1-9]\d*) ki\b", r"season \1", normalized_title)
    return re.sub(r"\b([1-9]\d*)(?:st|nd|rd|th) season\b", r"season \1", normalized_title)


def _normalize_episode_count(value) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, float):
        return int(value) if value > 0 and value.is_integer() else None

    if not isinstance(value, str):
        return None

    normalized_value = value.strip()

    if not normalized_value.isdigit():
        return None

    episode_count = int(normalized_value)
    return episode_count if episode_count > 0 else None


def _get_candidate_titles(candidate: dict) -> set:
    titles = {_normalize_title(candidate.get("main_title"))}
    title_list = candidate.get("title_list")

    if isinstance(title_list, dict):
        titles.update(_normalize_title(title) for title in title_list.values())

    return {title for title in titles if title}


def _score_candidate(candidate: dict, expected_titles: set, expected_episode_count: int | None) -> int | None:
    slug = candidate.get("slug")

    if not isinstance(slug, str) or ANIZONE_SLUG_PATTERN.fullmatch(slug) is None:
        return None

    candidate_titles = _get_candidate_titles(candidate)

    if not candidate_titles.intersection(expected_titles):
        return None

    score = 100
    candidate_episode_count = _normalize_episode_count(candidate.get("episode_count"))

    if expected_episode_count is not None and candidate_episode_count == expected_episode_count:
        score += 20

    if _normalize_title(candidate.get("main_title")) in expected_titles:
        score += 10

    return score


def _select_anime_candidate(candidates: list, expected_titles: set, expected_episode_count: int | None) -> str | None:
    scored_candidates = {}

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        score = _score_candidate(candidate, expected_titles, expected_episode_count)

        if score is not None:
            slug = candidate["slug"].lower()
            scored_candidates[slug] = max(score, scored_candidates.get(slug, 0))

    if not scored_candidates:
        return None

    highest_score = max(scored_candidates.values())
    best_slugs = [slug for slug, score in scored_candidates.items() if score == highest_score]

    if len(best_slugs) > 1:
        raise ValueError("Anime match is ambiguous on AniZone")

    return best_slugs[0]


def _get_metadata_titles(metadata: dict) -> tuple:
    titles = metadata.get("title")

    if not isinstance(titles, dict):
        return ()

    return tuple(dict.fromkeys(title for title in (titles.get("native"), titles.get("english"), titles.get("romaji")) if _normalize_title(title)))


def _get_year_titles(metadata: dict) -> tuple:
    start_date = metadata.get("startDate")
    year = start_date.get("year") if isinstance(start_date, dict) else None

    # AniZone lists both TV and ONA seasons as TV Series.
    if metadata.get("format") not in {"TV", "ONA"} or not isinstance(year, int) or isinstance(year, bool) or not 1900 <= year <= 2100:
        return ()

    titles = tuple(_normalize_title(title) for title in _get_metadata_titles(metadata))
    aliases = []

    if any(PART_MARKER_PATTERN.search(title) for title in titles):
        # Later cours keep their cour number in the year alias, e.g. "Title (2026 2 Cour)".
        for normalized_title in titles:
            match = COUR_SUFFIX_PATTERN.fullmatch(normalized_title)

            if match is not None:
                aliases.append(f"{match.group('base')} ({year} {match.group('part') or match.group('cour')} Cour)")

        return tuple(dict.fromkeys(aliases))

    for normalized_title in titles:
        match = SEASON_SUFFIX_PATTERN.fullmatch(normalized_title)

        if match is not None:
            aliases.append(f"{match.group('base')} ({year})")

    return tuple(dict.fromkeys(aliases))


def _select_metadata_candidate(candidates: list, metadata: dict, expected_episode_count: int | None) -> str | None:
    expected_titles = {_normalize_title(title) for title in _get_metadata_titles(metadata)}
    slug = _select_anime_candidate(candidates, expected_titles, expected_episode_count)

    if slug:
        return slug

    year_titles = {_normalize_title(title) for title in _get_year_titles(metadata)}

    if not year_titles:
        return None

    year_candidates = [
        candidate for candidate in candidates
        if isinstance(candidate, dict)
        and candidate.get("start_year") == metadata["startDate"]["year"]
        and candidate.get("type") == "TV Series"
    ]
    # Episode counts cannot disambiguate seasons that share a release year.
    matching_slugs = {
        candidate["slug"].lower() for candidate in year_candidates
        if _score_candidate(candidate, year_titles, None) is not None
    }

    if len(matching_slugs) > 1:
        raise ValueError("Anime match is ambiguous on AniZone")

    return next(iter(matching_slugs), None)


@lru_cache(maxsize=512)
def _resolve_anime(mal_id: int, titles: tuple, total_episodes) -> str:
    if not isinstance(mal_id, int) or isinstance(mal_id, bool) or mal_id <= 0:
        raise ValueError("mal_id must be a positive integer")

    expected_titles = {_normalize_title(title) for title in titles if _normalize_title(title)}
    expected_episode_count = _normalize_episode_count(total_episodes)
    client = AniZoneClient(deadline=monotonic() + ANIZONE_PROVIDER_TIMEOUT_SECONDS)
    candidates = []

    try:
        for title in dict.fromkeys(titles):
            if not _normalize_title(title):
                continue

            candidates.extend(client.search(title))
            slug = _select_anime_candidate(candidates, expected_titles, expected_episode_count)

            if slug:
                return slug

        # AniZone searches literal punctuation, even though matching normalizes it.
        searched_titles = set(expected_titles)

        for title in titles:
            search_title = re.split(r"[^\w\s]", title, maxsplit=1)[0]
            normalized_title = _normalize_title(search_title)

            if search_title == title or len(normalized_title) < 3 or normalized_title in searched_titles:
                continue

            searched_titles.add(normalized_title)
            candidates.extend(client.search(search_title.strip()))
            slug = _select_anime_candidate(candidates, expected_titles, expected_episode_count)

            if slug:
                return slug

        # A provider may index 'Dai N Ki' rather than an English season suffix.
        # Keep the complete normalized season identity when accepting results.
        for title in titles:
            season = SEASON_SUFFIX_PATTERN.fullmatch(_normalize_title(title))

            if season is None or season.group("base") in searched_titles:
                continue

            searched_titles.add(season.group("base"))
            candidates.extend(client.search(season.group("base")))
            slug = _select_anime_candidate(candidates, expected_titles, expected_episode_count)

            if slug:
                return slug

        remaining_seconds = client.deadline - monotonic()

        if remaining_seconds <= 0:
            raise AniZoneScraperError("AniZone request timed out")

        try:
            metadata = anilist.get_anime_title_metadata(mal_id, timeout=remaining_seconds)
        except anilist.AniListError as e:
            raise AniZoneScraperError(f"Unable to verify AniZone title match: {e}") from e

        if monotonic() >= client.deadline:
            raise AniZoneScraperError("AniZone request timed out")

        slug = _select_metadata_candidate(candidates, metadata, expected_episode_count)

        if slug:
            return slug

        year_titles = _get_year_titles(metadata)
        # Search can index only the main title, while verified aliases use a year.
        # Broaden the query only; matching still requires the full canonical alias.
        season_search_titles = tuple(YEAR_ALIAS_SUFFIX_PATTERN.sub("", title) for title in year_titles)

        for title in (*_get_metadata_titles(metadata), *season_search_titles, *year_titles):
            normalized_title = _normalize_title(title)

            if normalized_title in searched_titles:
                continue

            searched_titles.add(normalized_title)
            candidates.extend(client.search(title))
            slug = _select_metadata_candidate(candidates, metadata, expected_episode_count)

            if slug:
                return slug

        raise ValueError("Anime was not found on AniZone")
    finally:
        client.close()


def _normalize_audio_language(language: str) -> str | None:
    normalized_language = str(language).strip().lower()

    if normalized_language in {"ja", "jpn"}:
        return "ja"

    if normalized_language in {"en", "eng"}:
        return "en"

    return None


def _get_hls_audio_languages(master_playlist: str) -> tuple:
    languages = []

    for line in master_playlist.splitlines():
        stripped_line = line.strip()

        if not stripped_line.startswith("#EXT-X-MEDIA:") or HLS_AUDIO_TYPE_PATTERN.search(stripped_line) is None:
            continue

        language_match = HLS_LANGUAGE_PATTERN.search(stripped_line)

        if language_match is None:
            continue

        language = _normalize_audio_language(
            language_match.group("quoted") or language_match.group("plain")
        )

        if language and language not in languages:
            languages.append(language)

    return tuple(languages)


def _get_hls_qualities(master_playlist: str) -> tuple:
    qualities = []

    for line in master_playlist.splitlines():
        if not line.strip().startswith("#EXT-X-STREAM-INF:"):
            continue

        resolution_match = HLS_RESOLUTION_PATTERN.search(line)

        if resolution_match is None:
            continue

        quality = resolution_match.group("height")

        if quality not in qualities:
            qualities.append(quality)

    return tuple(qualities)


def _get_full_subtitle_url(player_data: dict) -> str | None:
    subtitles = player_data.get("subtitles")

    if not isinstance(subtitles, list):
        return None

    candidates = []

    for subtitle in subtitles:
        if not isinstance(subtitle, dict):
            continue

        language = str(subtitle.get("language", "")).strip().lower()
        forced = str(subtitle.get("forced", "")).strip().lower()
        subtitle_url = subtitle.get("file")

        if language not in {"en", "eng"} or forced in {"1", "true", "yes"}:
            continue

        try:
            subtitle_url = _validate_anizone_media_url(subtitle_url)
        except AniZoneScraperError:
            continue

        candidates.append((bool(subtitle.get("default")), subtitle_url))

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: not candidate[0])
    return candidates[0][1]


def _get_available_categories(audio_languages: tuple) -> list:
    return [
        category for language, category in AUDIO_CATEGORIES.items()
        if language in audio_languages
    ]


def _get_cached_episode_media(anime_slug: str, episode_number: int) -> dict | None:
    cache_key = (anime_slug, episode_number)

    with _episode_media_cache_lock:
        cached = _episode_media_cache.get(cache_key)

        if cached is None:
            return None

        expires_at, media = cached

        if expires_at <= monotonic():
            del _episode_media_cache[cache_key]
            return None

        _episode_media_cache.move_to_end(cache_key)
        return dict(media)


def _cache_episode_media(anime_slug: str, episode_number: int, media: dict) -> None:
    cache_key = (anime_slug, episode_number)

    with _episode_media_cache_lock:
        _episode_media_cache[cache_key] = (
            monotonic() + ANIZONE_MEDIA_CACHE_SECONDS,
            dict(media),
        )
        _episode_media_cache.move_to_end(cache_key)

        while len(_episode_media_cache) > ANIZONE_MEDIA_CACHE_SIZE:
            _episode_media_cache.popitem(last=False)


def _get_episode_media(anime_slug: str, episode_number: int, deadline: float) -> dict:
    cached_media = _get_cached_episode_media(anime_slug, episode_number)

    if cached_media is not None:
        return cached_media

    episode_url = f"{ANIZONE_BASE_URL}/anime/{anime_slug}/{episode_number}"
    client = AniZoneClient(deadline=deadline)

    try:
        try:
            episode_page = client.get_page_text(episode_url, referer=f"{ANIZONE_BASE_URL}/anime/{anime_slug}")
        except AniZoneNotFoundError as e:
            raise ValueError(f"AniZone does not have episode {episode_number}") from e

        player_data = _get_player_data(episode_page)
        master_url = _validate_anizone_media_url(player_data.get("src"))
        master_playlist = client.get_media_text(master_url, referer=episode_url)
    finally:
        client.close()

    media = {
        "audio_languages": _get_hls_audio_languages(master_playlist),
        "qualities": _get_hls_qualities(master_playlist),
        "referer": episode_url,
        "subtitle_url": _get_full_subtitle_url(player_data),
        "url": master_url,
    }

    if not media["audio_languages"]:
        raise ValueError("AniZone did not provide a supported audio track for this episode")

    _cache_episode_media(anime_slug, episode_number, media)
    return dict(media)


def _normalize_quality(quality: str | None) -> str | None:
    if quality is None:
        return None

    if not isinstance(quality, str):
        raise ValueError("quality must be a string")

    normalized_quality = quality.strip().lower().removesuffix("p")

    if not normalized_quality.isdigit():
        raise ValueError("quality must be a resolution such as 1080p")

    return normalized_quality


def _resolve_episode_media(mal_id: int, titles: tuple, total_episodes, episode_number: int) -> dict:
    deadline = monotonic() + ANIZONE_PROVIDER_TIMEOUT_SECONDS
    key = (mal_id, titles, total_episodes, episode_number)

    # Availability and playback arrive together; one upstream lookup serves both.
    with _episode_requests_lock:
        pending = _episode_requests.get(key)
        owner = pending is None
        if owner:
            pending = Future()
            _episode_requests[key] = pending

    if not owner:
        try:
            return dict(pending.result(timeout=max(0, deadline - monotonic())))
        except FutureTimeoutError as e:
            raise AniZoneScraperError("AniZone request timed out waiting for episode lookup") from e

    try:
        anime_slug = _resolve_anime(mal_id, titles, total_episodes)
        media = _get_episode_media(anime_slug, episode_number, deadline)
        pending.set_result(media)
        return dict(media)
    except Exception as e:
        pending.set_exception(e)
        raise
    finally:
        with _episode_requests_lock:
            del _episode_requests[key]


def get_anizone_episode_availability(mal_id: int, titles: tuple, total_episodes, episode_number: int) -> list:
    _validate_inputs(mal_id, titles, episode_number)
    media = _resolve_episode_media(mal_id, titles, total_episodes, episode_number)
    return _get_available_categories(media["audio_languages"])


def get_anizone_episode_stream(mal_id: int, titles: tuple, total_episodes, episode_number: int, category: str = "sub", quality: str | None = None) -> dict:
    _validate_inputs(mal_id, titles, episode_number)

    if category not in AUDIO_CATEGORIES.values():
        raise ValueError("category must be sub or dub")

    media = _resolve_episode_media(mal_id, titles, total_episodes, episode_number)
    available_categories = _get_available_categories(media["audio_languages"])

    if category not in available_categories:
        raise ValueError(f"AniZone does not have a {category} stream for this episode")

    requested_quality = _normalize_quality(quality)

    if requested_quality and requested_quality not in media["qualities"]:
        raise ValueError(f"AniZone does not have a {quality} stream for this episode")

    selected_quality = requested_quality

    if selected_quality is None and "1080" in media["qualities"]:
        selected_quality = "1080"

    audio_language = next(
        language for language, available_category in AUDIO_CATEGORIES.items()
        if available_category == category
    )

    return {
        "audio_language": audio_language,
        "available_categories": {"anizone": available_categories},
        "quality": selected_quality,
        "referer": media["referer"],
        "subtitle_url": media["subtitle_url"] if category == "sub" else None,
        "type": "hls",
        "url": media["url"],
    }


def _validate_inputs(mal_id: int, titles: tuple, episode_number: int) -> None:
    if not isinstance(mal_id, int) or isinstance(mal_id, bool) or mal_id <= 0:
        raise ValueError("mal_id must be a positive integer")

    if not isinstance(titles, tuple) or not any(_normalize_title(title) for title in titles):
        raise ValueError("At least one anime title is required")

    if not isinstance(episode_number, int) or isinstance(episode_number, bool) or episode_number <= 0:
        raise ValueError("episode_number must be a positive integer")


def run_anizone_episode_availability(mal_id: int, titles: tuple, total_episodes, episode_number: int) -> list:
    return get_anizone_episode_availability(mal_id, titles, total_episodes, episode_number)


def run_anizone_episode_stream(mal_id: int, titles: tuple, total_episodes, episode_number: int, category: str = "sub", quality: str | None = None) -> dict:
    return get_anizone_episode_stream(
        mal_id=mal_id,
        titles=titles,
        total_episodes=total_episodes,
        episode_number=episode_number,
        category=category,
        quality=quality
    )
