"""How model calls reach their service (dungeon/providers/urls.py `network`): a hosted one through the system's
proxy and certificate authorities, one on this computer directly."""
import asyncio
import datetime
import ssl

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from dungeon.providers import chat, urls
from dungeon.providers.chat import ChatProvider


def company_ca(path) -> str:
    """A CA a TLS-inspecting proxy at work would sign with, written as PEM."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Example Corp Inspection CA')])
    now = datetime.datetime.now(datetime.UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(key, hashes.SHA256()))
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(path)


def test_a_service_on_this_computer_is_reached_directly():
    for url in ('http://127.0.0.1:1234/v1', 'http://localhost:5001/api/v1', 'http://[::1]:8080/v1'):
        assert urls.network(url) == {'trust_env': False}


def test_a_hosted_service_uses_the_proxy_and_the_certificates_the_system_names(tmp_path, monkeypatch):
    monkeypatch.setenv('SSL_CERT_FILE', company_ca(tmp_path / 'corp.pem'))
    options = urls.network('https://openrouter.ai/api/v1')
    assert options['trust_env'] is True and isinstance(options['verify'], ssl.SSLContext)
    subjects = [dict(item[0] for item in cert['subject']).get('commonName') for cert in options['verify'].get_ca_certs()]
    assert 'Example Corp Inspection CA' in subjects
    assert len(subjects) > 1, "httpx's own list stays trusted too"


def test_hosted_chat_goes_through_the_proxy(monkeypatch):
    seen = []
    real = httpx.AsyncClient

    def client(**options):
        seen.append(options)
        return real(**options)

    monkeypatch.setattr(chat.httpx, 'AsyncClient', client)
    provider = ChatProvider(httpx.MockTransport(lambda request: httpx.Response(200, json={'data': []})))

    async def check(base_url):
        try:
            await provider.check({'provider': 'compatible', 'base_url': base_url, 'model': 'm', 'timeout_seconds': 5},
                                 'sk-test')
        except Exception:  # noqa: BLE001 - only the client options matter here
            pass

    asyncio.run(check('https://openrouter.ai/api/v1'))
    asyncio.run(check('http://127.0.0.1:1234/v1'))
    assert [options['trust_env'] for options in seen] == [True, False]
