"""Match a fetched page against the fingerprint table."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from src.fingerprints import CATEGORIES, FINGERPRINTS

SCRIPT_SRC = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)
LINK_HREF = re.compile(r'<link[^>]+href=["\']([^"\']+)["\']', re.I)
IFRAME_SRC = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)
META_GENERATOR = re.compile(
    r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']*)["\']', re.I
)
# Some sites emit the attributes the other way round.
META_GENERATOR_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']generator["\']', re.I
)


def asset_urls(html: str) -> list[str]:
    """Every externally referenced asset URL in the document."""
    return SCRIPT_SRC.findall(html) + LINK_HREF.findall(html) + IFRAME_SRC.findall(html)


def asset_hosts(urls: list[str], page_url: str) -> set[str]:
    """Hostnames referenced by the page, excluding its own."""
    own = (urlparse(page_url).hostname or "").lower()
    hosts: set[str] = set()
    for raw in urls:
        candidate = raw.strip()
        if candidate.startswith("//"):
            candidate = "https:" + candidate
        if not candidate.lower().startswith(("http://", "https://")):
            continue  # relative asset: same origin, tells us nothing about vendors
        host = (urlparse(candidate).hostname or "").lower()
        if host and host != own:
            hosts.add(host)
    return hosts


def generators(html: str) -> list[str]:
    return [g.strip() for g in META_GENERATOR.findall(html) + META_GENERATOR_ALT.findall(html) if g.strip()]


class Evidence:
    """Everything a page offers up, indexed once so 167 signals stay cheap."""

    def __init__(self, html: str, headers: dict, cookies: list[str], page_url: str) -> None:
        self.html = html
        self.html_lower = html.lower()
        self.headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        self.cookies = list(cookies or [])
        self.cookies_lower = {c.lower() for c in self.cookies}
        self.urls = asset_urls(html)
        # Matching against the raw asset URLs as well as the hostnames lets a
        # path-bearing fingerprint work (cdn.jsdelivr.net/npm/algoliasearch),
        # which a hostname-only index would miss.
        self.asset_blob = " ".join(self.urls).lower()
        self.hosts = asset_hosts(self.urls, page_url)
        self.generators = generators(html)
        self.generators_lower = [g.lower() for g in self.generators]

    def match_header(self, spec: str) -> str | None:
        name, _, wanted = spec.partition(":")
        value = self.headers.get(name.lower())
        if value is None:
            return None
        if wanted and wanted.lower() not in value.lower():
            return None
        return f"{name}: {value[:120]}"

    def match_cookie(self, name: str) -> str | None:
        if name.lower() in self.cookies_lower:
            return f"cookie {name}"
        return None

    def match_generator(self, needle: str) -> str | None:
        for original, lowered in zip(self.generators, self.generators_lower):
            if needle.lower() in lowered:
                return f'meta generator "{original[:80]}"'
        return None

    def match_host(self, needle: str) -> str | None:
        wanted = needle.lower()
        # An exact host match, or a subdomain of it, but never a coincidental
        # substring: "shop.app" must not be satisfied by "myshop.apple.com".
        for host in self.hosts:
            if host == wanted or host.endswith("." + wanted):
                return f"asset host {host}"
        if "/" in wanted and wanted in self.asset_blob:
            return f"asset url containing {needle}"
        return None

    def match_html(self, needle: str) -> str | None:
        if needle.lower() in self.html_lower:
            return f'html contains "{needle[:60]}"'
        return None

    def match(self, signal_type: str, value: str) -> str | None:
        handler = {
            "header": self.match_header,
            "cookie": self.match_cookie,
            "generator": self.match_generator,
            "host": self.match_host,
            "html": self.match_html,
        }.get(signal_type)
        return handler(value) if handler else None


def detect(html: str, headers: dict, cookies: list[str], page_url: str) -> list[dict]:
    """Return one entry per detected technology, strongest evidence first."""
    evidence = Evidence(html, headers, cookies, page_url)
    results: list[dict] = []

    for entry in FINGERPRINTS:
        matched: list[dict] = []
        for signal_type, value, confidence in entry["signals"]:
            hit = evidence.match(signal_type, value)
            if hit:
                matched.append({"type": signal_type, "confidence": confidence, "evidence": hit})
        if not matched:
            continue
        confirmed = any(m["confidence"] == "confirmed" for m in matched)
        results.append({
            "technology": entry["name"],
            "category": entry["category"],
            "categoryLabel": CATEGORIES.get(entry["category"], entry["category"]),
            "confidence": "confirmed" if confirmed else "likely",
            "signalCount": len(matched),
            "evidence": [m["evidence"] for m in matched],
            "signalTypes": sorted({m["type"] for m in matched}),
        })

    results.sort(
        key=lambda r: (r["confidence"] != "confirmed", -r["signalCount"], r["technology"])
    )
    return results


def summarise_stack(detections: list[dict]) -> dict[str, Any]:
    """Flatten detections into the columns a spreadsheet user filters on."""
    by_category: dict[str, list[str]] = {}
    for item in detections:
        by_category.setdefault(item["category"], []).append(item["technology"])

    confirmed = [d["technology"] for d in detections if d["confidence"] == "confirmed"]
    return {
        "technologies": [d["technology"] for d in detections],
        "technologiesConfirmed": confirmed,
        "technologyCount": len(detections),
        "confirmedCount": len(confirmed),
        "categoriesDetected": sorted(by_category),
        # One column per category keeps the CSV usable: "show me every
        # prospect whose Ecommerce column says Shopify" is one filter, not a
        # search through a packed list.
        **{f"stack{category.replace(' ', '')}": ", ".join(names)
           for category, names in by_category.items()},
    }
