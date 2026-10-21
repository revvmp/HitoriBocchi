import re
from datetime import date
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


SEASONS = ("winter", "spring", "summer", "fall")
MAL_SEASON_URL = "https://myanimelist.net/anime/season/{year}/{season}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def get_current_season(today: date | None = None) -> tuple[int, str]:
    """
    Returns the calendar year and anime season for the supplied date.
    """
    today = today or date.today()
    season = SEASONS[(today.month - 1) // 3]

    return today.year, season


def _parse_seasonal_tv_anime(page_html: str) -> list:
    soup = BeautifulSoup(page_html, "html.parser")
    tv_new_header = next(
        (
            header for header in soup.select(".anime-header")
            if header.get_text(" ", strip=True).casefold() == "tv (new)"
        ),
        None
    )

    if tv_new_header is None:
        raise ValueError("Could not find the TV (New) section on the MyAnimeList seasonal page")

    anime_list = []
    seen_mal_ids = set()
    anime_cards = tv_new_header.parent.find_all(
        "div",
        class_="js-seasonal-anime",
        recursive=False
    )

    for anime_card in anime_cards:
        title_link = anime_card.select_one(".title a[href]")

        if title_link is None:
            continue

        title = title_link.get_text(" ", strip=True)
        mal_url = title_link.get("href", "")
        parsed_url = urlparse(mal_url)
        anime_path = re.fullmatch(r"/anime/(\d+)(?:/[^/]+)?/?", parsed_url.path)

        if (
            not title
            or parsed_url.scheme not in {"http", "https"}
            or parsed_url.hostname not in {"myanimelist.net", "www.myanimelist.net"}
            or anime_path is None
        ):
            continue

        mal_id = int(anime_path.group(1))

        if mal_id in seen_mal_ids:
            continue

        seen_mal_ids.add(mal_id)
        anime_list.append({
            "mal_id": mal_id,
            "title": title,
            "mal_url": f"https://myanimelist.net{parsed_url.path.rstrip('/')}",
        })

    return anime_list


def scrape_seasonal_tv_anime(year: int | None = None, season: str | None = None) -> list:
    """
    Scrapes every anime in MyAnimeList's TV (New) section for a season.

    If no year or season is supplied, the current calendar season is used.
    Each result contains a MyAnimeList ID, title, and MyAnimeList URL.
    """
    current_year, current_season = get_current_season()
    year = current_year if year is None else year
    season = current_season if season is None else season

    if not isinstance(year, int) or isinstance(year, bool) or year <= 0:
        raise ValueError("year must be a positive integer")

    if not isinstance(season, str) or season.casefold() not in SEASONS:
        raise ValueError("season must be winter, spring, summer, or fall")

    season = season.casefold()
    page_url = MAL_SEASON_URL.format(year=year, season=season)
    page = requests.get(page_url, headers=HEADERS, timeout=15)
    page.raise_for_status()

    return _parse_seasonal_tv_anime(page.text)
