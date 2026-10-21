import base64
import ipaddress
import re
import socket
from functools import lru_cache
from urllib.parse import quote, urljoin, urlsplit

from curl_cffi import requests
from itsdangerous import URLSafeTimedSerializer

from streaming import subtitles


# Provider entry points only; scraper requests to these hosts need no discovery.
HOSTS = {
    "anibd": {"animeapps.top"},
    "anineko": {"anineko.to"},
    "anikoto": {"anikototv.to"},
    "reanime": {"reanime.to", "flixcloud.cc"},
}
CHUNK_SIZE = 64 * 1024
MAX_TEXT_SIZE = 4 * 1024 * 1024
# Heavily typeset ASS files can exceed 16 MiB (Attack on Titan S2 is about 17.7 MB).
MAX_SUBTITLE_SIZE = 32 * 1024 * 1024
URI_PATTERN = re.compile(r'URI=("|\')([^"\']+)\1')
ATTRIBUTE_PATTERN = re.compile(r'([A-Z0-9-]+)=(?:"([^"]*)"|([^,]*))')
CONTENT_TYPES = {".m3u8": "application/vnd.apple.mpegurl", ".mp4": "video/mp4", ".m4s": "video/mp4", ".ts": "video/mp2t", ".aac": "audio/aac", ".vtt": "text/vtt"}
# The public Flixcloud HLS loader uses this fixed mask for image-wrapped TS.
REANIME_SEGMENT_MASK = bytes([157, 42, 241, 71, 179, 142, 92, 112, 166, 25, 228, 59, 216, 98, 15, 197])


class PlaybackProxyError(ValueError):
    pass


@lru_cache(maxsize=128)
def _validate_public_host(host: str):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise PlaybackProxyError(f"Unable to resolve playback host: {host}") from e

    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise PlaybackProxyError("Playback host must resolve to a public address")


def validate_url(provider: str, url: str, discovered: bool = False) -> str:
    if provider not in HOSTS or not isinstance(url, str) or not url or len(url) > 8192:
        raise PlaybackProxyError("Invalid playback URL")

    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme != "https" or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise PlaybackProxyError("Invalid playback URL")

    # Embeds and CDNs rotate hosts, so URLs returned by the provider or signed into
    # a proxy token accept any public host; only entry points are allowlisted.
    if not discovered and not any(host == allowed or host.endswith("." + allowed) for allowed in HOSTS[provider]):
        raise PlaybackProxyError(f"Unexpected {provider} playback host: {host}")

    _validate_public_host(host)
    return url


def build_path(secret_key: str, provider: str, url: str, referer: str, category: str = "sub", quality: str | None = None, subtitle: bool = False, manifest_key: str | None = None, encrypted: bool = False) -> str:
    validate_url(provider, url, discovered=True)
    validate_url(provider, referer, discovered=True)
    payload = {"provider": provider, "url": url, "referer": referer, "category": category, "quality": quality, "subtitle": subtitle, "manifest_key": manifest_key, "encrypted": encrypted}
    token = URLSafeTimedSerializer(secret_key, salt="additional-playback-streams").dumps(payload)
    extension = ".vtt" if subtitle else ".mp4" if urlsplit(url).path.lower().endswith(".mp4") else ".m3u8" if urlsplit(url).path.lower().endswith(".m3u8") else ""
    return f"/api/playback-streams/{quote(token, safe='')}/resource{extension}"


def decode_token(secret_key: str, token: str) -> dict:
    if len(token) > 16000:
        raise PlaybackProxyError("Invalid playback token")

    payload = URLSafeTimedSerializer(secret_key, salt="additional-playback-streams").loads(token, max_age=4 * 60 * 60)

    if not isinstance(payload, dict) or payload.get("category") not in {"sub", "dub"} or payload.get("quality") not in {None, "1080p", "720p", "360p"}:
        raise PlaybackProxyError("Invalid playback token")

    if not isinstance(payload.get("encrypted", False), bool):
        raise PlaybackProxyError("Invalid encryption flag")

    validate_url(payload["provider"], payload["url"], discovered=True)
    validate_url(payload["provider"], payload["referer"], discovered=True)
    return payload


def fetch_resource(payload: dict, range_header: str | None = None):
    validate_url(payload["provider"], payload["url"], discovered=True)
    validate_url(payload["provider"], payload["referer"], discovered=True)
    headers = {"Referer": payload["referer"], "Accept-Encoding": "identity"}

    if range_header and not urlsplit(payload["url"]).path.lower().endswith(".m3u8") and not payload["subtitle"] and not is_wrapped_media(payload):
        if not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", range_header) or len(range_header) > 100:
            raise PlaybackProxyError("Invalid Range header")

        headers["Range"] = range_header

    return requests.get(payload["url"], headers=headers, impersonate="chrome136", timeout=30, allow_redirects=False, stream=True)


def is_wrapped_media(payload: dict) -> bool:
    parsed = urlsplit(payload["url"])
    return (payload["provider"] == "reanime" and parsed.path.lower().endswith((".webp", ".png"))) or (payload["provider"] == "anikoto" and (parsed.hostname or "").endswith(".tiktokcdn.com"))


def prepare_media(response, payload: dict):
    iterator = response.iter_content(chunk_size=CHUNK_SIZE)
    prefix = b""

    while len(prefix) < 1024:
        try:
            prefix += next(iterator)
        except StopIteration:
            break

    stripped = 0
    mask = None

    if is_wrapped_media(payload):
        if payload["provider"] == "reanime":
            if prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP":
                stripped = 12
            elif prefix.startswith(b"\x89PNG\r\n\x1a\n"):
                stripped = 8

            if stripped and prefix[stripped:stripped + 1] != b"G":
                mask = REANIME_SEGMENT_MASK
        else:
            stripped = next((index for index in range(min(len(prefix) - 376, 4096)) if prefix[index] == prefix[index + 188] == prefix[index + 376] == 71), 0)

    prefix = prefix[stripped:]

    if mask:
        prefix = bytes(value ^ mask[index % len(mask)] for index, value in enumerate(prefix))

    is_ts = len(prefix) > 376 and prefix[0] == prefix[188] == prefix[376] == 71

    is_encrypted = payload["provider"] == "reanime" and payload.get("encrypted", False) and len(prefix) >= 16

    if is_wrapped_media(payload) and not is_ts and not is_encrypted:
        response.close()
        raise PlaybackProxyError(f"Unsupported wrapped video segment on {urlsplit(payload['url']).hostname} (prefix {prefix[:12].hex()})")

    def chunks():
        offset = len(prefix)

        try:
            yield prefix

            for chunk in iterator:
                if mask:
                    chunk = bytes(value ^ mask[(offset + index) % len(mask)] for index, value in enumerate(chunk))

                offset += len(chunk)
                yield chunk
        finally:
            response.close()

    return chunks(), stripped, "video/mp2t" if is_ts else "application/octet-stream" if is_encrypted else None


def read_text(response, max_size: int = MAX_TEXT_SIZE) -> bytes:
    chunks = []
    size = 0

    try:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            size += len(chunk)

            if size > max_size:
                raise PlaybackProxyError("Playback text resource is too large")

            chunks.append(chunk)
    finally:
        response.close()

    return b"".join(chunks)


def attributes(line: str) -> dict:
    return {key: quoted or plain for key, quoted, plain in ATTRIBUTE_PATTERN.findall(line)}


def audio_category(line: str) -> str | None:
    values = attributes(line)
    language = values.get("LANGUAGE", "").lower()
    name = values.get("NAME", "").lower()

    if language in {"ja", "jpn", "jap"} or "japanese" in name:
        return "sub"

    if language in {"en", "eng"} or "english" in name:
        return "dub"

    return None


def decode_playlist(playlist: str, payload: dict) -> str:
    if not playlist.lstrip().startswith("#EXTM3U") and payload.get("manifest_key"):
        key = base64.b64decode(payload["manifest_key"], validate=True)
        encoded = base64.b64decode(playlist.strip(), validate=True)

        if len(key) != 32:
            raise PlaybackProxyError("Invalid playlist key")

        playlist = bytes(value ^ key[index % len(key)] for index, value in enumerate(encoded)).decode("utf-8")

    if not playlist.lstrip().startswith("#EXTM3U"):
        raise PlaybackProxyError("Invalid HLS playlist")

    return playlist


def rewrite_playlist(playlist: str, payload: dict, secret_key: str) -> str:
    lines = decode_playlist(playlist, payload).splitlines()
    audio_lines = [line for line in lines if line.startswith("#EXT-X-MEDIA:") and attributes(line).get("TYPE") == "AUDIO"]
    selected_audio = [line for line in audio_lines if audio_category(line) == payload["category"]]

    if audio_lines and not selected_audio:
        raise PlaybackProxyError("Selected audio is missing from the HLS playlist")

    groups = {attributes(line).get("GROUP-ID") for line in selected_audio}
    variants = [attributes(line) for line in lines if line.startswith("#EXT-X-STREAM-INF:")]
    heights = {item.get("RESOLUTION", "").split("x")[-1] for item in variants}
    preferred = (payload.get("quality") or "1080p").removesuffix("p")
    selected_height = preferred if preferred in heights else None
    result = []
    keep_variant = True
    encrypted = False

    def signed(uri, encrypted=False):
        return build_path(secret_key, payload["provider"], urljoin(payload["url"], uri), payload["referer"], payload["category"], payload.get("quality"), manifest_key=payload.get("manifest_key"), encrypted=encrypted)

    for line in lines:
        line = line.strip()

        if line.startswith("#EXT-X-KEY:"):
            encrypted = attributes(line).get("METHOD") == "AES-128"

        if line.startswith("#EXT-X-MEDIA:") and attributes(line).get("TYPE") == "AUDIO":
            if line not in selected_audio:
                continue

            # One default per audio group, preserving language and group IDs.
            first = next(item for item in selected_audio if attributes(item).get("GROUP-ID") == attributes(line).get("GROUP-ID"))
            default = "YES" if line == first else "NO"
            line = re.sub(r",DEFAULT=[^,]+", "", line) + f",DEFAULT={default}"

        if line.startswith("#EXT-X-STREAM-INF:"):
            values = attributes(line)
            keep_variant = (selected_height is None or values.get("RESOLUTION", "").endswith("x" + selected_height)) and (not audio_lines or values.get("AUDIO") in groups)

            if keep_variant:
                result.append(line)

            continue

        if line and not line.startswith("#"):
            if keep_variant:
                result.append(signed(line, encrypted))

            keep_variant = True
            continue

        if "URI=" in line:
            line = URI_PATTERN.sub(lambda match: f'URI="{signed(match[2])}"', line)

        result.append(line)

    if variants and not any(line.startswith("#EXT-X-STREAM-INF:") for line in result):
        raise PlaybackProxyError("No matching HLS variant")

    return "\n".join(result) + "\n"


def convert_subtitle(payload: bytes) -> str:
    return subtitles.convert_to_webvtt(payload)
