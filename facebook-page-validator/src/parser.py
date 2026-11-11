"""Structural parser for Facebook's public page HTML.

Everything is located by *marker*, never by position. Facebook ships ~230
`<script type="application/json">` blocks per page and their order changes
between requests, so the parser walks every block looking for the keys that
name what they hold:

    profile_social_context.content[]   -> {text:{text:"39M followers"}, uri:.../followers/}
    field_section_type                 -> category | about_contact_info |
                                          websites_and_social_links | ...
    profile_fields.nodes[].field_type  -> category | profile_phone | website | email

A field that no marker resolves is returned as None. That is the whole point:
on a REDUCED payload the about sections are simply absent, and reporting null
is correct where guessing a nearby number is not.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import urllib.parse
from typing import Any, Iterator

JSON_BLOCK = re.compile(
    r'<script type="application/json"[^>]*>(.*?)</script>', re.S
)

# "39M followers" / "1,234 followers" / "28K followers"
COUNT_TEXT = re.compile(r"^([\d][\d.,]*)\s*([KMB])?\s+\S+", re.I)

MULTIPLIER = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def iter_json_blocks(html: str) -> Iterator[Any]:
    """Yield every embedded JSON block that parses. Malformed blocks are skipped."""
    for raw in JSON_BLOCK.findall(html):
        try:
            yield json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue


def walk(node: Any) -> Iterator[dict]:
    """Depth-first walk yielding every dict in the tree."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def text_of(node: Any) -> str | None:
    """Unwrap Facebook's {text: {..., text: "..."}} envelope."""
    if isinstance(node, str):
        return node or None
    if isinstance(node, dict):
        inner = node.get("text")
        if isinstance(inner, str):
            return inner or None
        if isinstance(inner, dict):
            return text_of(inner)
    return None


def parse_count(label: str | None) -> int | None:
    """"39M followers" -> 39000000. Returns None when the shape is unfamiliar.

    Abbreviated counts are approximations on Facebook's side; the raw label is
    always kept alongside so a buyer can see what was actually rendered.
    """
    if not label:
        return None
    match = COUNT_TEXT.match(label.strip())
    if not match:
        return None
    number, suffix = match.groups()
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    if suffix:
        value *= MULTIPLIER[suffix.upper()]
    return int(value)


def unwrap_link(url: str | None) -> str | None:
    """Undo Facebook's l.php redirect wrapper.

    Outbound links are rewritten to l.facebook.com/l.php?u=<encoded>&h=<token>,
    which is useless to a buyer: the token is per-render, so the wrapped URL is
    not even stable between two fetches of the same page.
    """
    if not url:
        return None
    if "/l.php" not in url and "l.facebook.com" not in url:
        return url
    try:
        query = urllib.parse.urlparse(url).query
        target = urllib.parse.parse_qs(query).get("u", [None])[0]
    except ValueError:
        return url
    return target or url


def decode_page_id(encoded: str) -> str | None:
    """Recover the numeric page id from a base64 node id.

    'profile_field_section:100044541544829:category' is base64-encoded into the
    section id, which makes it the one page-id source that survives on pages
    where the header renderer is absent.
    """
    try:
        decoded = base64.b64decode(encoded + "==", validate=False).decode("utf-8", "ignore")
    except (binascii.Error, ValueError):
        return None
    found = re.search(r"(\d{8,20})", decoded)
    return found.group(1) if found else None


def extract_social_context(blocks: list[Any]) -> dict:
    """Follower and following counts, keyed off the link each row points at."""
    out: dict[str, Any] = {}
    for block in blocks:
        for node in walk(block):
            content = node.get("profile_social_context")
            if not isinstance(content, dict):
                continue
            for row in content.get("content") or []:
                if not isinstance(row, dict):
                    continue
                uri = row.get("uri") or ""
                label = text_of(row.get("text"))
                if "/followers" in uri:
                    out["followersLabel"] = label
                    out["followers"] = parse_count(label)
                elif "/following" in uri:
                    out["followingLabel"] = label
                    out["following"] = parse_count(label)
    return out


def extract_about_fields(blocks: list[Any]) -> dict:
    """Categories, phone, website, email and address from the about tab."""
    categories: list[str] = []
    websites: list[str] = []
    emails: list[str] = []
    phones: list[str] = []
    addresses: list[str] = []
    page_id: str | None = None

    for block in blocks:
        for node in walk(block):
            section_type = node.get("field_section_type")
            if not section_type:
                continue
            if page_id is None and isinstance(node.get("id"), str):
                page_id = decode_page_id(node["id"])
            fields = node.get("profile_fields") or {}
            for field in fields.get("nodes") or []:
                if not isinstance(field, dict):
                    continue
                value = text_of(field.get("title"))
                if not value:
                    continue
                field_type = field.get("field_type") or ""
                if field_type == "category":
                    categories.append(value)
                elif field_type == "website":
                    # The rendered title is the clean URL; link_url is wrapped.
                    websites.append(unwrap_link(field.get("link_url")) or value)
                elif field_type == "email":
                    emails.append(value)
                elif "phone" in field_type:
                    phones.append(value)
                elif "address" in field_type or "location" in field_type:
                    addresses.append(value)

    def dedupe(items: list[str]) -> list[str]:
        return list(dict.fromkeys(i.strip() for i in items if i and i.strip()))

    return {
        "pageId": page_id,
        "categories": dedupe(categories),
        "websites": dedupe(websites),
        "emails": dedupe(emails),
        "phones": dedupe(phones),
        "addresses": dedupe(addresses),
    }


def extract_name(html: str, blocks: list[Any]) -> str | None:
    """Page name, preferring the OpenGraph tag and falling back to <title>."""
    og = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if og:
        return og.group(1).strip() or None
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
    if title:
        cleaned = re.sub(r"\s*\|\s*Facebook\s*$", "", title.group(1)).strip()
        return cleaned or None
    return None


def count_posts(blocks: list[Any]) -> int:
    """How many feed stories the payload actually carried.

    Used to justify the tier, not as an engagement metric: on a REDUCED payload
    this is 0 for pages that post every day.
    """
    seen: set[int] = set()
    for block in blocks:
        for node in walk(block):
            stamp = node.get("creation_time")
            if isinstance(stamp, int) and 1_000_000_000 < stamp < 4_000_000_000:
                seen.add(stamp)
    return len(seen)


def parse_page(html: str) -> dict:
    """Parse one page's HTML into a flat record of whatever could be located."""
    blocks = list(iter_json_blocks(html))
    record: dict[str, Any] = {"name": extract_name(html, blocks)}
    record.update(extract_social_context(blocks))
    record.update(extract_about_fields(blocks))

    # Fill only what the structural pass could not find; og: data is a summary,
    # so it must never overwrite a value read from the real profile fields.
    for key, value in parse_og_description(html).items():
        if record.get(key) in (None, [], ""):
            record[key] = value
    if not record.get("categories") and record.get("ogCategory"):
        record["categories"] = [record["ogCategory"]]

    record["postsInPayload"] = count_posts(blocks)
    record["_jsonBlocks"] = len(blocks)
    return record


# -- og:description fallback --------------------------------------------------
# Facebook packs a compact summary into the OpenGraph description:
#     "Eoddata beeip.com. 124 followers. App Page"
# It survives on REDUCED payloads where the about sections are missing entirely,
# which makes it the difference between a null record and a usable one.
OG_DESCRIPTION = re.compile(
    r'<meta property="og:description" content="([^"]*)"'
)


def parse_og_description(html: str) -> dict:
    """Pull follower count and category out of the OpenGraph summary line."""
    match = OG_DESCRIPTION.search(html)
    if not match:
        return {}
    raw = match.group(1)
    parts = [p.strip() for p in raw.split(".") if p.strip()]
    out: dict[str, Any] = {"ogDescription": raw}
    for part in parts:
        lowered = part.lower()
        if lowered.endswith("followers") or lowered.endswith("follower"):
            out["followersLabel"] = part
            out["followers"] = parse_count(part)
        elif lowered.endswith("likes") or lowered.endswith("like"):
            out["likesLabel"] = part
            out["likes"] = parse_count(part)
    # The trailing segment is the page category when Facebook includes one.
    if len(parts) >= 3 and not parts[-1].lower().endswith(("followers", "follower")):
        out["ogCategory"] = parts[-1]
    return out
