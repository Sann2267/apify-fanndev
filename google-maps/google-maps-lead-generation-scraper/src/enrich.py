"""Enrichment: mine a business website for emails and social accounts.

This is the step that turns a Maps listing into an outreach-ready lead, since
Google itself never exposes an email address.

Two things make the difference between useful output and noise:

* **Share widgets are not accounts.** Almost every site embeds a Facebook share
  button and a Twitter intent link, so a naive regex reports that every business
  has a Facebook page called "sharer". Known widget paths are filtered out.
* **Homepages often have no email.** The address usually lives on a contact
  page, so when the homepage yields nothing we follow one same-domain
  contact-ish link. One hop only -- this is enrichment, not a crawl.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlparse

from src.client import MapsClient
from src.constants import (
    CONTACT_PAGE_HINTS,
    ENRICH_TIMEOUT,
    MAX_ENRICH_BYTES,
    SOCIAL_PATH_BLOCKLIST,
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")
# Cloudflare and similar obfuscate addresses; these are never real inboxes.
EMAIL_REJECT_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css",
                       ".js", ".ico", ".mp4", ".pdf", ".woff", ".woff2")
EMAIL_REJECT_SUBSTR = ("example.com", "yourdomain", "domain.com", "email.com",
                       "sentry.io", "wixpress.com", "@2x", "@3x", "@media")

SOCIAL_PATTERNS = {
    "instagram": re.compile(r"https?://(?:[a-z]{2,3}\.)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]{2,40})"),
    "facebook": re.compile(r"https?://(?:[a-z]{2,3}-[a-z]{2}\.|www\.|m\.|web\.)?facebook\.com/([A-Za-z0-9_.\-]{2,60})"),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]{2,20})"),
    "linkedin": re.compile(r"https?://(?:[a-z]{2,3}\.)?(?:www\.)?linkedin\.com/(?:company|in|school)/([A-Za-z0-9_\-%.]{2,60})"),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@|c/|channel/|user/)([A-Za-z0-9_\-]{2,60})"),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]{2,40})"),
    "whatsapp": re.compile(r"https?://(?:api\.whatsapp\.com/send\?phone=|wa\.me/)(\d{6,20})"),
    "telegram": re.compile(r"https?://(?:www\.)?t\.me/([A-Za-z0-9_]{3,40})"),
}
TEL_RE = re.compile(r"tel:\+?([\d\-\s().]{6,25})")
LINK_RE = re.compile(r'href=["\']([^"\']{1,300})["\']', re.IGNORECASE)


def _valid_email(value: str) -> bool:
    low = value.lower()
    if low.endswith(EMAIL_REJECT_SUFFIX):
        return False
    return not any(bad in low for bad in EMAIL_REJECT_SUBSTR)


def extract_contacts(html: str) -> dict:
    """Pull emails, socials and tel: numbers out of one page of HTML."""
    text = unescape(html[:MAX_ENRICH_BYTES])

    emails = sorted({e.lower() for e in EMAIL_RE.findall(text) if _valid_email(e)})

    socials: dict[str, list[str]] = {}
    for network, pattern in SOCIAL_PATTERNS.items():
        handles = []
        for handle in pattern.findall(text):
            clean = handle.strip("/.").split("?")[0]
            if not clean or clean.lower() in SOCIAL_PATH_BLOCKLIST:
                continue
            if clean not in handles:
                handles.append(clean)
        if handles:
            socials[network] = handles[:5]

    phones = sorted({re.sub(r"[^\d+]", "", p) for p in TEL_RE.findall(text)
                     if len(re.sub(r"[^\d]", "", p)) >= 7})

    return {"emails": emails, "socialProfiles": socials, "websitePhones": phones[:5]}


def find_contact_page(html: str, base_url: str) -> str | None:
    """Pick one same-domain contact-ish link to follow."""
    base_host = (urlparse(base_url).hostname or "").lower().lstrip("www.")
    best = None
    for href in LINK_RE.findall(html[:MAX_ENRICH_BYTES]):
        href = unescape(href).strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        low = href.lower()
        if not any(hint in low for hint in CONTACT_PAGE_HINTS):
            continue
        absolute = urljoin(base_url, href)
        host = (urlparse(absolute).hostname or "").lower().lstrip("www.")
        if host and base_host and host != base_host:
            continue          # never wander off the business's own domain
        if absolute.rstrip("/") == base_url.rstrip("/"):
            continue
        # Prefer an explicit contact page over a generic "about".
        if any(h in low for h in ("contact", "kontak", "hubungi")):
            return absolute
        best = best or absolute
    return best


def _merge(primary: dict, extra: dict) -> dict:
    merged = {
        "emails": sorted(set(primary["emails"]) | set(extra["emails"])),
        "websitePhones": sorted(set(primary["websitePhones"]) | set(extra["websitePhones"])),
        "socialProfiles": dict(primary["socialProfiles"]),
    }
    for network, handles in extra["socialProfiles"].items():
        existing = merged["socialProfiles"].setdefault(network, [])
        for handle in handles:
            if handle not in existing:
                existing.append(handle)
    return merged


async def enrich_website(client: MapsClient, website: str, follow_contact: bool = True) -> dict:
    """Fetch a business website and mine it for contact details.

    Never raises: a lead whose site is dead, slow or hostile still has to reach
    the dataset with its Maps data intact, so failures are reported in the
    record rather than thrown.
    """
    result: dict = {
        "emails": [], "socialProfiles": {}, "websitePhones": [],
        "enrichmentStatus": "not_attempted", "enrichmentPagesFetched": 0,
        "enrichmentFinalUrl": None,
    }
    if not website:
        return result

    url = website if website.startswith("http") else f"https://{website}"
    try:
        status, final_url, html = await client.get_text(url, timeout=ENRICH_TIMEOUT)
    except Exception as exc:
        result["enrichmentStatus"] = f"fetch_failed:{type(exc).__name__}"
        return result

    result["enrichmentFinalUrl"] = final_url
    result["enrichmentPagesFetched"] = 1
    if status >= 400:
        result["enrichmentStatus"] = f"http_{status}"
        return result

    found = extract_contacts(html)
    result.update(found)
    result["enrichmentStatus"] = "ok"

    # Only spend a second request when the homepage gave us no email.
    if follow_contact and not found["emails"]:
        contact_url = find_contact_page(html, final_url)
        if contact_url:
            try:
                status2, _, html2 = await client.get_text(contact_url, timeout=ENRICH_TIMEOUT)
                result["enrichmentPagesFetched"] = 2
                if status2 < 400:
                    merged = _merge(found, extract_contacts(html2))
                    result.update(merged)
                    result["enrichmentStatus"] = "ok_contact_page"
            except Exception:
                # The contact hop is a bonus; its failure must not downgrade
                # what the homepage already gave us.
                pass

    return result
