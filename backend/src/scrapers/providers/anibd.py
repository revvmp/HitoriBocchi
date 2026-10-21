import json
import re
from urllib.parse import urljoin

from scrapers.providers import common
from streaming import additional_proxy


BASE = "https://epeng.animeapps.top"


def inventory(client, anime):
    groups = client.json(f"{BASE}/api2.php", params={"epid": anime["anilist_id"]})
    episodes = {}

    if not isinstance(groups, list):
        raise common.ProviderError("Anibd.app returned an invalid inventory")

    for group in groups:
        name = str(group.get("server_name", "")).lower()
        category = "dub" if "dub" in name else "sub" if "sub" in name else None

        if not category:
            continue

        for item in group.get("server_data", []):
            number = common.episode_number(item.get("name", item.get("slug")))
            link = item.get("link")

            if number and isinstance(link, str) and link:
                episodes.setdefault(number, {}).setdefault(category, []).append(link)

    return episodes


def _player_config(html):
    # Newer players publish a JSON PLAYER_CONFIG; older ones use object literals.
    config = re.search(r"PLAYER_CONFIG\s*=\s*(\{.*?\})\s*;\s*</script>", html, re.DOTALL)

    if config:
        data = json.loads(config[1])
        tracks = data.get("tracks")
        return data.get("videoUrl"), tracks if isinstance(tracks, list) else []

    match = re.search(r'videoUrl\s*:\s*"([^"\n]+)"', html)
    tracks_match = re.search(r"\btracks\s*:\s*(\[.*?\])", html, re.DOTALL)
    return match[1] if match else None, json.loads(tracks_match[1]) if tracks_match else []


def stream(client, anime, number, category, item):
    for link in item:
        for player in client.json(f"{BASE}/apilink.php", params={"data": link}):
            url = player.get("link")

            if not url:
                continue

            try:
                referer = common.origin(url)
                html = client.get(url, referer, discovered=True).text
                video_url, tracks = _player_config(html)

                if video_url:
                    # Older players can point at retired hosts; try the next player instead.
                    additional_proxy.validate_url("anibd", urljoin(url, video_url), discovered=True)
                    subtitle = common.english_subtitle(tracks)
                    return {"url": urljoin(url, video_url), "referer": referer, "subtitle_url": urljoin(url, subtitle) if subtitle else None}
            except ValueError:
                continue

    raise common.ProviderError("Anibd.app has no playable stream for this episode")
