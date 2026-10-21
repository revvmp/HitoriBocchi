from scrapers.providers import anibd, anikoto, anineko, common, reanime
from streaming import additional_proxy


PROVIDERS = {"reanime": reanime, "anibd": anibd, "anineko": anineko, "anikoto": anikoto}


def _inventory(client, anime):
    return common.cached((client.provider, "inventory", anime["mal_id"], anime["anilist_id"], anime["titles"]), lambda: PROVIDERS[client.provider].inventory(client, anime))


def _episode_versions(client, anime, episode_number, category=None):
    versions = _inventory(client, anime).get(episode_number, {})

    if client.provider == "reanime" and (not versions or category is not None and category not in versions):
        versions = {**versions, **reanime.episode_versions(client, anime, episode_number)}

    return versions


def availability(provider: str, anime: dict, episode_number: int, deadline: float | None = None) -> list:
    client = common.Client(provider)

    if deadline is not None:
        client.deadline = min(client.deadline, deadline)

    try:
        return list(_episode_versions(client, anime, episode_number))
    finally:
        client.close()


def stream(provider: str, anime: dict, episode_number: int, category: str, quality: str | None = None, deadline: float | None = None) -> dict:
    if provider not in PROVIDERS or category not in {"sub", "dub"} or quality not in {None, "1080p", "720p", "360p"}:
        raise common.ProviderError("Unsupported playback selection")

    client = common.Client(provider)

    if deadline is not None:
        client.deadline = min(client.deadline, deadline)

    try:
        versions = _episode_versions(client, anime, episode_number, category)

        if category not in versions:
            raise common.EpisodeNotFoundError("This server does not store the requested episode and version")

        def resolve():
            result = PROVIDERS[provider].stream(client, anime, episode_number, category, versions[category])
            additional_proxy.validate_url(provider, result["url"], discovered=True)
            additional_proxy.validate_url(provider, result["referer"], discovered=True)
            payload = {"provider": provider, "url": result["url"], "referer": result["referer"], "category": category, "quality": quality, "manifest_key": result.get("manifest_key")}

            # Validate the selected child playlist too, before reporting playback success.
            for depth in range(3):
                manifest = client.get(payload["url"], result["referer"], discovered=True).text
                rewritten = additional_proxy.rewrite_playlist(manifest, payload, "validation-only")

                if "#EXT-X-STREAM-INF:" not in rewritten:
                    break

                child = next(line for line in rewritten.splitlines() if line and not line.startswith("#"))
                payload = additional_proxy.decode_token("validation-only", child.split("/")[-2])
            else:
                raise common.ProviderError("Too many nested HLS playlists")

            if result.get("subtitle_url"):
                additional_proxy.validate_url(provider, result["subtitle_url"], discovered=True)

            return result

        result = dict(common.cached((provider, "stream", anime["mal_id"], episode_number, category, quality), resolve, 300))
        result["available_categories"] = {provider: list(versions)}
        return result
    finally:
        client.close()
