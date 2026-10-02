from eyohe.core.enums import EntityType
from eyohe.enrichment.extract import extract_entities


def test_extracts_emails_domains_urls_ips_handles_and_socials() -> None:
    text = (
        "Contact hello@example-labs.test or visit https://example-labs.test/about. "
        "Code: https://github.com/acme-example-labs/demo-site and https://twitter.com/acme_labs. "
        "Server 93.184.216.34 and 2606:2800:220:1:248:1893:25c8:1946; follow @acme_labs. "
        "Ignore styles.css and image.png. Wallet 0x52908400098527886E0F7030069857D2E4169EE7."
    )
    ents = extract_entities(text)
    by = {(e.type, e.value) for e in ents}
    assert (EntityType.EMAIL, "hello@example-labs.test") in by
    assert (EntityType.URL, "https://example-labs.test/about") in by
    assert (EntityType.REPOSITORY, "acme-example-labs/demo-site") in by
    assert (EntityType.SOCIAL_ACCOUNT, "github:acme-example-labs") in by
    assert (EntityType.SOCIAL_ACCOUNT, "x:acme_labs") in by
    assert (EntityType.IP, "93.184.216.34") in by
    assert (EntityType.IP, "2606:2800:220:1:248:1893:25c8:1946") in by
    assert (EntityType.USERNAME, "acme_labs") in by
    assert (EntityType.CRYPTO_ADDRESS, "0x52908400098527886E0F7030069857D2E4169EE7") in by
    assert not any(v in ("styles.css", "image.png") for t, v in by if t == EntityType.DOMAIN)


def test_private_ips_are_ignored() -> None:
    ents = extract_entities("hosts 10.0.0.1 and 127.0.0.1 and 192.168.1.5")
    assert not [e for e in ents if e.type == EntityType.IP]
