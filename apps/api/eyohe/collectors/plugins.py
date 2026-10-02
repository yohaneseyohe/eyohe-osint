"""Built-in collector plugins. Add third-party collectors by subclassing BaseCollector and
appending an instance here (or calling collector_registry.register at import time)."""

from __future__ import annotations

from eyohe.collectors.base import BaseCollector
from eyohe.collectors.ct_collector import CTLogCollector
from eyohe.collectors.dns_collector import DNSCollector
from eyohe.collectors.github_collector import GitHubCollector
from eyohe.collectors.ip_collector import IPInfoCollector
from eyohe.collectors.rdap_collector import RDAPCollector
from eyohe.collectors.reddit_collector import RedditCollector
from eyohe.collectors.social_collector import SocialProfileCollector
from eyohe.collectors.wayback_collector import WaybackCollector
from eyohe.collectors.web_collector import WebFetchCollector

BUILTIN_COLLECTORS: list[BaseCollector] = [
    DNSCollector(),
    RDAPCollector(),
    CTLogCollector(),
    IPInfoCollector(),
    WebFetchCollector(),
    WaybackCollector(),
    GitHubCollector(),
    RedditCollector(),
    SocialProfileCollector(),
]
