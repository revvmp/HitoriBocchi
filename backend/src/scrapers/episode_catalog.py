import asyncio
import os
from time import monotonic

import httpx

from database.database import AnimeDatabase
from scrapers.providers import additional, anikoto, common, miruro


HEADERS = {"Referer": anikoto.BASE + "/", "Accept": "application/json"}
SUPPORTED_STREAM_PROVIDERS = ("anikoto",)
STREAM_PROVIDER_TIMEOUT_SECONDS = 7
EPISODE_INVENTORY_TIMEOUT_SECONDS = 30


def _use_miruro() -> bool:
    backend = os.environ.get("EPISODE_SCRAPER_BACKEND", "miruro").strip().lower()

    if backend not in {"anikoto", "miruro"}:
        raise ValueError("EPISODE_SCRAPER_BACKEND must be anikoto or miruro")

    return backend == "miruro"


def _validate_request(anilist_id: int, category: str = "sub", provider: str | None = None, episode_number: int | None = None):
    if not isinstance(anilist_id, int) or isinstance(anilist_id, bool) or anilist_id <= 0:
        raise ValueError("anilist_id must be a positive integer")

    if category not in {"sub", "dub"}:
        raise ValueError("category must be sub or dub")

    if provider not in {None, "anikoto"}:
        raise ValueError("Only provider='anikoto' is supported by the Anikoto episode scraper")

    if episode_number is not None and (not isinstance(episode_number, int) or isinstance(episode_number, bool) or episode_number <= 0):
        raise ValueError("episode_number must be a positive integer")


def _anime_metadata(anilist_id: int, deadline: float) -> dict:
    # Scheduled imports already have MAL titles; avoid a GraphQL call per anime.
    with AnimeDatabase() as db:
        anime = db.fetch_anime_by_anilist_id(anilist_id)

    if anime is not None:
        titles = tuple(dict.fromkeys(title.strip() for title in (anime.title_english, anime.title) if isinstance(title, str) and title.strip()))
        return {"mal_id": anime.id, "anilist_id": anilist_id, "titles": titles}

    remaining = deadline - monotonic()

    if remaining <= 0:
        raise RuntimeError("Anikoto metadata request timed out")

    query = "query ($id: Int!) { Media(id: $id, type: ANIME) { id idMal title { english romaji } } }"

    with httpx.Client(timeout=remaining) as client:
        response = client.post("https://graphql.anilist.co", json={"query": query, "variables": {"id": anilist_id}})

    if response.status_code != 200:
        raise RuntimeError(f"AniList metadata returned HTTP {response.status_code}: {response.text[:200]}")

    payload = response.json()
    media = (payload.get("data") or {}).get("Media") if not payload.get("errors") else None

    if not isinstance(media, dict) or media.get("id") != anilist_id or not isinstance(media.get("idMal"), int) or isinstance(media["idMal"], bool) or media["idMal"] <= 0:
        raise ValueError("AniList did not return a matching anime with a MAL ID")

    titles = tuple(dict.fromkeys(title.strip() for title in (media.get("title") or {}).values() if isinstance(title, str) and title.strip()))

    if not titles:
        raise ValueError("Anime title metadata is unavailable")

    return {"mal_id": media["idMal"], "anilist_id": anilist_id, "titles": titles}


def requires_anilist_id() -> bool:
    return _use_miruro()


def _get_rows(anilist_id: int | None, anime: dict | None = None) -> dict:
    client = common.Client("anikoto")
    client.deadline = monotonic() + EPISODE_INVENTORY_TIMEOUT_SECONDS

    try:
        if anime is None:
            anime = _anime_metadata(anilist_id, client.deadline)
        # Always fetch a fresh inventory for synchronization, not the playback cache.
        return anikoto.episode_rows(client, anime)
    finally:
        client.close()


def _format_episodes(rows: dict, category: str) -> list:
    episodes = [{"episode_number": number, "title": row["title"] or "Untitled"} for number, row in sorted(rows.items()) if category in row["versions"]]

    if not episodes:
        raise ValueError(f"No matching {category} episodes found on Anikoto")

    return episodes


async def get_catalog_episodes(anime, category: str = "sub", provider: str | None = None) -> list:
    """Use the selected backend; the Anikoto override accepts stored MAL metadata."""
    if _use_miruro():
        return await get_anime_episodes(anime.anilist_id, category, provider)

    _validate_request(anime.id, category, provider)
    titles = tuple(dict.fromkeys(title.strip() for title in (anime.title_english, anime.title) if isinstance(title, str) and title.strip()))
    metadata = {"mal_id": anime.id, "anilist_id": anime.anilist_id, "titles": titles}
    rows = await asyncio.to_thread(_get_rows, anime.anilist_id, metadata)
    return _format_episodes(rows, category)


async def get_anime_episodes(anilist_id: int, category: str = "sub", provider: str | None = None) -> list:
    """Return fresh episode numbers and titles from the selected sync backend."""
    if _use_miruro():
        return await miruro.get_anime_episodes(anilist_id, category, provider)

    _validate_request(anilist_id, category, provider)
    rows = await asyncio.to_thread(_get_rows, anilist_id)
    return _format_episodes(rows, category)


def _stream_operation(anilist_id: int, episode_number: int, category: str | None = None, quality: str | None = None):
    deadline = monotonic() + STREAM_PROVIDER_TIMEOUT_SECONDS
    anime = _anime_metadata(anilist_id, deadline)

    if category is None:
        categories = additional.availability("anikoto", anime, episode_number, deadline=deadline)
        return {"anikoto": categories} if categories else {}

    result = additional.stream("anikoto", anime, episode_number, category, quality, deadline=deadline)
    return {**result, "type": "hls"}


async def get_episode_stream_availability(anilist_id: int, episode_number: int) -> dict:
    if _use_miruro():
        return await miruro.get_episode_stream_availability(anilist_id, episode_number)

    if episode_number is None:
        raise ValueError("episode_number must be a positive integer")

    _validate_request(anilist_id, episode_number=episode_number)
    return await asyncio.to_thread(_stream_operation, anilist_id, episode_number)


async def get_episode_stream(anilist_id: int, episode_number: int, category: str = "sub", provider: str | None = None, quality: str | None = None) -> dict:
    if _use_miruro():
        return await miruro.get_episode_stream(anilist_id, episode_number, category, provider, quality)

    if episode_number is None:
        raise ValueError("episode_number must be a positive integer")

    if quality is not None and not isinstance(quality, str):
        raise ValueError("quality must be a string")

    _validate_request(anilist_id, category, provider, episode_number)
    return await asyncio.to_thread(_stream_operation, anilist_id, episode_number, category, quality)


def run_episode_stream_availability(anilist_id: int, episode_number: int) -> dict:
    if _use_miruro():
        return miruro.run_episode_stream_availability(anilist_id, episode_number)

    return asyncio.run(get_episode_stream_availability(anilist_id, episode_number))


def run_episode_stream(anilist_id: int, episode_number: int, category: str = "sub", provider: str | None = None, quality: str | None = None) -> dict:
    if _use_miruro():
        return miruro.run_episode_stream(anilist_id, episode_number, category, provider, quality)

    return asyncio.run(get_episode_stream(anilist_id, episode_number, category, provider, quality))
