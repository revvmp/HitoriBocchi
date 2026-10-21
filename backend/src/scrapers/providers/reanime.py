from scrapers.providers import common, flixcloud
from streaming import additional_proxy


BASE = "https://reanime.to"


def resolve(client, anime):
    matches = {}
    unmapped = []

    for title in anime["titles"]:
        data = client.json(f"{BASE}/api/v1/search", params={"q": title, "limit": 10})

        for item in data.get("results", []):
            if str(item.get("anilist_id")) == str(anime["anilist_id"]):
                matches[item["anime_id"]] = item
            elif str(item.get("anilist_id")) == "0":
                titles = item.get("title", {})
                titles = list(titles.values()) if isinstance(titles, dict) else [titles]
                unmapped.append({"id": item["anime_id"], "titles": [title for title in titles if isinstance(title, str)]})

    if not matches:
        return common.exact_match(unmapped, anime["titles"])["id"]

    # Duplicate listings that all confirm the AniList ID are the same show;
    # playback uses the canonical AniList ID, so merge their inventories.
    return next(iter(matches)) if len(matches) == 1 else tuple(sorted(matches))


def inventory(client, anime):
    slugs = common.cached(("reanime-title", anime["anilist_id"], anime["titles"]), lambda: resolve(client, anime), 3600)
    episodes = {}

    for slug in (slugs,) if isinstance(slugs, str) else slugs:
        data = client.json(f"{BASE}/api/v1/anime/{slug}/episodes", params={"limit": 2000})

        for item in data.get("data", []):
            number = common.episode_number(item.get("episode_number"))

            if number and item.get("playable"):
                for category in ("sub", "dub"):
                    if item.get(category + "bed") is True:
                        episodes.setdefault(number, {}).setdefault(category, slug)

    return episodes


def _episode_servers(client, anime, number):
    def load():
        data = client.json(f"{BASE}/api/flix/{anime['anilist_id']}/{number}")
        if not isinstance(data, dict) or not isinstance(data.get("servers"), list):
            raise common.ProviderError("Re:Anime returned an invalid episode server list")

        servers = [server for server in data.get("servers", []) if isinstance(server, dict) and server.get("dataLink") and server.get("dataType") in {"sub", "s-sub", "dub", "s-dub"}]

        if not servers:
            raise common.EpisodeNotFoundError("Re:Anime has no servers for this episode")

        return servers

    return common.cached(("reanime-episode-servers", anime["anilist_id"], number), load, 300)


def episode_versions(client, anime, number):
    # The title was already resolved against its identity by inventory().
    # Jikan-backed episode lists can be empty even when this endpoint has media.
    try:
        servers = _episode_servers(client, anime, number)
    except common.EpisodeNotFoundError:
        return {}

    return {server["dataType"].removeprefix("s-"): True for server in servers}


def stream(client, anime, number, category, item):
    servers = [server for server in _episode_servers(client, anime, number) if server.get("dataType") in {category, "s-" + category}]
    servers.sort(key=lambda server: server.get("serverName") != "HD-2")
    errors = []
    attempted = set()

    for server in servers:
        if server["dataLink"] in attempted:
            continue

        attempted.add(server["dataLink"])

        try:
            result = flixcloud.extract(client, server["dataLink"])
            additional_proxy.validate_url("reanime", result["url"], discovered=True)

            if result.get("subtitle_url"):
                additional_proxy.validate_url("reanime", result["subtitle_url"], discovered=True)

            return result
        except Exception as e:
            errors.append(str(e))

    raise common.ProviderError("; ".join(errors) or "No Re:Anime stream for the requested version")
