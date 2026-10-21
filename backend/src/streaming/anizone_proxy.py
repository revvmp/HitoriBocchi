import re
from functools import lru_cache
from html import unescape
from urllib.parse import quote, unquote, urljoin, urlsplit

from curl_cffi import requests as curl_requests
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

from streaming import network


ANIZONE_STREAM_PROXY_TOKEN_MAX_AGE = 4 * 60 * 60
ANIZONE_STREAM_PROXY_CHUNK_SIZE = 64 * 1024
ANIZONE_STREAM_PROXY_MAX_PLAYLIST_SIZE = 2 * 1024 * 1024
ANIZONE_STREAM_PROXY_MAX_SUBTITLE_SIZE = 2 * 1024 * 1024
ANIZONE_STREAM_PROXY_TOKEN_SALT = "anizone-stream-proxy"
ANIZONE_STREAM_PROXY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

ANIZONE_SITE_HOSTNAME = "anizone.to"
ANIZONE_MEDIA_HOSTNAMES = {
    "vid-cdn.xyz",
    "xin-cdn.xyz",
}
ANIZONE_CONTENT_TYPES = {
    ".aac": "audio/aac",
    ".key": "application/octet-stream",
    ".m4a": "audio/mp4",
    ".m4s": "video/mp4",
    ".mp4": "video/mp4",
    ".ts": "video/mp2t",
    ".vtt": "text/vtt",
}
ANIZONE_AUDIO_LANGUAGES = {"en", "ja"}
ANIZONE_QUALITIES = {"360", "720", "1080"}
ANIZONE_RESOURCE_KINDS = {"stream", "subtitle"}
URI_ATTRIBUTE_PATTERN = re.compile(r'URI=(?P<quote>["\'])(?P<uri>.*?)(?P=quote)')
HLS_AUDIO_TYPE_PATTERN = re.compile(r"(?:^|[:,])TYPE=AUDIO(?:,|$)", re.IGNORECASE)
HLS_LANGUAGE_PATTERN = re.compile(r'(?:^|,)LANGUAGE=(?:"(?P<quoted>[^"]+)"|(?P<plain>[^,]+))', re.IGNORECASE)
HLS_RESOLUTION_PATTERN = re.compile(r"\bRESOLUTION=\d+x(?P<height>\d+)\b", re.IGNORECASE)
ASS_TIME_PATTERN = re.compile(r"^(?P<hours>\d+):(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2})(?:\.(?P<fraction>\d{1,3}))?$")
ASS_OVERRIDE_PATTERN = re.compile(r"\{[^}]*\}")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
SAFE_RESOURCE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]")
BYTE_RANGE_PATTERN = re.compile(r"bytes=(?:\d+-\d*|-\d+)")


class AniZoneStreamProxyError(RuntimeError):
    pass


@lru_cache(maxsize=32)
def _validate_public_hostname(hostname: str) -> None:
    network.require_public_host(hostname, AniZoneStreamProxyError, "AniZone stream")


def _validate_anizone_url(url: str, hostnames: set, label: str) -> str:
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise AniZoneStreamProxyError(f"Invalid AniZone {label}")

    try:
        parsed_url = urlsplit(url)
        port = parsed_url.port
    except ValueError as e:
        raise AniZoneStreamProxyError(f"Invalid AniZone {label}") from e

    actual_hostname = (parsed_url.hostname or "").lower().rstrip(".")

    if parsed_url.scheme != "https" or not actual_hostname or port not in {None, 443}:
        raise AniZoneStreamProxyError(f"Invalid AniZone {label}")

    if parsed_url.username or parsed_url.password:
        raise AniZoneStreamProxyError(f"Invalid AniZone {label}")

    if not any(
        actual_hostname == hostname or actual_hostname.endswith(f".{hostname}")
        for hostname in hostnames
    ):
        raise AniZoneStreamProxyError(f"Unexpected AniZone {label} host")

    _validate_public_hostname(actual_hostname)
    return url


def validate_anizone_stream_url(url: str) -> str:
    return _validate_anizone_url(url, ANIZONE_MEDIA_HOSTNAMES, "stream URL")


def _validate_anizone_referer(referer: str) -> str:
    return _validate_anizone_url(referer, {ANIZONE_SITE_HOSTNAME}, "stream referer")


def _validate_audio_language(audio_language: str) -> str:
    if audio_language not in ANIZONE_AUDIO_LANGUAGES:
        raise AniZoneStreamProxyError("Invalid AniZone audio language")

    return audio_language


def _validate_quality(quality: str | None) -> str | None:
    if quality is not None and quality not in ANIZONE_QUALITIES:
        raise AniZoneStreamProxyError("Invalid AniZone stream quality")

    return quality


def _validate_resource_kind(resource_kind: str) -> str:
    if resource_kind not in ANIZONE_RESOURCE_KINDS:
        raise AniZoneStreamProxyError("Invalid AniZone stream resource type")

    return resource_kind


def _get_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt=ANIZONE_STREAM_PROXY_TOKEN_SALT)


def create_anizone_stream_proxy_token(secret_key: str, url: str, referer: str, audio_language: str, quality: str | None = None, resource_kind: str = "stream") -> str:
    validate_anizone_stream_url(url)
    _validate_anizone_referer(referer)
    _validate_audio_language(audio_language)
    _validate_quality(quality)
    _validate_resource_kind(resource_kind)

    return _get_serializer(secret_key).dumps({
        "audio_language": audio_language,
        "quality": quality,
        "referer": referer,
        "resource_kind": resource_kind,
        "url": url,
    })


def decode_anizone_stream_proxy_token(secret_key: str, token: str) -> dict:
    if not isinstance(token, str) or not token or len(token) > 8192:
        raise AniZoneStreamProxyError("Invalid AniZone stream token")

    try:
        payload = _get_serializer(secret_key).loads(
            token,
            max_age=ANIZONE_STREAM_PROXY_TOKEN_MAX_AGE
        )
    except SignatureExpired:
        raise
    except BadData as e:
        raise AniZoneStreamProxyError("Invalid AniZone stream token") from e

    if not isinstance(payload, dict):
        raise AniZoneStreamProxyError("Invalid AniZone stream token")

    url = payload.get("url")
    referer = payload.get("referer")
    audio_language = payload.get("audio_language")
    quality = payload.get("quality")
    resource_kind = payload.get("resource_kind")
    validate_anizone_stream_url(url)
    _validate_anizone_referer(referer)
    _validate_audio_language(audio_language)
    _validate_quality(quality)
    _validate_resource_kind(resource_kind)

    return {
        "audio_language": audio_language,
        "quality": quality,
        "referer": referer,
        "resource_kind": resource_kind,
        "url": url,
    }


def get_anizone_stream_resource_name(url: str, fallback: str = "resource") -> str:
    pathname = unquote(urlsplit(url).path)
    resource_name = pathname.rsplit("/", 1)[-1] or fallback
    resource_name = SAFE_RESOURCE_NAME_PATTERN.sub("_", resource_name)[:100]
    return resource_name or fallback


def get_anizone_stream_content_type(url: str, upstream_content_type: str | None) -> str:
    pathname = urlsplit(url).path.lower()

    for suffix, content_type in ANIZONE_CONTENT_TYPES.items():
        if pathname.endswith(suffix):
            return content_type

    return upstream_content_type or "application/octet-stream"


def build_anizone_stream_proxy_path(secret_key: str, url: str, referer: str, audio_language: str, quality: str | None = None, resource_kind: str = "stream", fallback: str = "resource") -> str:
    token = create_anizone_stream_proxy_token(
        secret_key=secret_key,
        url=url,
        referer=referer,
        audio_language=audio_language,
        quality=quality,
        resource_kind=resource_kind
    )
    resource_name = (
        "subtitles.vtt"
        if resource_kind == "subtitle"
        else get_anizone_stream_resource_name(url, fallback)
    )
    return f"/api/anizone-streams/{quote(token, safe='')}/{quote(resource_name, safe='')}"


def _rewrite_anizone_hls_uri(uri: str, playlist_url: str, referer: str, secret_key: str, audio_language: str, quality: str | None) -> str:
    parsed_uri = urlsplit(uri)

    if parsed_uri.scheme and parsed_uri.scheme != "https":
        raise AniZoneStreamProxyError("AniZone playlist contains an unsupported URL")

    absolute_url = urljoin(playlist_url, uri)
    return build_anizone_stream_proxy_path(
        secret_key=secret_key,
        url=absolute_url,
        referer=referer,
        audio_language=audio_language,
        quality=quality
    )


def _rewrite_uri_attributes(line: str, playlist_url: str, referer: str, secret_key: str, audio_language: str, quality: str | None) -> str:
    return URI_ATTRIBUTE_PATTERN.sub(
        lambda match: f'URI={match.group("quote")}{_rewrite_anizone_hls_uri(match.group("uri"), playlist_url, referer, secret_key, audio_language, quality)}{match.group("quote")}',
        line
    )


def _get_hls_language(line: str) -> str | None:
    match = HLS_LANGUAGE_PATTERN.search(line)

    if match is None:
        return None

    language = (match.group("quoted") or match.group("plain")).strip().lower()

    if language in {"ja", "jpn"}:
        return "ja"

    if language in {"en", "eng"}:
        return "en"

    return None


def _set_hls_attribute(line: str, name: str, value: str) -> str:
    attribute_pattern = re.compile(
        rf'(?P<prefix>[:,]){re.escape(name)}=(?:"[^"]*"|[^,]*)',
        re.IGNORECASE
    )

    if attribute_pattern.search(line):
        return attribute_pattern.sub(
            lambda match: f'{match.group("prefix")}{name}={value}',
            line,
            count=1
        )

    return f"{line},{name}={value}"


def rewrite_anizone_hls_playlist(playlist: str, playlist_url: str, referer: str, secret_key: str, audio_language: str, quality: str | None = None) -> str:
    validate_anizone_stream_url(playlist_url)
    _validate_anizone_referer(referer)
    _validate_audio_language(audio_language)
    _validate_quality(quality)

    lines = playlist.splitlines()
    is_master_playlist = any(
        line.strip().startswith("#EXT-X-STREAM-INF:")
        for line in lines
    )
    rewritten_lines = []
    pending_variant = None
    selected_audio_tracks = 0
    selected_variants = 0

    for line in lines:
        stripped_line = line.strip()

        if pending_variant is not None:
            if not stripped_line or stripped_line.startswith("#"):
                if pending_variant:
                    rewritten_lines.append(line)

                continue

            if pending_variant:
                rewritten_lines.append(
                    _rewrite_anizone_hls_uri(
                        stripped_line,
                        playlist_url,
                        referer,
                        secret_key,
                        audio_language,
                        quality
                    )
                )

            pending_variant = None
            continue

        if is_master_playlist and stripped_line.startswith("#EXT-X-MEDIA:") and HLS_AUDIO_TYPE_PATTERN.search(stripped_line):
            if _get_hls_language(stripped_line) != audio_language:
                continue

            line = _set_hls_attribute(line, "DEFAULT", "YES")
            line = _set_hls_attribute(line, "AUTOSELECT", "YES")
            line = _rewrite_uri_attributes(
                line,
                playlist_url,
                referer,
                secret_key,
                audio_language,
                quality
            )
            rewritten_lines.append(line)
            selected_audio_tracks += 1
            continue

        if is_master_playlist and stripped_line.startswith("#EXT-X-STREAM-INF:"):
            resolution_match = HLS_RESOLUTION_PATTERN.search(stripped_line)
            variant_quality = resolution_match.group("height") if resolution_match else None
            pending_variant = quality is None or variant_quality == quality

            if not pending_variant:
                continue

            rewritten_lines.append(line)
            selected_variants += 1
            continue

        if stripped_line and not stripped_line.startswith("#"):
            line = _rewrite_anizone_hls_uri(
                stripped_line,
                playlist_url,
                referer,
                secret_key,
                audio_language,
                quality
            )
        elif "URI=" in line:
            line = _rewrite_uri_attributes(
                line,
                playlist_url,
                referer,
                secret_key,
                audio_language,
                quality
            )

        rewritten_lines.append(line)

    if is_master_playlist and selected_audio_tracks == 0:
        raise AniZoneStreamProxyError("AniZone playlist does not contain the selected audio track")

    if is_master_playlist and quality is not None and selected_variants == 0:
        raise AniZoneStreamProxyError("AniZone playlist does not contain the selected quality")

    rewritten_playlist = "\n".join(rewritten_lines)

    if playlist.endswith(("\n", "\r")):
        rewritten_playlist += "\n"

    return rewritten_playlist


def _format_vtt_time(value: str) -> str | None:
    match = ASS_TIME_PATTERN.fullmatch(value.strip())

    if match is None:
        return None

    fraction = (match.group("fraction") or "0")[:3].ljust(3, "0")
    return f'{int(match.group("hours")):02d}:{int(match.group("minutes")):02d}:{int(match.group("seconds")):02d}.{fraction}'


def _decode_subtitle_payload(payload: bytes) -> str:
    try:
        if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
            return payload.decode("utf-16")

        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise AniZoneStreamProxyError("AniZone subtitle file is invalid") from e


def _convert_ass_to_vtt(subtitle: str) -> str:
    in_events = False
    event_fields = []
    cues = []

    for line in subtitle.splitlines():
        stripped_line = line.strip()

        if stripped_line.startswith("[") and stripped_line.endswith("]"):
            in_events = stripped_line.casefold() == "[events]"
            continue

        if not in_events:
            continue

        if stripped_line.casefold().startswith("format:"):
            event_fields = [
                field.strip().casefold()
                for field in stripped_line.split(":", 1)[1].split(",")
            ]
            continue

        if not event_fields or not stripped_line.casefold().startswith("dialogue:"):
            continue

        values = stripped_line.split(":", 1)[1].lstrip().split(",", len(event_fields) - 1)

        if len(values) != len(event_fields):
            continue

        event = dict(zip(event_fields, values))
        start_time = _format_vtt_time(event.get("start", ""))
        end_time = _format_vtt_time(event.get("end", ""))
        text = event.get("text", "")

        if start_time is None or end_time is None or re.search(r"\{\\p[1-9]", text, re.IGNORECASE):
            continue

        text = ASS_OVERRIDE_PATTERN.sub("", text)
        text = re.sub(r"\\[Nn]", "\n", text)
        text = text.replace("\\h", " ")
        text = HTML_TAG_PATTERN.sub("", text)
        text = unescape(text).strip()

        if text:
            cues.append(f"{start_time} --> {end_time}\n{text}")

    if not cues:
        raise AniZoneStreamProxyError("AniZone subtitle file does not contain readable cues")

    return "WEBVTT\n\n" + "\n\n".join(cues) + "\n"


def _convert_srt_to_vtt(subtitle: str) -> str:
    cues = []
    timing = re.compile(r"^(\d{2,}:[0-5]\d:[0-5]\d[,\.]\d{3})\s+-->\s+(\d{2,}:[0-5]\d:[0-5]\d[,\.]\d{3})$")

    for block in re.split(r"\n\s*\n", subtitle.replace("\r\n", "\n").replace("\r", "\n").strip()):
        lines = block.splitlines()

        if lines and lines[0].strip().isdigit():
            lines = lines[1:]

        match = timing.fullmatch(lines[0].strip()) if lines else None

        if match is None:
            continue

        text = ASS_OVERRIDE_PATTERN.sub("", "\n".join(lines[1:])).strip()

        if text:
            cues.append(f"{match[1].replace(',', '.')} --> {match[2].replace(',', '.')}\n{text}")

    if not cues:
        raise AniZoneStreamProxyError("AniZone subtitle file does not contain readable cues")

    return "WEBVTT\n\n" + "\n\n".join(cues) + "\n"


def convert_anizone_subtitle(payload: bytes, url: str) -> str:
    validate_anizone_stream_url(url)
    subtitle = _decode_subtitle_payload(payload)

    if urlsplit(url).path.lower().endswith(".vtt") or subtitle.lstrip().startswith("WEBVTT"):
        if not subtitle.lstrip().startswith("WEBVTT"):
            raise AniZoneStreamProxyError("AniZone subtitle file is invalid")

        return subtitle

    if "-->" in subtitle and "[events]" not in subtitle.casefold():
        return _convert_srt_to_vtt(subtitle)

    return _convert_ass_to_vtt(subtitle)


def validate_anizone_range_header(range_header: str | None) -> str | None:
    return network.validate_range_header(range_header, BYTE_RANGE_PATTERN, AniZoneStreamProxyError)


def fetch_anizone_stream_resource(url: str, referer: str, resource_kind: str = "stream", range_header: str | None = None):
    validate_anizone_stream_url(url)
    referer = _validate_anizone_referer(referer)
    resource_kind = _validate_resource_kind(resource_kind)
    resource_name = get_anizone_stream_resource_name(url)
    range_header = (
        None
        if resource_kind == "subtitle" or resource_name.lower().endswith(".m3u8")
        else validate_anizone_range_header(range_header)
    )
    headers = dict(ANIZONE_STREAM_PROXY_HEADERS)
    headers["Referer"] = referer
    headers["Origin"] = f"https://{ANIZONE_SITE_HOSTNAME}"
    headers["Accept-Encoding"] = "identity"

    if resource_name.lower().endswith(".m3u8"):
        headers["Accept"] = "application/vnd.apple.mpegurl,application/x-mpegURL,*/*"
    elif resource_kind == "subtitle":
        headers["Accept"] = "text/vtt,text/plain,*/*"

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
        raise AniZoneStreamProxyError("Unable to reach AniZone stream host") from e
