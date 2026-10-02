from eyohe.core.urlnorm import normalize_url, registrable_domain


def test_normalize_strips_tracking_fragment_and_default_port() -> None:
    a = normalize_url("HTTPS://Example.COM:443/Path/?utm_source=x&b=2&a=1#frag")
    assert a == "https://example.com/Path?a=1&b=2"


def test_normalize_trailing_slash_and_scheme_default() -> None:
    assert normalize_url("example.com/") == "http://example.com/"
    assert normalize_url("http://example.com/a/") == "http://example.com/a"
    assert normalize_url("http://example.com//a//b") == "http://example.com/a/b"


def test_same_page_from_two_engines_dedupes() -> None:
    assert normalize_url("https://github.com/foo/bar?ref=search") == normalize_url("https://github.com/foo/bar/")


def test_registrable_domain() -> None:
    assert registrable_domain("https://docs.sub.example.co.uk/x") == "example.co.uk"
