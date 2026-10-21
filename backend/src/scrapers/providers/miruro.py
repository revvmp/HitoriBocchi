import asyncio
import json
import gzip
import io
import re
from datetime import date, datetime, timezone
from time import monotonic
from urllib.parse import urljoin, urlsplit
from curl_cffi.requests import AsyncSession
from streaming import subtitles
from utils.logger import get_logger

# --- Constants ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Referer": "https://www.miruro.tv/",
    "Origin": "https://www.miruro.tv",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "sec-ch-ua": '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
MIRURO_API_URL = "https://www.miruro.tv/api/v1"
MAX_CATALOG_SIZE = 4 * 1024 * 1024
PREFERRED_STREAM_QUALITIES = {"1080", "1080p", "fhd", "fullhd"}
SUPPORTED_STREAM_PROVIDERS = ("animepahe", "kickassanime", "aniwaves")
STREAM_PROVIDER_TIMEOUT_SECONDS = 7
logger = get_logger(__name__)


class PartialEpisodeInventoryError(RuntimeError):
    def __init__(self, episodes: list, failures: list):
        self.episodes = episodes
        self.failures = failures
        super().__init__(f"Miruro could not check {len(failures)} episodes; first failure: {failures[0]['error']}")


class MiruroClient:
    def __init__(self):
        self.session = AsyncSession(impersonate="chrome136", timeout=STREAM_PROVIDER_TIMEOUT_SECONDS)
        self.anime = {}
        self.playback = {}
        self.catalog_sync = False
        self.deadline = monotonic() + STREAM_PROVIDER_TIMEOUT_SECONDS

    async def close(self):
        await self.session.close()

    async def _request(self, path: str, params: dict | None = None) -> dict:
        response = await self.session.get(f"{MIRURO_API_URL}/{path}", params=params, headers=HEADERS)

        # Only catalog jobs retry here; interactive playback keeps its deadline.
        if self.catalog_sync and response.status_code in {502, 503, 504}:
            logger.warning(f"Miruro HTTP {response.status_code} for {path}; retrying once")
            await asyncio.sleep(1)
            response = await self.session.get(f"{MIRURO_API_URL}/{path}", params=params, headers=HEADERS)

        if response.status_code != 200:
            raise RuntimeError(f"Miruro HTTP {response.status_code} for {path}: {response.text[:300]}")

        try:
            if response.headers.get("Content-Type", "").split(";", 1)[0] == "application/octet-stream":
                key = b"miruro/catalog"
                compressed = bytes(value ^ key[index % len(key)] for index, value in enumerate(response.content))

                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as body:
                    decoded = body.read(MAX_CATALOG_SIZE + 1)

                if len(decoded) > MAX_CATALOG_SIZE:
                    raise ValueError("Catalog response is too large")

                data = json.loads(decoded)
            else:
                data = response.json()
        except (ValueError, OSError, EOFError) as error:
            raise RuntimeError(f"Miruro returned an invalid catalog response for {path}") from error

        if not isinstance(data, dict):
            raise RuntimeError(f"Miruro returned an invalid catalog object for {path}")

        return data

    async def _resolve(self, anilist_id: int) -> dict:
        if anilist_id not in self.anime:
            # Miruro only accepts the browser's lookup limit, and now uses opaque IDs.
            data = await self._request("anime", {"anilist_id_in": str(anilist_id), "limit": 100})
            matches = {
                item["id"]: item for item in data.get("data", [])
                if str(anilist_id) in item.get("external_ids", {}).get("anilist", [])
                and re.fullmatch(r"[A-Za-z0-9_-]{32}", str(item.get("id", "")))
            }

            if len(matches) != 1 or data.get("has_more"):
                raise ValueError(f"Miruro has no unambiguous catalog match for AniList ID {anilist_id}")

            self.anime[anilist_id] = next(iter(matches.values()))

        return self.anime[anilist_id]

    async def get_episode_inventory(self, anilist_id: int, episode_number: int) -> dict:
        anime = await self._resolve(anilist_id)
        data = await self._request(f"anime/{anime['id']}/episodes/{episode_number}/play")

        if data.get("episode_number") != episode_number or not isinstance(data.get("tracks"), list):
            raise RuntimeError("Miruro returned an invalid episode playback response")

        providers = {}

        for track in data["tracks"]:
            version = track.get("track")

            if version not in {"sub", "ssub", "dub"}:
                continue

            category = "dub" if version == "dub" else "sub"

            for provider in track.get("providers", []):
                name = provider.get("provider")

                if name not in SUPPORTED_STREAM_PROVIDERS:
                    continue

                streams = [
                    dict(stream, type="hls", referer=next((value for key, value in server.get("headers", {}).items() if key.lower() == "referer"), HEADERS["Referer"]))
                    for server in provider.get("servers", [])
                    for stream in server.get("streams", [])
                    if stream.get("format") == "hls" and stream.get("url")
                ]

                if not streams:
                    continue

                key = (anilist_id, episode_number, name, category)

                # Prefer full soft subtitles when both sub variants are available.
                if key not in self.playback or version == "ssub":
                    self.playback[key] = {"streams": streams, "subtitles": provider.get("subtitles", [])}

                episodes = providers.setdefault(name, {"episodes": {}})["episodes"]
                episodes[category] = [{"id": str(episode_number), "number": episode_number}]

        return {"providers": providers}

    async def get_catalog_episodes(self, anilist_id: int, category: str = "sub") -> list:
        """Fetch the released episode catalog in bulk without extracting playback."""
        if category not in {"sub", "dub"}:
            raise ValueError("category must be sub or dub")

        self.catalog_sync = True
        anime = await self._resolve(anilist_id)
        count = (anime.get("episode_counts") or {}).get(category)

        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(f"Miruro has no confirmed {category} episode count")

        if count == 0:
            raise ValueError(f"No {category} episodes found on Miruro")

        data = await self._request(f"anime/{anime['id']}/episodes", {"limit": 10000})

        if not isinstance(data.get("data"), list) or data.get("has_more"):
            raise RuntimeError("Miruro returned an incomplete episode catalog")

        kind = "film" if anime.get("format") == "MOVIE" else "regular"
        today = datetime.now(timezone.utc).date()
        episodes = {}

        for row in data["data"]:
            number = row.get("episode_number")

            if row.get("kind", kind) != kind or not isinstance(number, int) or isinstance(number, bool) or not 0 < number <= count:
                continue

            aired_on = row.get("aired_on")

            if isinstance(aired_on, str):
                try:
                    if date.fromisoformat(aired_on) > today:
                        continue
                except ValueError:
                    pass

            episodes[number] = {"episode_number": number, "title": row.get("title") or "Untitled"}

        if not episodes:
            raise ValueError(f"No released {category} episodes found on Miruro")

        return [episodes[number] for number in sorted(episodes)]

    async def get_episodes(self, anilist_id: int) -> dict:
        self.catalog_sync = True
        anime = await self._resolve(anilist_id)
        kind = "film" if anime.get("format") == "MOVIE" else "regular"
        # The current catalog rejects kind filters; match the browser query.
        data = await self._request(f"anime/{anime['id']}/episodes", {"limit": 10000})

        if not isinstance(data.get("data"), list) or data.get("has_more"):
            raise RuntimeError("Miruro returned an incomplete episode catalog")

        providers = {}
        failures = []
        semaphore = asyncio.Semaphore(3)

        async def inventory(row):
            if row.get("kind", kind) != kind:
                return

            aired_on = row.get("aired_on")

            if isinstance(aired_on, str):
                try:
                    if date.fromisoformat(aired_on) > datetime.now(timezone.utc).date():
                        return
                except ValueError:
                    pass

            number = row.get("episode_number")

            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                return

            async with semaphore:
                try:
                    available = await self.get_episode_inventory(anilist_id, number)
                except Exception as error:
                    failures.append({"episode_number": number, "error": str(error)})
                    return

            for name, provider in available["providers"].items():
                episodes = providers.setdefault(name, {"episodes": {}})["episodes"]

                for category in provider["episodes"]:
                    episodes.setdefault(category, []).append({"id": str(number), "number": number, "title": row.get("title")})

        # Catalog metadata alone does not prove a provider stores the episode.
        await asyncio.gather(*(inventory(row) for row in data["data"]))

        for provider in providers.values():
            for episodes in provider["episodes"].values():
                episodes.sort(key=lambda episode: episode["number"])

        result = {"providers": providers}

        if failures:
            result["failures"] = sorted(failures, key=lambda failure: failure["episode_number"])

        return result

    async def get_streaming_link(self, episode_id: str, provider: str, anilist_id: int, category: str = "sub") -> dict:
        key = (anilist_id, int(episode_id), provider, category)

        if key not in self.playback:
            await self.get_episode_inventory(anilist_id, int(episode_id))

        if key not in self.playback:
            raise ValueError("Miruro has no HLS stream for the requested episode and version")

        return self.playback[key]

    async def validate_stream(self, stream: dict, category: str, quality: str | None) -> None:
        from streaming import miruro_proxy

        url = stream["url"]
        referer = stream.get("referer") or HEADERS["Referer"]
        origin = urlsplit(referer)

        for depth in range(3):
            miruro_proxy.validate_stream_url(url)
            response = await self.session.get(url, headers={"Referer": referer, "Origin": f"{origin.scheme}://{origin.netloc}"}, allow_redirects=False)

            if response.status_code != 200 or not response.text.lstrip().startswith("#EXTM3U"):
                raise RuntimeError(f"Miruro media returned HTTP {response.status_code} or an invalid HLS playlist")

            lines = miruro_proxy._select_hls_renditions(response.text, category, quality)

            if not any(line.startswith("#EXT-X-STREAM-INF:") for line in lines):
                return

            child = next((line for line in lines if line and not line.startswith("#")), None)

            if not child:
                raise RuntimeError("Miruro returned no matching HLS variant")

            url = urljoin(url, child)

        raise RuntimeError("Miruro returned too many nested playlists")

    async def validate_subtitle(self, url: str, referer: str) -> str | None:
        from streaming import miruro_proxy

        remaining = self.deadline - monotonic() - 0.1

        if remaining <= 0:
            return None

        try:
            miruro_proxy.validate_stream_url(url)
            response = await self.session.get(url, headers={"Referer": referer}, timeout=remaining, allow_redirects=False)

            if response.status_code != 200 or len(response.content) > miruro_proxy.STREAM_PROXY_MAX_SUBTITLE_SIZE:
                raise ValueError(f"Subtitle HTTP {response.status_code} or oversized response")

            subtitles.convert_to_webvtt(response.content)
            return url
        except Exception as error:
            # Optional captions must not turn playable video into a server failure.
            logger.warning("Miruro subtitle unavailable on %s: %s", urlsplit(url).hostname, error)
            return None


def _select_provider_episodes(episodes_data: dict, category: str, provider: str | None) -> tuple:
    providers = episodes_data.get("providers", {})

    if not providers:
        raise ValueError("No streaming providers found")

    if provider:
        provider_data = providers.get(provider)
        if provider_data is None:
            raise ValueError(f"Streaming provider '{provider}' is not available")

        episodes = provider_data.get("episodes", {}).get(category, [])
        if not episodes:
            raise ValueError(f"No {category} episodes found for provider '{provider}'")

        return provider, episodes

    provider_names = list(providers.keys())
    if "pewe" in providers:
        provider_names.remove("pewe")
        provider_names.insert(0, "pewe")

    for provider_name in provider_names:
        episodes = providers[provider_name].get("episodes", {}).get(category, [])
        if episodes:
            return provider_name, episodes

    raise ValueError(f"No {category} episodes found")


def _merge_supported_provider_episodes(episodes_data: dict, category: str) -> list:
    providers = episodes_data.get("providers", {})

    if not providers:
        raise ValueError("No streaming providers found")

    merged_episodes = {}

    for provider_name in SUPPORTED_STREAM_PROVIDERS:
        provider_data = providers.get(provider_name)

        if provider_data is None:
            continue

        episodes = provider_data.get("episodes", {}).get(category, [])

        for episode in episodes:
            episode_number = episode.get("number")

            if episode_number is None:
                continue

            episode_key = str(episode_number).strip()

            if not episode_key or episode_key in merged_episodes:
                continue

            merged_episodes[episode_key] = episode

    if not merged_episodes:
        raise ValueError(f"No {category} episodes found for supported streaming providers")

    return list(merged_episodes.values())


def _get_available_categories_by_provider(episodes_data: dict, episode_number: int) -> dict:
    available_categories = {}

    for provider, provider_data in episodes_data.get("providers", {}).items():
        provider_episodes = provider_data.get("episodes", {})
        categories = [
            category for category in ("sub", "dub")
            if any(
                str(episode.get("number")) == str(episode_number)
                for episode in provider_episodes.get(category, [])
            )
        ]

        if categories:
            available_categories[provider] = categories

    return available_categories


async def _get_episode_inventory(client: MiruroClient, anilist_id: int, episode_number: int, category: str | None = None, provider: str | None = None) -> dict:
    return await client.get_episode_inventory(anilist_id, episode_number)


def _select_stream(streams: list, quality: str | None = None) -> dict:
    if not streams:
        raise ValueError("No stream URLs found for this episode")

    hls_streams = [
        stream for stream in streams
        if str(stream.get("type", "")).lower() == "hls"
    ]

    if not hls_streams:
        raise ValueError("No HLS stream URLs found for this episode")

    if quality:
        normalized_quality = quality.lower().removesuffix("p")
        selected_stream = next(
            (
                stream for stream in hls_streams
                if str(stream.get("quality", "")).lower().removesuffix("p") == normalized_quality
            ),
            None
        )

        if selected_stream is None:
            selected_stream = next(
                (
                    stream for stream in hls_streams
                    if str(stream.get("quality") or "").lower() in {"", "auto", "default"}
                ),
                None
            )

        if selected_stream is None:
            raise ValueError(f"Stream quality '{quality}' is not available")

        return selected_stream

    selected_stream = next(
        (
            stream for stream in hls_streams
            if str(stream.get("quality", "")).lower().replace(" ", "") in PREFERRED_STREAM_QUALITIES
        ),
        None
    )

    if selected_stream is not None:
        return selected_stream

    return next(
        (
            stream for stream in hls_streams
            if str(stream.get("quality") or "").lower() in {"", "auto", "default"}
        ),
        hls_streams[0]
    )


async def get_anime_episodes(anilist_id: int, category: str = "sub", provider: str | None = None) -> list:
    """
    Fetches episode numbers and titles for an anime using its AniList ID.
    Uses the bulk released catalog unless one specific provider is requested.
    """
    if not isinstance(anilist_id, int) or isinstance(anilist_id, bool) or anilist_id <= 0:
        raise ValueError("anilist_id must be a positive integer")

    client = MiruroClient()

    try:
        if provider is None:
            return await client.get_catalog_episodes(anilist_id, category)

        episodes_data = await client.get_episodes(anilist_id)

        failures = episodes_data.get("failures", [])

        try:
            if provider:
                _, episodes = _select_provider_episodes(episodes_data, category, provider)
            else:
                episodes = _merge_supported_provider_episodes(episodes_data, category)
        except ValueError:
            if failures:
                raise PartialEpisodeInventoryError([], failures)
            raise

        result = [
            {
                "episode_number": episode.get("number"),
                "title": episode.get("title") or "Untitled",
            }
            for episode in episodes
        ]

        if failures:
            raise PartialEpisodeInventoryError(result, failures)

        return result

    finally:
        await client.close()


async def get_episode_stream_availability(anilist_id: int, episode_number: int) -> dict:
    if not isinstance(anilist_id, int) or isinstance(anilist_id, bool) or anilist_id <= 0:
        raise ValueError("anilist_id must be a positive integer")

    if not isinstance(episode_number, int) or isinstance(episode_number, bool) or episode_number <= 0:
        raise ValueError("episode_number must be a positive integer")

    client = MiruroClient()

    try:
        episodes_data = await _get_episode_inventory(client, anilist_id, episode_number)
        available_categories = _get_available_categories_by_provider(episodes_data, episode_number)
        return {
            provider: available_categories[provider]
            for provider in SUPPORTED_STREAM_PROVIDERS
            if provider in available_categories
        }
    finally:
        await client.close()


async def get_episode_stream(anilist_id: int, episode_number: int, category: str = "sub", provider: str | None = None, quality: str | None = None) -> dict:
    """
    Fetches one stream and its required request information using an AniList ID and episode number.
    Prefers a 1080p stream, then an automatic/default stream, unless a quality is requested.
    """
    if not isinstance(anilist_id, int) or isinstance(anilist_id, bool) or anilist_id <= 0:
        raise ValueError("anilist_id must be a positive integer")

    if not isinstance(episode_number, int) or isinstance(episode_number, bool) or episode_number <= 0:
        raise ValueError("episode_number must be a positive integer")

    if quality is not None and not isinstance(quality, str):
        raise ValueError("quality must be a string")

    client = MiruroClient()

    try:
        episodes_data = await _get_episode_inventory(client, anilist_id, episode_number, category, provider)
        available_categories = _get_available_categories_by_provider(episodes_data, episode_number)

        if provider is None:
            provider = next(
                (name for name in SUPPORTED_STREAM_PROVIDERS if category in available_categories.get(name, [])),
                None
            )

            if provider is None:
                raise ValueError(f"Episode {episode_number} was not found")

        selected_provider, episodes = _select_provider_episodes(episodes_data, category, provider)
        episode = next(
            (
                episode for episode in episodes
                if str(episode.get("number")) == str(episode_number)
            ),
            None
        )

        if episode is None:
            raise ValueError(f"Episode {episode_number} was not found")

        episode_id = episode.get("id")
        if not episode_id:
            raise ValueError(f"Episode {episode_number} does not have a provider id")

        sources = await client.get_streaming_link(
            episode_id=episode_id,
            provider=selected_provider,
            anilist_id=anilist_id,
            category=category
        )
        streams = [stream for stream in sources.get("streams", []) if stream.get("url")]
        selected_stream = _select_stream(streams, quality)
        subtitle = next(
            (
                subtitle for subtitle in sources.get("subtitles", [])
                if subtitle.get("file")
                and str(subtitle.get("language", "")).lower() in {"en", "eng", "en-us", "en-gb"}
                and str(subtitle.get("format", "")).lower() in {"vtt", "srt", "ass"}
                and not re.search(r"\b(?:signs?|songs?|dubtitles?)\b", str(subtitle.get("label", "")), re.IGNORECASE)
            ),
            None
        ) if category == "sub" else None
        referer = selected_stream.get("referer") or HEADERS["Referer"]
        if subtitle:
            _, subtitle_url = await asyncio.gather(
                client.validate_stream(selected_stream, category, quality),
                client.validate_subtitle(subtitle["file"], referer),
            )
        else:
            await client.validate_stream(selected_stream, category, quality)
            subtitle_url = None

        return {
            "available_categories": available_categories,
            "url": selected_stream["url"],
            "referer": referer,
            "type": selected_stream.get("type", ""),
            "quality": selected_stream.get("quality"),
            "subtitle_url": subtitle_url,
        }

    finally:
        await client.close()


def run_episode_stream_availability(anilist_id: int, episode_number: int) -> dict:
    try:
        return asyncio.run(
            asyncio.wait_for(
                get_episode_stream_availability(
                    anilist_id=anilist_id,
                    episode_number=episode_number
                ),
                timeout=STREAM_PROVIDER_TIMEOUT_SECONDS
            )
        )
    except asyncio.TimeoutError as e:
        raise RuntimeError(
            f"Streaming provider inventory did not respond within {STREAM_PROVIDER_TIMEOUT_SECONDS} seconds"
        ) from e


def run_episode_stream(anilist_id: int, episode_number: int, category: str = "sub", provider: str | None = None, quality: str | None = None) -> dict:
    try:
        return asyncio.run(
            asyncio.wait_for(
                get_episode_stream(
                    anilist_id=anilist_id,
                    episode_number=episode_number,
                    category=category,
                    provider=provider,
                    quality=quality
                ),
                timeout=STREAM_PROVIDER_TIMEOUT_SECONDS
            )
        )
    except asyncio.TimeoutError as e:
        raise RuntimeError(
            f"Streaming provider did not respond within {STREAM_PROVIDER_TIMEOUT_SECONDS} seconds"
        ) from e
