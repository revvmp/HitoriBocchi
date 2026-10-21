import time
from functools import lru_cache
from urllib.parse import quote, unquote, urlsplit

from curl_cffi import requests as curl_requests
from itsdangerous import BadData, SignatureExpired, URLSafeSerializer, URLSafeTimedSerializer

from streaming import network


MANGA_IMAGE_PROXY_TOKEN_MAX_AGE = 2 * 60 * 60
MANGA_IMAGE_PROXY_TOKEN_REUSE_WINDOW = 60 * 60
MANGA_IMAGE_PROXY_CHUNK_SIZE = 64 * 1024
MANGA_IMAGE_PROXY_MAX_SIZE = 25 * 1024 * 1024
MANGA_IMAGE_PROXY_TOKEN_SALT = "manga-image-proxy"
MANGAKATANA_ALLOWED_HOST_SUFFIXES = (
    "mangakatana.com",
)

MANGA_IMAGE_CONTENT_TYPES = {
    ".avif": "image/avif",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class MangaImageProxyError(ValueError):
    pass


@lru_cache(maxsize=32)
def _validate_public_hostname(hostname: str) -> None:
    network.require_public_host(hostname, MangaImageProxyError, "manga image")


def validate_manga_image_url(url: str) -> str:
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise MangaImageProxyError("Invalid manga image URL")

    parsed_url = urlsplit(url)

    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise MangaImageProxyError("Manga image URL must use HTTPS")

    hostname = parsed_url.hostname.lower().rstrip(".")

    is_allowed_host = any(
        hostname == suffix or hostname.endswith(f".{suffix}")
        for suffix in MANGAKATANA_ALLOWED_HOST_SUFFIXES
    )

    if not is_allowed_host:
        raise MangaImageProxyError("Manga image host is not allowed")

    _validate_public_hostname(hostname)
    return hostname


def _get_serializer(secret_key: str) -> URLSafeSerializer:
    return URLSafeSerializer(
        secret_key,
        salt=MANGA_IMAGE_PROXY_TOKEN_SALT
    )


def _get_legacy_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key,
        salt=MANGA_IMAGE_PROXY_TOKEN_SALT
    )


def create_manga_image_proxy_token(secret_key: str, url: str) -> str:
    validate_manga_image_url(url)
    current_time = int(time.time())
    token_bucket_started_at = (
        current_time
        // MANGA_IMAGE_PROXY_TOKEN_REUSE_WINDOW
        * MANGA_IMAGE_PROXY_TOKEN_REUSE_WINDOW
    )
    expires_at = token_bucket_started_at + MANGA_IMAGE_PROXY_TOKEN_MAX_AGE
    return _get_serializer(secret_key).dumps({
        "url": url,
        "expires_at": expires_at,
    })


def decode_manga_image_proxy_token(secret_key: str, token: str) -> str:
    try:
        payload = _get_serializer(secret_key).loads(token)
    except BadData:
        try:
            payload = _get_legacy_serializer(secret_key).loads(
                token,
                max_age=MANGA_IMAGE_PROXY_TOKEN_MAX_AGE
            )
        except SignatureExpired:
            raise
        except BadData as e:
            raise MangaImageProxyError("Invalid manga image token") from e
    else:
        expires_at = payload.get("expires_at") if isinstance(payload, dict) else None

        if (
            not isinstance(expires_at, int)
            or isinstance(expires_at, bool)
        ):
            raise MangaImageProxyError("Invalid manga image token")

        if time.time() >= expires_at:
            raise SignatureExpired(
                "Manga image token has expired",
                payload=payload
            )

    if not isinstance(payload, dict):
        raise MangaImageProxyError("Invalid manga image token")

    url = payload.get("url")
    validate_manga_image_url(url)
    return url


def get_manga_image_resource_name(url: str, fallback: str = "page.webp") -> str:
    resource_name = unquote(urlsplit(url).path).rsplit("/", 1)[-1]
    resource_name = "".join(
        character
        if character.isalnum() or character in {".", "_", "-"}
        else "_"
        for character in resource_name
    )[:100]
    return resource_name or fallback


def get_manga_image_content_type(url: str, content_type: str) -> str:
    if isinstance(content_type, str) and content_type.lower().startswith("image/"):
        return content_type

    if not isinstance(content_type, str) or content_type.lower() != "application/octet-stream":
        return ""

    image_path = urlsplit(url).path.casefold()

    for extension, guessed_type in MANGA_IMAGE_CONTENT_TYPES.items():
        if image_path.endswith(extension):
            return guessed_type

    return ""


def build_manga_image_proxy_path(secret_key: str, url: str, fallback: str = "page.webp") -> str:
    token = create_manga_image_proxy_token(secret_key, url)
    resource_name = get_manga_image_resource_name(url, fallback)
    return f"/api/manga-images/{quote(token, safe='')}/{quote(resource_name, safe='')}"


def fetch_manga_image(url: str):
    validate_manga_image_url(url)

    try:
        return curl_requests.get(
            url,
            headers={
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Encoding": "identity",
                "Referer": "https://mangakatana.com/",
            },
            impersonate="chrome",
            timeout=30,
            allow_redirects=False,
            stream=True
        )
    except Exception as e:
        raise MangaImageProxyError("Unable to reach manga image host") from e
