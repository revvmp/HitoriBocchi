import requests
import re
import unicodedata
from urllib.parse import urlparse

from bs4 import BeautifulSoup

MAL_SEARCH_URL = "https://myanimelist.net/anime.php"
MAL_MANGA_SEARCH_URL = "https://myanimelist.net/manga.php"
MAL_SEARCH_FALLBACK_URL = "https://myanimelist.net/search/prefix.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def slugify(text: str) -> str:
    """
    Converts a raw anime title into a clean, lowercase, URL-safe slug string.
    e.g., "Naruto: Shippuden" -> "naruto-shippuden"
    """
    # 1. Normalize unicode characters (handles odd accents or symbols)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    # 2. Lowercase
    text = text.lower()
    # 3. Strip out everything that isn't alphanumeric, spaces, or hyphens
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    # 4. Replace consecutive spaces or whitespace with a single hyphen
    text = re.sub(r'[\s]+', '-', text)
    # 5. Trim trailing or leading hyphens
    text = text.strip('-')
    return text

def _parse_anime_search_results(page_html: str, limit: int = 1) -> list:
    soup = BeautifulSoup(page_html, "html.parser")
    anime_list = []
    seen_mal_ids = set()

    for title_link in soup.select('a[data-l-module-id="anime-search-result"][href]'):
        title_element = title_link.find("strong")

        if title_element is None:
            continue

        title = title_element.get_text(" ", strip=True)
        mal_url = title_link.get("href", "")
        parsed_url = urlparse(mal_url)
        anime_path = re.fullmatch(r'/anime/(\d+)(?:/[^/]+)?/?', parsed_url.path)

        if (
            not title
            or parsed_url.scheme not in {'http', 'https'}
            or parsed_url.hostname not in {'myanimelist.net', 'www.myanimelist.net'}
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

        if len(anime_list) == limit:
            break

    return anime_list

def _parse_anime_search_json(search_data: dict, limit: int = 1) -> list:
    anime_list = []
    seen_mal_ids = set()

    for category in search_data.get("categories", []):
        if category.get("type") != "anime":
            continue

        for item in category.get("items", []):
            mal_id = item.get("id")
            title = item.get("name")
            mal_url = item.get("url")

            if (
                not isinstance(mal_id, int)
                or isinstance(mal_id, bool)
                or not isinstance(title, str)
                or not title.strip()
                or not isinstance(mal_url, str)
            ):
                continue

            parsed_url = urlparse(mal_url)
            anime_path = re.fullmatch(
                r'/anime/(\d+)(?:/[^/]+)?/?',
                parsed_url.path
            )

            if (
                parsed_url.scheme not in {'http', 'https'}
                or parsed_url.hostname not in {
                    'myanimelist.net',
                    'www.myanimelist.net'
                }
                or anime_path is None
                or int(anime_path.group(1)) != mal_id
                or mal_id in seen_mal_ids
            ):
                continue

            seen_mal_ids.add(mal_id)
            anime_list.append({
                "mal_id": mal_id,
                "title": title.strip(),
                "mal_url": f"https://myanimelist.net{parsed_url.path.rstrip('/')}",
            })

            if len(anime_list) == limit:
                return anime_list

    return anime_list

def search_mal_anime(search_query: str, limit: int = 1) -> list:
    """
    Searches MyAnimeList and returns matching anime IDs, titles, and URLs.
    """
    if not isinstance(search_query, str) or not search_query.strip():
        raise ValueError("search_query is required")

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")

    normalized_query = search_query.strip()

    try:
        page = requests.get(
            MAL_SEARCH_URL,
            params={"q": normalized_query, "cat": "anime"},
            headers=HEADERS,
            timeout=15
        )
        page.raise_for_status()
        search_results = _parse_anime_search_results(page.text, limit)

        if search_results:
            return search_results
    except requests.RequestException:
        pass

    fallback_page = requests.get(
        MAL_SEARCH_FALLBACK_URL,
        params={"type": "anime", "keyword": normalized_query, "v": 1},
        headers=HEADERS,
        timeout=15
    )
    fallback_page.raise_for_status()

    return _parse_anime_search_json(fallback_page.json(), limit)

def scrape_anime_meta_data(url: str):
    parsed_url = urlparse(url)
    anime_path = re.fullmatch(r'/anime/(\d+)(?:/[^/]+)?/?', parsed_url.path)

    if parsed_url.scheme not in {'http', 'https'} or parsed_url.hostname not in {'myanimelist.net', 'www.myanimelist.net'} or anime_path is None:
        raise ValueError('Invalid MyAnimeList anime URL')

    # Example url: "https://myanimelist.net/anime/52991" - Frieren
    page = requests.get(url, headers=HEADERS, timeout=15)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")

    title = soup.find('h1', class_="title-name h1_bold_none").get_text(strip=True)
    title_english_element = soup.find('p', class_="title-english title-inherit")

    if title_english_element:
        title_english = title_english_element.get_text(strip=True)
    else:
        title_english_label = soup.find(
            'span',
            class_="dark_text",
            string=lambda text: text and text.strip() == "English:"
        )

        if title_english_label:
            raw_title_english = title_english_label.parent.get_text(" ", strip=True)
            title_english = raw_title_english.replace("English:", "", 1).strip()
        else:
            title_english = title

    title_english = title_english or title
    slug = slugify(title_english)
    synopsis = soup.find('p', itemprop="description").get_text(separator="\n", strip=True)

    img_element = soup.find('img', itemprop="image")
    image = None
    if img_element:
        image = img_element.get("data-src") or img_element.get("src")

    rating_element = soup.find('span', itemprop="ratingValue")
    rating = 0.0
    if rating_element:
        try:
            rating = float(rating_element.get_text(strip=True))
        except ValueError:
            rating = 0.0

    genre_elements = soup.find_all(attrs={"itemprop": "genre"})
    genres_list = [element.get_text().strip() for element in genre_elements]
    genres = ",".join(genres_list)

    status_span = soup.find('span', string="Status:")
    raw_status = status_span.parent.get_text()
    status = raw_status.replace("Status:", "").strip()

    popularity_span = soup.find('span', string="Popularity:")
    raw_popularity = popularity_span.parent.get_text()
    popularity = int(raw_popularity.split("#")[1])

    current_episodes = 0

    total_episodes_span = soup.find('span', string="Episodes:")
    raw_episodes = total_episodes_span.parent.get_text()
    total_episodes = raw_episodes.replace("Episodes:", "").strip()

    anime_id = int(anime_path.group(1))
    anime_data = {
        "mal_id": anime_id,
        "title": title,
        "title_english": title_english,
        "slug": slug,
        "synopsis": synopsis,
        "image": image,
        "rating": rating,
        "genres": genres,
        "status": status,
        "popularity": popularity,
        "current_episodes": current_episodes,
        "total_episodes": total_episodes,
    }

    return anime_data


def _parse_manga_search_results(page_html: str, limit: int = 1) -> list:
    soup = BeautifulSoup(page_html, "html.parser")
    manga_list = []
    seen_mal_ids = set()
    title_links = soup.select(
        'a[data-l-module-id="manga-search-result"][href], '
        'a.hoverinfo_trigger[href*="/manga/"]'
    )

    for title_link in title_links:
        title_element = title_link.find("strong")
        title = (
            title_element.get_text(" ", strip=True)
            if title_element is not None
            else title_link.get_text(" ", strip=True)
        )
        mal_url = title_link.get("href", "")
        parsed_url = urlparse(mal_url)
        manga_path = re.fullmatch(r'/manga/(\d+)(?:/[^/]+)?/?', parsed_url.path)

        if (
            not title
            or parsed_url.scheme not in {'http', 'https'}
            or parsed_url.hostname not in {'myanimelist.net', 'www.myanimelist.net'}
            or manga_path is None
        ):
            continue

        mal_id = int(manga_path.group(1))

        if mal_id in seen_mal_ids:
            continue

        seen_mal_ids.add(mal_id)
        manga_list.append({
            "mal_id": mal_id,
            "title": title,
            "mal_url": f"https://myanimelist.net{parsed_url.path.rstrip('/')}",
        })

        if len(manga_list) == limit:
            break

    return manga_list


def _parse_manga_search_json(search_data: dict, limit: int = 1) -> list:
    manga_list = []
    seen_mal_ids = set()

    for category in search_data.get("categories", []):
        if category.get("type") != "manga":
            continue

        for item in category.get("items", []):
            mal_id = item.get("id")
            title = item.get("name")
            mal_url = item.get("url")

            if (
                not isinstance(mal_id, int)
                or isinstance(mal_id, bool)
                or not isinstance(title, str)
                or not title.strip()
                or not isinstance(mal_url, str)
            ):
                continue

            parsed_url = urlparse(mal_url)
            manga_path = re.fullmatch(
                r'/manga/(\d+)(?:/[^/]+)?/?',
                parsed_url.path
            )

            if (
                parsed_url.scheme not in {'http', 'https'}
                or parsed_url.hostname not in {
                    'myanimelist.net',
                    'www.myanimelist.net'
                }
                or manga_path is None
                or int(manga_path.group(1)) != mal_id
                or mal_id in seen_mal_ids
            ):
                continue

            seen_mal_ids.add(mal_id)
            manga_list.append({
                "mal_id": mal_id,
                "title": title.strip(),
                "mal_url": f"https://myanimelist.net{parsed_url.path.rstrip('/')}",
            })

            if len(manga_list) == limit:
                return manga_list

    return manga_list


def search_mal_manga(search_query: str, limit: int = 1) -> list:
    """Searches MyAnimeList and returns matching manga IDs, titles, and URLs."""
    if not isinstance(search_query, str) or not search_query.strip():
        raise ValueError("search_query is required")

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")

    normalized_query = search_query.strip()

    try:
        page = requests.get(
            MAL_MANGA_SEARCH_URL,
            params={"q": normalized_query, "cat": "manga"},
            headers=HEADERS,
            timeout=15
        )
        page.raise_for_status()
        search_results = _parse_manga_search_results(page.text, limit)

        if search_results:
            return search_results
    except requests.RequestException:
        pass

    fallback_page = requests.get(
        MAL_SEARCH_FALLBACK_URL,
        params={"type": "manga", "keyword": normalized_query, "v": 1},
        headers=HEADERS,
        timeout=15
    )
    fallback_page.raise_for_status()

    return _parse_manga_search_json(fallback_page.json(), limit)


def _get_mal_labeled_value(soup: BeautifulSoup, label: str, default: str = "") -> str:
    label_element = soup.find(
        'span',
        class_="dark_text",
        string=lambda text: text and text.strip() == f"{label}:"
    )

    if label_element is None or label_element.parent is None:
        return default

    return label_element.parent.get_text(" ", strip=True).replace(
        f"{label}:",
        "",
        1
    ).strip() or default


def scrape_manga_meta_data(url: str):
    """Scrapes manga or manhwa metadata from a MyAnimeList manga URL."""
    parsed_url = urlparse(url)
    manga_path = re.fullmatch(r'/manga/(\d+)(?:/[^/]+)?/?', parsed_url.path)

    if parsed_url.scheme not in {'http', 'https'} or parsed_url.hostname not in {'myanimelist.net', 'www.myanimelist.net'} or manga_path is None:
        raise ValueError('Invalid MyAnimeList manga URL')

    page = requests.get(url, headers=HEADERS, timeout=15)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")

    title_element = soup.find('h1', class_="title-name h1_bold_none") or soup.select_one(
        'h1 [itemprop="name"]'
    )
    title_meta = soup.select_one('meta[property="og:title"]')
    title = (
        title_element.get_text(" ", strip=True)
        if title_element is not None
        else title_meta.get("content", "").strip()
        if title_meta is not None
        else ""
    )

    if not title:
        raise ValueError("MyAnimeList manga title was not found")

    title_english_element = soup.find('p', class_="title-english title-inherit")
    title_english = (
        title_english_element.get_text(strip=True)
        if title_english_element is not None
        else _get_mal_labeled_value(soup, "English", title)
    ) or title
    synopsis_element = soup.find('span', itemprop="description") or soup.find(
        'p',
        itemprop="description"
    )
    synopsis_meta = soup.select_one('meta[property="og:description"]')
    synopsis = (
        synopsis_element.get_text(separator="\n", strip=True)
        if synopsis_element is not None
        else synopsis_meta.get("content", "").strip()
        if synopsis_meta is not None
        else ""
    )
    img_element = soup.find('img', itemprop="image")
    image = (
        img_element.get("data-src") or img_element.get("src")
        if img_element is not None
        else None
    )

    if not image:
        image_meta = soup.select_one('meta[property="og:image"]')
        image = image_meta.get("content") if image_meta is not None else None

    rating_element = soup.find('span', itemprop="ratingValue")

    try:
        rating = float(rating_element.get_text(strip=True)) if rating_element else 0.0
    except ValueError:
        rating = 0.0

    genres = ",".join(
        element.get_text().strip()
        for element in soup.find_all(attrs={"itemprop": "genre"})
    )
    popularity_value = _get_mal_labeled_value(soup, "Popularity")
    popularity_match = re.search(r'#([\d,]+)', popularity_value)
    popularity = (
        int(popularity_match.group(1).replace(",", ""))
        if popularity_match
        else None
    )

    return {
        "mal_id": int(manga_path.group(1)),
        "title": title,
        "title_english": title_english,
        "slug": slugify(title_english),
        "synopsis": synopsis,
        "image": image,
        "rating": rating,
        "genres": genres,
        "status": _get_mal_labeled_value(soup, "Status", "Unknown"),
        "popularity": popularity,
        "media_type": _get_mal_labeled_value(soup, "Type", "Manga"),
        "current_chapters": 0,
        "total_chapters": _get_mal_labeled_value(soup, "Chapters", "Unknown"),
    }
