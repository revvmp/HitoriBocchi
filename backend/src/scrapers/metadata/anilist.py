import time

import httpx


ANILIST_URL = "https://graphql.anilist.co"
RETRYABLE_STATUS_CODES = {408, 425, 429}


class AniListError(RuntimeError):
    pass


def get_anime_title_metadata(mal_id: int, timeout: float) -> dict:
    """Fetches canonical titles and release metadata for provider title matching."""
    if not isinstance(mal_id, int) or isinstance(mal_id, bool) or mal_id <= 0:
        raise ValueError("mal_id must be a positive integer")

    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    query = """
    query ($malId: Int!) {
        Media(idMal: $malId, type: ANIME) {
            idMal
            title { english romaji native }
            startDate { year }
            format
        }
    }
    """

    try:
        with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
            response = client.post(ANILIST_URL, json={"query": query, "variables": {"malId": mal_id}})
    except httpx.RequestError as e:
        raise AniListError("Unable to fetch AniList title metadata") from e

    if response.status_code != 200:
        raise AniListError(f"AniList title metadata returned HTTP {response.status_code}: {_get_error_message(response)}")

    try:
        payload = response.json()
    except ValueError as e:
        raise AniListError("AniList returned invalid title metadata") from e

    data = payload.get("data") if isinstance(payload, dict) and not payload.get("errors") else None
    media = data.get("Media") if isinstance(data, dict) else None

    if not isinstance(media, dict) or media.get("idMal") != mal_id:
        raise AniListError(f"AniList title metadata did not match MAL ID {mal_id}")

    return media


def _get_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300].strip() or "unknown error"

    errors = payload.get("errors", []) if isinstance(payload, dict) else []

    if errors and isinstance(errors[0], dict):
        return errors[0].get("message", "unknown error")

    return response.text[:300].strip() or "unknown error"


def resolve_anilist_id(mal_id: int, timeout: float = 15.0, retries: int = 3) -> int:
    """Resolves a MyAnimeList anime ID to its AniList ID."""
    if not isinstance(mal_id, int) or isinstance(mal_id, bool) or mal_id <= 0:
        raise ValueError("mal_id must be a positive integer")

    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 1:
        raise ValueError("retries must be a positive integer")

    query = """
    query ($malId: Int!) {
        Media(idMal: $malId, type: ANIME) {
            id
        }
    }
    """
    last_error = "unknown error"

    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
        for attempt in range(1, retries + 1):
            try:
                response = client.post(
                    ANILIST_URL,
                    json={"query": query, "variables": {"malId": mal_id}}
                )
            except httpx.RequestError as error:
                last_error = str(error)
            else:
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except ValueError as error:
                        last_error = f"unexpected response: {error}"
                    else:
                        errors = payload.get("errors", []) if isinstance(payload, dict) else []

                        if errors:
                            last_error = errors[0].get(
                                "message",
                                "unknown GraphQL error"
                            )
                            break

                        data = payload.get("data") if isinstance(payload, dict) else None
                        media = data.get("Media") if isinstance(data, dict) else None

                        if isinstance(media, dict) and isinstance(media.get("id"), int):
                            return media["id"]

                        last_error = f"no anime matched MAL ID {mal_id}"
                        break
                else:
                    last_error = (
                        f"HTTP {response.status_code}: "
                        f"{_get_error_message(response)}"
                    )

                    if (response.status_code not in RETRYABLE_STATUS_CODES and response.status_code < 500):
                        break

            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 4))

    raise AniListError(
        f"Unable to resolve MAL ID {mal_id} through AniList "
        f"after {retries} attempts: {last_error}"
    )


def resolve_anilist_manga_id(mal_id: int, timeout: float = 15.0, retries: int = 3) -> int:
    """Resolves a MyAnimeList manga ID to its AniList ID."""
    if not isinstance(mal_id, int) or isinstance(mal_id, bool) or mal_id <= 0:
        raise ValueError("mal_id must be a positive integer")

    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 1:
        raise ValueError("retries must be a positive integer")

    query = """
    query ($malId: Int!) {
        Media(idMal: $malId, type: MANGA) {
            id
        }
    }
    """
    last_error = "unknown error"

    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
        for attempt in range(1, retries + 1):
            try:
                response = client.post(
                    ANILIST_URL,
                    json={"query": query, "variables": {"malId": mal_id}}
                )
            except httpx.RequestError as error:
                last_error = str(error)
            else:
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except ValueError as error:
                        last_error = f"unexpected response: {error}"
                    else:
                        errors = payload.get("errors", []) if isinstance(payload, dict) else []

                        if errors:
                            last_error = errors[0].get(
                                "message",
                                "unknown GraphQL error"
                            )
                            break

                        data = payload.get("data") if isinstance(payload, dict) else None
                        media = data.get("Media") if isinstance(data, dict) else None

                        if isinstance(media, dict) and isinstance(media.get("id"), int):
                            return media["id"]

                        last_error = f"no manga matched MAL ID {mal_id}"
                        break
                else:
                    last_error = (
                        f"HTTP {response.status_code}: "
                        f"{_get_error_message(response)}"
                    )

                    if (response.status_code not in RETRYABLE_STATUS_CODES and response.status_code < 500):
                        break

            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 4))

    raise AniListError(
        f"Unable to resolve manga MAL ID {mal_id} through AniList "
        f"after {retries} attempts: {last_error}"
    )
