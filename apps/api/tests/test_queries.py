from eyohe.core.enums import TargetType
from eyohe.search.queries import generate_branches, is_query_allowed


def test_domain_branches_include_site_operators() -> None:
    b = generate_branches(TargetType.DOMAIN, "example.com", objective="identify infrastructure and employees")
    qs = [x.query for x in b]
    assert "site:example.com" in qs
    assert any("site:github.com" in q for q in qs)
    assert any("filetype:pdf" in q for q in qs)
    assert any(x.category == "news" for x in b)
    assert any("infrastructure" in q for q in qs)  # objective keywords add a focused branch


def test_credential_hunting_dorks_are_refused() -> None:
    assert not is_query_allowed("example.com filetype:env")[0]
    assert not is_query_allowed('intext:"password" site:example.com')[0]
    assert not is_query_allowed('"BEGIN RSA PRIVATE KEY" example.com')[0]
    assert is_query_allowed('"example.com" site:reddit.com')[0]
    assert is_query_allowed('"Acme" filetype:pdf')[0]
