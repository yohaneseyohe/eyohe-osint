import pytest

from eyohe.core.errors import UnsafeURLError
from eyohe.core.netsafety import validate_host, validate_url_syntax


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/x",
        "file:///etc/passwd",
        "http://user:pass@example.com/",
        "http:///nohost",
        "gopher://example.com",
    ],
)
def test_bad_schemes_and_credentials(url: str) -> None:
    with pytest.raises(UnsafeURLError):
        validate_url_syntax(url)


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.1",
        "172.16.0.9",
        "169.254.169.254",
        "0.0.0.0",
        "localhost",
        "metadata.google.internal",
        "::1",
        "fe80::1",
        "fd00::1",
        "100.64.0.1",
        "intranet.corp",
        "printer.local",
        "::ffff:127.0.0.1",
    ],
)
def test_private_hosts_blocked(host: str) -> None:
    with pytest.raises(UnsafeURLError):
        validate_host(host, allow_private=False)


def test_public_ip_allowed() -> None:
    validate_host("93.184.216.34", allow_private=False)
    validate_host("example.com", allow_private=False)


def test_private_allowed_when_explicitly_enabled() -> None:
    validate_host("127.0.0.1", allow_private=True)
