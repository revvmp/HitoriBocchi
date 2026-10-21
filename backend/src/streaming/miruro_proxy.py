import re
from functools import lru_cache
from urllib.parse import quote, unquote, urljoin, urlsplit

from curl_cffi import requests as curl_requests
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

from scrapers.providers.miruro import HEADERS
from streaming import network, subtitles

STREAM_PROXY_TOKEN_MAX_AGE = 4 * 60 * 60
STREAM_PROXY_CHUNK_SIZE = 64 * 1024
STREAM_PROXY_MAX_PLAYLIST_SIZE = 2 * 1024 * 1024
STREAM_PROXY_MAX_SUBTITLE_SIZE = 16 * 1024 * 1024
STREAM_PROXY_TOKEN_SALT = "anime-stream-proxy"

URI_ATTRIBUTE_PATTERN = re.compile(r'URI=(?P<quote>["\'])(?P<uri>.*?)(?P=quote)')
SAFE_RESOURCE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]")
BYTE_RANGE_PATTERN = re.compile(r"bytes=\d*-\d*")
HLS_ATTRIBUTE_PATTERN = re.compile(r'([A-Z0-9-]+)=(?:"([^"]*)"|([^,]*))')


class StreamProxyError(ValueError):
    pass


@lru_cache(maxsize=128)
def _validate_public_hostname(hostname: str) -> None:
    network.require_public_host(hostname, StreamProxyError, "stream")


def validate_stream_url(url: str) -> str:
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise StreamProxyError("Invalid stream URL")

    parsed_url = urlsplit(url)

    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise StreamProxyError("Stream URL must use HTTPS")

    hostname = parsed_url.hostname.lower().rstrip(".")
    _validate_public_hostname(hostname)
    return hostname


def _validate_referer(referer: str) -> str:
    if not isinstance(referer, str) or not referer or len(referer) > 2048:
        raise StreamProxyError("Invalid stream referer")

    parsed_referer = urlsplit(referer)

    if parsed_referer.scheme not in {"http", "https"} or not parsed_referer.hostname:
        raise StreamProxyError("Invalid stream referer")

    return referer


def _get_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt=STREAM_PROXY_TOKEN_SALT)


def create_stream_proxy_token(secret_key: str, url: str, referer: str, resource_kind: str | None = None, category: str | None = None, quality: str | None = None) -> str:
    validate_stream_url(url)
    _validate_referer(referer)
    if resource_kind not in {None, "playlist", "subtitle", "media"}:
        raise StreamProxyError("Invalid stream resource kind")

    if category not in {None, "sub", "dub"} or quality not in {None, "1080p", "720p", "360p"}:
        raise StreamProxyError("Invalid stream selection")

    return _get_serializer(secret_key).dumps({"url": url, "referer": referer, "resource_kind": resource_kind, "category": category, "quality": quality})


def decode_stream_proxy_token(secret_key: str, token: str) -> dict:
    try:
        payload = _get_serializer(secret_key).loads(
            token,
            max_age=STREAM_PROXY_TOKEN_MAX_AGE
        )
    except SignatureExpired:
        raise
    except BadData as e:
        raise StreamProxyError("Invalid stream token") from e

    if not isinstance(payload, dict):
        raise StreamProxyError("Invalid stream token")

    url = payload.get("url")
    referer = payload.get("referer")
    validate_stream_url(url)
    _validate_referer(referer)
    resource_kind = payload.get("resource_kind")

    if resource_kind not in {None, "playlist", "subtitle", "media"}:
        raise StreamProxyError("Invalid stream resource kind")

    category = payload.get("category")
    quality = payload.get("quality")

    if category not in {None, "sub", "dub"} or quality not in {None, "1080p", "720p", "360p"}:
        raise StreamProxyError("Invalid stream selection")

    return {"url": url, "referer": referer, "resource_kind": resource_kind, "category": category, "quality": quality}


def get_stream_resource_name(url: str, fallback: str = "resource") -> str:
    pathname = unquote(urlsplit(url).path)
    resource_name = pathname.rsplit("/", 1)[-1] or fallback
    resource_name = SAFE_RESOURCE_NAME_PATTERN.sub("_", resource_name)[:100]
    return resource_name or fallback


def build_stream_proxy_path(secret_key: str, url: str, referer: str, fallback: str = "resource", resource_kind: str | None = None, category: str | None = None, quality: str | None = None) -> str:
    token = create_stream_proxy_token(secret_key, url, referer, resource_kind, category, quality)
    resource_name = get_stream_resource_name(url, fallback)

    if resource_kind == "playlist":
        resource_name = "playlist.m3u8"
    elif resource_kind == "subtitle":
        resource_name = "subtitles.vtt"

    return f"/api/streams/{quote(token, safe='')}/{quote(resource_name, safe='')}"

def _rewrite_hls_uri(uri: str, playlist_url: str, referer: str, secret_key: str, resource_kind: str, category: str | None, quality: str | None) -> str:
    parsed_uri = urlsplit(uri)

    if parsed_uri.scheme and parsed_uri.scheme != "https":
        return uri

    absolute_url = urljoin(playlist_url, uri)
    return build_stream_proxy_path(secret_key, absolute_url, referer, resource_kind=resource_kind, category=category, quality=quality)


def _select_hls_renditions(playlist: str, category: str | None, quality: str | None) -> list:
    lines = playlist.splitlines()

    def attributes(line):
        return {key: quoted or plain for key, quoted, plain in HLS_ATTRIBUTE_PATTERN.findall(line)}

    audio = [line for line in lines if line.startswith("#EXT-X-MEDIA:") and attributes(line).get("TYPE") == "AUDIO"]
    selected_audio = audio

    if category and audio:
        languages = {"ja", "jpn", "jap"} if category == "sub" else {"en", "eng"}
        name = "japanese" if category == "sub" else "english"
        selected_audio = [line for line in audio if attributes(line).get("LANGUAGE", "").lower() in languages or name in attributes(line).get("NAME", "").lower()]

        if not selected_audio:
            raise StreamProxyError("Stream playlist does not contain the selected audio")

    heights = {attributes(line).get("RESOLUTION", "").split("x")[-1] for line in lines if line.startswith("#EXT-X-STREAM-INF:")}
    height = (quality or "1080p").removesuffix("p")
    groups = {attributes(line).get("GROUP-ID") for line in selected_audio}
    defaults = set()
    result = []
    keep_variant = True

    for line in lines:
        if line in audio and category:
            if line not in selected_audio:
                continue

            group = attributes(line).get("GROUP-ID")
            default = "YES" if group not in defaults else "NO"
            defaults.add(group)
            line = re.sub(r",DEFAULT=[^,]+", "", line) + f",DEFAULT={default}"

        if line.startswith("#EXT-X-STREAM-INF:"):
            values = attributes(line)
            keep_variant = (height not in heights or values.get("RESOLUTION", "").endswith("x" + height)) and (not category or not audio or values.get("AUDIO") in groups)

            if keep_variant:
                result.append(line)

            continue

        if line and not line.startswith("#"):
            if keep_variant:
                result.append(line)

            keep_variant = True
        else:
            result.append(line)

    return result


def rewrite_hls_playlist(playlist: str, playlist_url: str, referer: str, secret_key: str, category: str | None = None, quality: str | None = None) -> str:
    rewritten_lines = []
    next_is_playlist = False

    for line in _select_hls_renditions(playlist, category, quality):
        stripped_line = line.strip()

        if stripped_line and not stripped_line.startswith("#"):
            line = _rewrite_hls_uri(stripped_line, playlist_url, referer, secret_key, "playlist" if next_is_playlist else "media", category, quality)
            next_is_playlist = False
        elif "URI=" in line:
            resource_kind = "playlist" if stripped_line.startswith(("#EXT-X-MEDIA:", "#EXT-X-I-FRAME-STREAM-INF:", "#EXT-X-RENDITION-REPORT:")) else "media"
            line = URI_ATTRIBUTE_PATTERN.sub(
                lambda match: f'URI={match.group("quote")}{_rewrite_hls_uri(match.group("uri"), playlist_url, referer, secret_key, resource_kind, category, quality)}{match.group("quote")}',
                line
            )

        if stripped_line.startswith("#EXT-X-STREAM-INF:"):
            next_is_playlist = True

        rewritten_lines.append(line)

    rewritten_playlist = "\n".join(rewritten_lines)

    if playlist.endswith(("\n", "\r")):
        rewritten_playlist += "\n"

    return rewritten_playlist


def validate_range_header(range_header: str | None) -> str | None:
    return network.validate_range_header(range_header, BYTE_RANGE_PATTERN, StreamProxyError)


def fetch_stream_resource(url: str, referer: str, range_header: str | None = None, resource_kind: str | None = None):
    validate_stream_url(url)
    referer = _validate_referer(referer)
    range_header = validate_range_header(range_header)
    parsed_referer = urlsplit(referer)
    headers = dict(HEADERS)
    headers["Referer"] = referer
    headers["Origin"] = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
    headers["Accept-Encoding"] = "identity"

    if range_header and resource_kind not in {"playlist", "subtitle"} and not urlsplit(url).path.lower().endswith((".m3u8", ".vtt", ".srt", ".ass")):
        headers["Range"] = range_header

    try:
        return curl_requests.get(
            url,
            headers=headers,
            impersonate="chrome110",
            timeout=30,
            allow_redirects=False,
            stream=True
        )
    except Exception as e:
        raise StreamProxyError("Unable to reach stream host") from e


def read_subtitle(response) -> str:
    chunks = []
    size = 0

    try:
        for chunk in response.iter_content(chunk_size=STREAM_PROXY_CHUNK_SIZE):
            size += len(chunk)

            if size > STREAM_PROXY_MAX_SUBTITLE_SIZE:
                raise StreamProxyError("Stream subtitle is too large")

            chunks.append(chunk)

        return subtitles.convert_to_webvtt(b"".join(chunks))
    except (UnicodeError, ValueError) as error:
        raise StreamProxyError("Stream subtitle is invalid") from error
    finally:
        response.close()
