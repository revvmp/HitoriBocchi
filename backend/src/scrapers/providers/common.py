import re
import unicodedata
from collections import OrderedDict
from html import unescape
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

from curl_cffi import requests

from streaming import additional_proxy


PROVIDER_TIMEOUT = 7
_cache = OrderedDict()
_cache_lock = Lock()


class ProviderError(ValueError):
    pass


class EpisodeNotFoundError(ProviderError):
    pass


def normalize_title(title: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", unescape(title)).casefold() if char.isalnum())


def exact_match(candidates: list, titles: tuple) -> dict:
    aliases = {normalize_title(title) for title in titles if title}
    matches = {item["id"]: item for item in candidates if aliases.intersection(normalize_title(title) for title in item["titles"] if title)}

    if len(matches) != 1:
        raise ProviderError("No unambiguous title match on this server")

    return next(iter(matches.values()))


def episode_number(value) -> int | None:
    text = str(value)
    return int(text) if re.fullmatch(r"0*[1-9]\d*", text) else None


def english_subtitle(tracks: list) -> str | None:
    candidates = []

    for track in tracks:
        if not isinstance(track, dict):
            continue

        label = " ".join(str(track.get(key) or "") for key in ("language", "lang", "srclang", "label", "name")).casefold()
        url = track.get("url") or track.get("file") or track.get("src")
        is_english = re.search(r"\b(?:english|eng|en)(?:\b|[-_])", label)
        signs_only = re.search(r"\b(?:signs?|songs?|dubtitles?|thumbnails?)\b", label)

        # PGS/VobSub bitmap tracks cannot be converted to WebVTT.
        is_bitmap = isinstance(url, str) and urlsplit(url).path.lower().endswith((".sup", ".idx", ".sub"))

        if url and is_english and not signs_only and not is_bitmap:
            candidates.append(("full" not in label, not track.get("default", False), url))

    candidates.sort(key=lambda item: item[:2])
    return candidates[0][2] if candidates else None


def cached(key, loader, seconds: int = 600):
    with _cache_lock:
        entry = _cache.get(key)

        if entry and entry[0] > monotonic():
            _cache.move_to_end(key)
            return entry[1]

    value = loader()

    with _cache_lock:
        _cache[key] = (monotonic() + seconds, value)
        _cache.move_to_end(key)

        while len(_cache) > 512:
            _cache.popitem(last=False)

    return value


class Client:
    def __init__(self, provider: str):
        self.provider = provider
        self.deadline = monotonic() + PROVIDER_TIMEOUT
        self.session = requests.Session(impersonate="chrome136")

    def close(self):
        self.session.close()

    def get(self, url: str, referer: str | None = None, params=None, discovered: bool = False):
        additional_proxy.validate_url(self.provider, url, discovered)
        remaining = self.deadline - monotonic()

        if remaining <= 0:
            raise ProviderError(f"{self.provider} timed out")

        headers = {"Accept": "*/*"}

        if "/ajax/" in url or self.provider == "anikoto" and urlsplit(url).path.startswith("/stream/getSources"):
            headers["X-Requested-With"] = "XMLHttpRequest"

        if referer:
            headers["Referer"] = referer

        response = self.session.get(url, params=params, headers=headers, timeout=remaining, allow_redirects=False)

        if response.status_code != 200:
            raise ProviderError(f"{self.provider} returned HTTP {response.status_code}: {response.text[:120]}")

        return response

    def json(self, url: str, referer: str | None = None, params=None, discovered: bool = False):
        response = self.get(url, referer, params, discovered)

        try:
            return response.json()
        except ValueError as e:
            raise ProviderError(f"{self.provider} returned invalid JSON") from e


def origin(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}/"
