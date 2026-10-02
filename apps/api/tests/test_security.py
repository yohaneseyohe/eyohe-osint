from eyohe.core.logging import contains_secret, redact_text
from eyohe.core.security import hash_password, verify_password


def test_password_hash_roundtrip() -> None:
    h = hash_password("CorrectHorse9Battery")
    assert h.startswith("$argon2id$")
    assert verify_password("CorrectHorse9Battery", h)
    assert not verify_password("nope", h)


def test_redaction() -> None:
    text = "token=ghp_FAKEFAKEFAKEFAKEFAKEFAKEFAKE00 and api_key: supersecret123 AKIAFAKEFAKEFAKEFAKE"
    out = redact_text(text)
    assert "ghp_" not in out and "supersecret123" not in out and "AKIAFAKEFAKEFAKEFAKE" not in out
    assert contains_secret("ghp_FAKEFAKEFAKEFAKEFAKEFAKEFAKE00")
    assert not contains_secret("hello world")
