import re
from functools import lru_cache
from urllib.parse import quote, unquote, urljoin, urlsplit

from curl_cffi import requests as curl_requests
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

from streaming import network


ANIDB_STREAM_PROXY_TOKEN_MAX_AGE = 4 * 60 * 60
ANIDB_STREAM_PROXY_CHUNK_SIZE = 64 * 1024
ANIDB_STREAM_PROXY_MAX_PLAYLIST_SIZE = 2 * 1024 * 1024
ANIDB_STREAM_PROXY_TOKEN_SALT = "anidb-stream-proxy"
ANIDB_STREAM_PROXY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

ANIDB_HOSTNAME = "anidb.app"
ANIDB_CONTENT_TYPES = {
    ".aac": "audio/aac",
    ".m4a": "audio/mp4",
    ".m4s": "video/mp4",
    ".mp4": "video/mp4",
    ".ts": "video/mp2t",
    ".vtt": "text/vtt",
    ".xls": "video/mp2t",
}
URI_ATTRIBUTE_PATTERN = re.compile(r'URI=(?P<quote>["\'])(?P<uri>.*?)(?P=quote)')
SAFE_RESOURCE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]")
BYTE_RANGE_PATTERN = re.compile(r"bytes=(?:\d+-\d*|-\d+)")


class AniDBStreamProxyError(RuntimeError):
    pass


@lru_cache(maxsize=16)
def _validate_public_hostname(hostname: str) -> None:
    network.require_public_host(hostname, AniDBStreamProxyError, "AniDB stream")


def _validate_anidb_url(url: str, label: str) -> str:
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise AniDBStreamProxyError(f"Invalid AniDB {label}")

    try:
        parsed_url = urlsplit(url)
        port = parsed_url.port
    except ValueError as e:
        raise AniDBStreamProxyError(f"Invalid AniDB {label}") from e

    hostname = (parsed_url.hostname or "").lower().rstrip(".")

    if parsed_url.scheme != "https" or not hostname or port not in {None, 443}:
        raise AniDBStreamProxyError(f"Invalid AniDB {label}")

    if parsed_url.username or parsed_url.password:
        raise AniDBStreamProxyError(f"Invalid AniDB {label}")

    if hostname != ANIDB_HOSTNAME and not hostname.endswith(f".{ANIDB_HOSTNAME}"):
        raise AniDBStreamProxyError(f"Unexpected AniDB {label} host")

    _validate_public_hostname(hostname)
    return url


def validate_anidb_stream_url(url: str) -> str:
    return _validate_anidb_url(url, "stream URL")


def _validate_anidb_referer(referer: str) -> str:
    return _validate_anidb_url(referer, "stream referer")


def _get_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt=ANIDB_STREAM_PROXY_TOKEN_SALT)


def create_anidb_stream_proxy_token(secret_key: str, url: str, referer: str) -> str:
    validate_anidb_stream_url(url)
    _validate_anidb_referer(referer)
    return _get_serializer(secret_key).dumps({"url": url, "referer": referer})


def decode_anidb_stream_proxy_token(secret_key: str, token: str) -> dict:
    if not isinstance(token, str) or not token or len(token) > 8192:
        raise AniDBStreamProxyError("Invalid AniDB stream token")

    try:
        payload = _get_serializer(secret_key).loads(
            token,
            max_age=ANIDB_STREAM_PROXY_TOKEN_MAX_AGE
        )
    except SignatureExpired:
        raise
    except BadData as e:
        raise AniDBStreamProxyError("Invalid AniDB stream token") from e

    if not isinstance(payload, dict):
        raise AniDBStreamProxyError("Invalid AniDB stream token")

    url = payload.get("url")
    referer = payload.get("referer")
    validate_anidb_stream_url(url)
    _validate_anidb_referer(referer)
    return {"url": url, "referer": referer}


def get_anidb_stream_resource_name(url: str, fallback: str = "resource") -> str:
    pathname = unquote(urlsplit(url).path)
    resource_name = pathname.rsplit("/", 1)[-1] or fallback
    resource_name = SAFE_RESOURCE_NAME_PATTERN.sub("_", resource_name)[:100]
    return resource_name or fallback


def get_anidb_stream_content_type(url: str, upstream_content_type: str | None) -> str:
    pathname = urlsplit(url).path.lower()

    for suffix, content_type in ANIDB_CONTENT_TYPES.items():
        if pathname.endswith(suffix):
            return content_type

    return upstream_content_type or "application/octet-stream"


def build_anidb_stream_proxy_path(secret_key: str, url: str, referer: str, fallback: str = "resource") -> str:
    token = create_anidb_stream_proxy_token(secret_key, url, referer)
    resource_name = get_anidb_stream_resource_name(url, fallback)
    return f"/api/anidb-streams/{quote(token, safe='')}/{quote(resource_name, safe='')}"


def _rewrite_anidb_hls_uri(uri: str, playlist_url: str, referer: str, secret_key: str) -> str:
    parsed_uri = urlsplit(uri)

    if parsed_uri.scheme and parsed_uri.scheme != "https":
        raise AniDBStreamProxyError("AniDB playlist contains an unsupported URL")

    absolute_url = urljoin(playlist_url, uri)
    return build_anidb_stream_proxy_path(secret_key, absolute_url, referer)


def rewrite_anidb_hls_playlist(playlist: str, playlist_url: str, referer: str, secret_key: str) -> str:
    rewritten_lines = []

    for line in playlist.splitlines():
        stripped_line = line.strip()

        if stripped_line and not stripped_line.startswith("#"):
            line = _rewrite_anidb_hls_uri(stripped_line, playlist_url, referer, secret_key)
        elif "URI=" in line:
            line = URI_ATTRIBUTE_PATTERN.sub(
                lambda match: f'URI={match.group("quote")}{_rewrite_anidb_hls_uri(match.group("uri"), playlist_url, referer, secret_key)}{match.group("quote")}',
                line
            )

        rewritten_lines.append(line)

    rewritten_playlist = "\n".join(rewritten_lines)

    if playlist.endswith(("\n", "\r")):
        rewritten_playlist += "\n"

    return rewritten_playlist


def validate_anidb_range_header(range_header: str | None) -> str | None:
    return network.validate_range_header(range_header, BYTE_RANGE_PATTERN, AniDBStreamProxyError)


def fetch_anidb_stream_resource(url: str, referer: str, range_header: str | None = None):
    validate_anidb_stream_url(url)
    referer = _validate_anidb_referer(referer)
    resource_name = get_anidb_stream_resource_name(url)
    range_header = (
        None
        if resource_name.lower().endswith(".m3u8")
        else validate_anidb_range_header(range_header)
    )
    parsed_referer = urlsplit(referer)
    headers = dict(ANIDB_STREAM_PROXY_HEADERS)
    headers["Referer"] = referer
    headers["Origin"] = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
    headers["Accept-Encoding"] = "identity"

    if resource_name.lower().endswith(".m3u8"):
        headers["Accept"] = "application/vnd.apple.mpegurl,application/x-mpegURL,*/*"

    if range_header:
        headers["Range"] = range_header

    try:
        return curl_requests.get(
            url,
            headers=headers,
            impersonate="chrome136",
            timeout=30,
            allow_redirects=False,
            stream=True
        )
    except Exception as e:
        raise AniDBStreamProxyError("Unable to reach AniDB stream host") from e
