import pytest

from eyohe.core.enums import TargetType
from eyohe.enrichment.classify import classify_target


@pytest.mark.parametrize(
    "raw,expected,norm",
    [
        ("example.com", TargetType.DOMAIN, "example.com"),
        ("Sub.Example.COM.", TargetType.DOMAIN, "sub.example.com"),
        ("8.8.8.8", TargetType.IP, "8.8.8.8"),
        ("2001:4860:4860::8888", TargetType.IP, "2001:4860:4860::8888"),
        ("Someone@Example.com", TargetType.EMAIL, "someone@example.com"),
        ("https://www.instagram.com/some_handle/", TargetType.SOCIAL_ACCOUNT, "instagram:some_handle"),
        ("https://github.com/octocat", TargetType.SOCIAL_ACCOUNT, "github:octocat"),
        ("https://www.reddit.com/u/demo_user_42/", TargetType.SOCIAL_ACCOUNT, "reddit:demo_user_42"),
        ("https://example.com/blog/post?utm_source=x", TargetType.URL, "https://example.com/blog/post"),
        ("@eyohe123", TargetType.USERNAME, "eyohe123"),
        ("eyohe123", TargetType.USERNAME, "eyohe123"),
        ("Acme Technologies Inc", TargetType.ORGANIZATION, "Acme Technologies Inc"),
        ("Jane Doe", TargetType.PERSON, "Jane Doe"),
        ("org:Blue Harbor", TargetType.ORGANIZATION, "Blue Harbor"),
        (
            "0x52908400098527886E0F7030069857D2E4169EE7",
            TargetType.CRYPTO_ADDRESS,
            "0x52908400098527886E0F7030069857D2E4169EE7",
        ),
        ("+1 (415) 555-0100", TargetType.PHONE, "+14155550100"),
    ],
)
def test_classify(raw: str, expected: TargetType, norm: str) -> None:
    t, n, _ = classify_target(raw)
    assert t == expected
    assert n == norm
