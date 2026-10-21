"""
Network safety checks shared by the signed proxies. Signed tokens already prevent arbitrary URLs;
these checks additionally keep proxied hosts on public addresses and ranges well formed.
"""
import ipaddress
import re
import socket


MAX_RANGE_HEADER_LENGTH = 100


def require_public_host(hostname: str, error_class: type[Exception], label: str):
    """
    Raises error_class unless hostname resolves only to public addresses. `label` names the host, e.g. "AniDB stream".
    """
    try:
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise error_class(f"Unable to resolve {label} host") from e

    if not addresses:
        raise error_class(f"Unable to resolve {label} host")

    for address in addresses:
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise error_class(f"{label[:1].upper()}{label[1:]} host must resolve to a public address")


def validate_range_header(range_header: str | None, pattern: re.Pattern, error_class: type[Exception]) -> str | None:
    if range_header is None:
        return None

    if len(range_header) > MAX_RANGE_HEADER_LENGTH or pattern.fullmatch(range_header) is None:
        raise error_class("Invalid Range header")

    return range_header
