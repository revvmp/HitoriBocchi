from math import isfinite

import requests


ANISKIP_API_URL = "https://api.aniskip.com/v2/skip-times"
ANISKIP_SKIP_TYPES = ("op", "ed")
ANISKIP_TYPE_NAMES = {
    "op": "opening",
    "ed": "ending",
}


class AniSkipError(Exception):
    pass


def fetch_aniskip_skip_times(mal_id: int, episode_number: int, episode_length: float) -> list[dict]:
    """
    Fetches and normalizes AniSkip opening and ending intervals.
    """
    params = [("types[]", skip_type) for skip_type in ANISKIP_SKIP_TYPES]
    params.append(("episodeLength", round(episode_length, 3)))

    try:
        response = requests.get(
            f"{ANISKIP_API_URL}/{mal_id}/{episode_number}",
            params=params,
            headers={"User-Agent": "HitoriBocchi/1.0"},
            timeout=10
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise AniSkipError("AniSkip is currently unavailable") from e

    try:
        data = response.json()
    except ValueError as e:
        raise AniSkipError("AniSkip returned an invalid response") from e

    if not isinstance(data, dict):
        raise AniSkipError("AniSkip returned an invalid response")

    results = data.get("results")

    if not data.get("found") or not isinstance(results, list):
        return []

    skip_times = []

    for result in results:
        if not isinstance(result, dict):
            continue

        skip_type = ANISKIP_TYPE_NAMES.get(result.get("skipType"))
        interval = result.get("interval")

        if not skip_type or not isinstance(interval, dict):
            continue

        start_time = interval.get("startTime")
        end_time = interval.get("endTime")

        if (
            isinstance(start_time, bool)
            or isinstance(end_time, bool)
            or not isinstance(start_time, (int, float))
            or not isinstance(end_time, (int, float))
            or not isfinite(start_time)
            or not isfinite(end_time)
        ):
            continue

        start_time = max(0.0, min(float(start_time), episode_length))
        end_time = max(0.0, min(float(end_time), episode_length))

        if end_time <= start_time:
            continue

        skip_times.append({
            "skip_type": skip_type,
            "start_time": round(start_time, 3),
            "end_time": round(end_time, 3),
        })

    return sorted(
        skip_times,
        key=lambda skip_time: (
            skip_time["start_time"],
            skip_time["end_time"]
        )
    )
