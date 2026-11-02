"""URL checks copied from prosperos-study server/providers/config.py at bbcbde4, and how a model call reaches its
service."""
import logging
import os
import ssl
from functools import cache
from ipaddress import ip_address
from urllib.parse import urlsplit

import certifi

from dungeon.errors import DomainError

log = logging.getLogger('dungeon')


def is_loopback(host: str | None) -> bool:
    if host == 'localhost':
        return True
    try:
        return ip_address(host or '').is_loopback
    except ValueError:
        return False


def validate_compatible_url(url: str):
    parts = urlsplit(url)
    if not parts.hostname or (parts.scheme != 'https' and not (parts.scheme == 'http' and is_loopback(parts.hostname))):
        raise DomainError('Use an HTTPS API base URL, or HTTP for a loopback service.', 422)
    if any((parts.username, parts.password, parts.query, parts.fragment)):
        raise DomainError('Put credentials in the API key field, not in the server address.', 422)
    if parts.port == 0:
        raise DomainError('Use a valid service port.', 422)


def network(base_url: str) -> dict:
    """httpx client options for a model call to `base_url`. A service on this computer is reached directly. A hosted
    one goes through the proxy the system names (HTTPS_PROXY, ALL_PROXY, NO_PROXY) and trusts the system's certificate
    authorities and SSL_CERT_FILE / SSL_CERT_DIR besides httpx's own list, so it works behind a proxy at work that
    inspects TLS. Nothing about the request (its key least of all) is logged here."""
    if is_loopback(urlsplit(base_url).hostname):
        return {'trust_env': False}
    return {'trust_env': True, 'verify': trusted(os.environ.get('SSL_CERT_FILE') or None,
                                                 os.environ.get('SSL_CERT_DIR') or None)}


@cache
def trusted(cafile: str | None, capath: str | None) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_default_certs()
    if cafile or capath:
        try:
            context.load_verify_locations(cafile=cafile, capath=capath)
        except (OSError, ssl.SSLError) as error:
            log.warning('The certificates in SSL_CERT_FILE / SSL_CERT_DIR could not be read: %s', error)
    return context
