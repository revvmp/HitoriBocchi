import base64
import json
import re
from urllib import parse

from bs4 import BeautifulSoup
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from scrapers.providers import common
from streaming import additional_proxy


BASE = "https://anikototv.to"


def _season_title(title):
    # Equivalent sequel labels still require unique episode MAL confirmation.
    title = re.sub(r"\s+(\d+)(?:st|nd|rd|th)\s+Season$", r" Season \1", title.strip(), flags=re.IGNORECASE)
    roman = re.search(r"\s+(II|III|IV|V|VI|VII|VIII|IX|X)$", title)

    if roman:
        numbers = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
        title = title[:roman.start()] + f" Season {numbers[roman[1]]}"

    return common.normalize_title(re.sub(r"\s+(?:season\s+)?([2-9]|[1-9]\d+)$", r" Season \1", title, flags=re.IGNORECASE))


def resolve(client, anime):
    candidates = []
    aliases = {common.normalize_title(title) for title in anime["titles"] if title}

    for title in anime["titles"]:
        soup = BeautifulSoup(client.get(f"{BASE}/filter", params={"keyword": title}).text, "html.parser")

        for link in soup.select("a.name.d-title[href]"):
            match = re.match(r"/watch/([a-z0-9-]+)(?:/|$)", parse.urlsplit(link["href"]).path)

            if match:
                candidates.append({"id": match[1], "titles": [link.get_text(strip=True), link.get("data-jp", "")]})

    matches = {item["id"]: item for item in candidates if aliases.intersection(common.normalize_title(title) for title in item["titles"] if title)}
    requires_mal_confirmation = len(matches) != 1

    if not matches:
        season_aliases = {_season_title(title) for title in anime["titles"] if title}
        matches = {item["id"]: item for item in candidates if season_aliases.intersection(_season_title(title) for title in item["titles"] if title)}

    if not matches:
        returned_titles = list(dict.fromkeys(title for item in candidates for title in item["titles"] if title))
        raise common.ProviderError(f"Anikoto found no exact title match for MAL ID {anime['mal_id']}; searched {anime['titles']!r}; returned {returned_titles[:6]!r}")

    if not requires_mal_confirmation:
        return _show_id(client, next(iter(matches)))

    # Duplicate listings and equivalent season labels require episode MAL identity.
    # Never resolve them by search order or episode count.
    confirmed = set()

    for slug in matches:
        show = _show_id(client, slug)
        soup = _episode_list(client, show)

        if any(common.episode_number(link["data-num"]) and str(link.get("data-mal")) == str(anime["mal_id"]) for link in soup.select("a[data-num][data-ids]")):
            confirmed.add(show)

    if len(confirmed) != 1:
        raise common.ProviderError(f"Anikoto found {len(matches)} matching title listings for MAL ID {anime['mal_id']}, but {len(confirmed)} inventories confirm that MAL ID; candidates {list(matches)!r}")

    return next(iter(confirmed))


def _show_id(client, slug):
    soup = BeautifulSoup(client.get(f"{BASE}/watch/{slug}").text, "html.parser")
    show = soup.select_one(".watch-wrap[data-id]")

    if not show or not str(show["data-id"]).isdigit():
        raise common.ProviderError("Anikoto show ID is missing")

    return show["data-id"]


def _episode_list(client, show):
    data = client.json(f"{BASE}/ajax/episode/list/{show}", BASE + "/")
    return BeautifulSoup(data.get("result", ""), "html.parser")


def inventory(client, anime):
    rows = episode_rows(client, anime)
    return {number: row["versions"] for number, row in rows.items()}


def episode_rows(client, anime):
    show = common.cached(("anikoto-title", anime["mal_id"], anime["titles"]), lambda: resolve(client, anime), 3600)
    soup = _episode_list(client, show)
    episodes = {}

    for link in soup.select("a[data-num][data-ids]"):
        number = common.episode_number(link["data-num"])

        # Every episode must independently confirm the requested MAL season.
        if not number or str(link.get("data-mal")) != str(anime["mal_id"]):
            continue

        title = link.select_one(".d-title")
        episodes[number] = {
            "title": title.get_text(" ", strip=True) if title else f"Episode {number}",
            "versions": {category: link["data-ids"] for category in ("sub", "dub") if link.get(f"data-{category}") == "1"},
        }

    return episodes


def decrypt_source(value: str, script: str) -> str | None:
    strings = list(dict.fromkeys(match[1] for match in re.findall(r"""(["'])((?:(?!\1)[^\r\n\\]){1,32})\1""", script)))
    encrypted = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    for key in strings:
        if len(key.encode()) > 32:
            continue

        for iv in strings:
            if len(iv.encode()) != 16:
                continue

            try:
                decryptor = Cipher(algorithms.AES(key.encode().ljust(32, b"\0")), modes.CBC(iv.encode())).decryptor()
                plain = decryptor.update(encrypted) + decryptor.finalize()
                unpadder = padding.PKCS7(128).unpadder()
                data = json.loads(unpadder.update(plain) + unpadder.finalize())
                url = data.get("file") or data.get("url")

                if isinstance(url, str) and url.startswith("https://"):
                    return url
            except (ValueError, UnicodeDecodeError):
                continue

    return None


def extract(client, embed):
    page = client.get(embed, BASE + "/", discovered=True).text
    soup = BeautifulSoup(page, "html.parser")
    player = soup.select_one("[data-id]")

    if not player:
        raise common.ProviderError("Anikoto player ID is missing")

    origin = common.origin(embed)
    params = [("id", player["data-id"]), ("id", player["data-id"])]
    server = parse.parse_qs(parse.urlsplit(embed).query).get("s", [""])[0]

    if re.fullmatch(r"[a-zA-Z0-9_-]+", server):
        params.append(("s", server))

    for tag in soup.select("script[src]"):
        script_url = parse.urljoin(embed, tag["src"])

        if parse.urlsplit(script_url).hostname != parse.urlsplit(embed).hostname:
            continue

        script = client.get(script_url, embed, discovered=True).text
        routes = sorted(set(re.findall(r'''["'](stream/getSources[\w/-]*)["']''', script)), key=len, reverse=True)

        for route in routes:
            data = client.json(parse.urljoin(origin, route), embed, params=params, discovered=True)
            sources = data.get("sources") or {}
            url = sources.get("file") if isinstance(sources, dict) else None

            if not url and data.get("enc"):
                url = decrypt_source(data["enc"], script)

            if url:
                tracks = data.get("tracks") or []
                subtitle = common.english_subtitle(tracks)
                return {"url": url, "referer": origin, "subtitle_url": subtitle}

    raise common.ProviderError("Anikoto returned no supported media source")


def stream(client, anime, number, category, item):
    data = client.json(f"{BASE}/ajax/server/list", BASE + "/", params={"servers": item})
    soup = BeautifulSoup(data.get("result", ""), "html.parser")

    errors = []

    for server in soup.select(f'.type[data-type="{category}"] [data-link-id]'):
        try:
            data = client.json(f"{BASE}/ajax/server", BASE + "/", params={"get": server["data-link-id"]})
            embed = data.get("result", {}).get("url")

            if embed:
                result = extract(client, embed)

                # A resolved URL can still be unavailable on the current host.
                if not client.get(result["url"], result["referer"], discovered=True).text.lstrip().startswith("#EXTM3U"):
                    raise common.ProviderError("Anikoto returned an invalid HLS playlist")

                if result.get("subtitle_url"):
                    additional_proxy.validate_url("anikoto", result["subtitle_url"], discovered=True)

                return result
        except ValueError as error:
            errors.append(str(error))

    raise common.ProviderError(f"Anikoto has no supported HLS stream for this episode: {'; '.join(errors)}")
