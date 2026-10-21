import re
from html import unescape
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.providers import common


BASE = "https://anineko.to"


def resolve(client, anime):
    candidates = []

    for title in anime["titles"]:
        html = client.get(f"{BASE}/browser", params={"keyword": title}).text

        if "SQLSTATE[" in html:
            raise common.ProviderError("AniNeko returned a database error instead of search results")

        soup = BeautifulSoup(html, "html.parser")

        for link in soup.select(".nv-anime-title a[href]"):
            match = re.fullmatch(r"/watch/([a-z0-9-]+)", urlsplit(link["href"]).path)

            if match:
                candidates.append({"id": match[1], "titles": [link.get_text(strip=True)]})

    return common.exact_match(candidates, anime["titles"])["id"]


def inventory(client, anime):
    slug = common.cached(("anineko-title", anime["mal_id"], anime["titles"]), lambda: resolve(client, anime), 3600)
    soup = BeautifulSoup(client.get(f"{BASE}/watch/{slug}").text, "html.parser")
    episodes = {}

    for article in soup.select("article.nv-info-episode-item"):
        link = article.select_one("a.nv-info-episode-main[href]")

        if not link:
            continue

        match = re.fullmatch(rf"/watch/{re.escape(slug)}/ep-(\d+)", urlsplit(link["href"]).path)
        number = common.episode_number(match[1]) if match else None

        if not number:
            continue

        badges = {span.get_text(strip=True).lower() for span in article.select(".nv-info-episode-badges span")}
        episodes[number] = {category: urljoin(BASE, link["href"]) for category in ("sub", "dub") if category in badges}

    return episodes


def stream(client, anime, number, category, item):
    soup = BeautifulSoup(client.get(item, BASE + "/").text, "html.parser")

    for button in soup.select(f'.nv-server-grid[data-id="{category}"] [data-video]'):
        embed = button["data-video"]

        try:
            html = client.get(embed, BASE + "/", discovered=True).text
            match = re.search(r'''(?:const\s+src\s*=|file\s*:)\s*["'](https://[^"']+\.m3u8[^"']*)["']''', html)

            if match:
                params = parse_qs(urlsplit(embed).query)
                subtitle = next((params[key][0] for key in ("sub", "caption_1", "c1_file") if params.get(key)), None)
                return {"url": unescape(match[1]), "referer": common.origin(embed), "subtitle_url": subtitle}
        except ValueError:
            continue

    raise common.ProviderError("AniNeko has no supported HLS stream for this episode")
