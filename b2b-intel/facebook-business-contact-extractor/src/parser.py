"""Extract a business page's public contact details from its about tab.

Everything is located by the key that names it, never by position: Facebook
ships ~230 `<script type="application/json">` blocks per page and reorders them
between requests. The shape that matters is

    field_section_type            category | about_contact_info | ...
      profile_fields.nodes[]
        field_type                category | profile_phone | profile_email |
                                  website | address | business_hours |
                                  business_price | business_services |
                                  screenname | ratings
        title.text                the rendered value

A field no marker resolves is emitted as null. On this surface that distinction
is the product: "this business publishes no email" and "we could not find the
email" are different facts, and a lead list that conflates them is worthless.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from src.fbcore import (
    dedupe,
    decode_b64_id,
    iter_json_blocks,
    og_tag,
    parse_count,
    text_of,
    unwrap_link,
    walk,
)

PAGE_SLUG = re.compile(r"facebook\.com/(?:pg/)?([^/?#]+)", re.I)
RESERVED = {"profile.php", "people", "groups", "events", "marketplace", "watch", "ads",
            "pages", "search", "photo", "reel"}
EMAIL_IN_TEXT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
# "96% recommend (5,939 reviews)"
RATING = re.compile(r"(\d[\d.,]*)\s*%\s*recommend\s*\(([\d.,]+)\s*review", re.I)


def page_ref(value: str) -> str | None:
    """Reduce a page URL or slug to the bare vanity slug."""
    value = (value or "").strip()
    if not value:
        return None
    match = PAGE_SLUG.match(value) or PAGE_SLUG.search(value)
    if match:
        value = match.group(1)
    value = value.strip("/").split("?")[0].split("#")[0]
    if not value or value.lower() in RESERVED:
        return None
    return value


def _list_items(field: dict) -> list[str]:
    out = []
    for group in field.get("list_item_groups") or []:
        for item in group.get("list_items") or []:
            label = text_of(item.get("text"))
            if label:
                out.append(label)
    return out


def parse_about(html: str) -> dict:
    """One page's about tab -> a flat contact record."""
    record: dict[str, Any] = {
        "pageName": None,
        "pageId": None,
        "categories": [],
        "emails": [],
        "phones": [],
        "websites": [],
        "addresses": [],
        "socialHandles": [],
        "services": [],
        "hoursLabel": None,
        "priceRange": None,
        "ratingSummaryText": None,
        "recommendPercent": None,
        "reviewCount": None,
        "followers": None,
        "followersLabel": None,
        "likes": None,
    }

    raw_name = og_tag(html, "og:title")
    if raw_name:
        record["pageName"] = re.sub(r"\s*\|\s*Facebook\s*$", "", raw_name).strip() or None

    for block in iter_json_blocks(html):
        for node in walk(block):
            social = node.get("profile_social_context")
            if isinstance(social, dict):
                for row in social.get("content") or []:
                    if not isinstance(row, dict):
                        continue
                    uri = row.get("uri") or ""
                    label = text_of(row.get("text"))
                    if "/followers" in uri:
                        record["followersLabel"] = label
                        record["followers"] = parse_count(label)

            if not node.get("field_section_type"):
                continue
            if record["pageId"] is None and isinstance(node.get("id"), str):
                record["pageId"] = decode_b64_id(node["id"])

            for field in (node.get("profile_fields") or {}).get("nodes") or []:
                if not isinstance(field, dict):
                    continue
                field_type = field.get("field_type") or ""
                value = text_of(field.get("title"))
                if not value:
                    continue

                if field_type == "category":
                    record["categories"].append(value)
                elif field_type == "website":
                    # The rendered title is the clean URL; link_url is wrapped in
                    # l.facebook.com with a token that changes between fetches.
                    record["websites"].append(unwrap_link(field.get("link_url")) or value)
                elif field_type == "profile_email" or field_type == "email":
                    record["emails"].append(value)
                elif "phone" in field_type:
                    record["phones"].append(value)
                elif "address" in field_type or field_type == "location":
                    record["addresses"].append(value)
                elif field_type == "business_hours":
                    record["hoursLabel"] = value
                elif field_type == "business_price":
                    record["priceRange"] = value
                elif field_type == "business_services":
                    record["services"] = [s.strip() for s in re.split(r"·|·", value)
                                          if s.strip()]
                elif field_type == "screenname":
                    handle = value
                    for label in _list_items(field):
                        handle = f"{label}: {value}"
                        break
                    record["socialHandles"].append(handle)
                elif field_type == "ratings":
                    record["ratingSummaryText"] = value
                    match = RATING.search(value)
                    if match:
                        try:
                            record["recommendPercent"] = float(match.group(1).replace(",", ""))
                        except ValueError:
                            pass
                        try:
                            record["reviewCount"] = int(match.group(2).replace(",", ""))
                        except ValueError:
                            pass
                elif field_type == "page_id" and record["pageId"] is None:
                    record["pageId"] = value

    # An email printed in the page's own description is public information the
    # structured field often omits. It is collected, but tagged by where it came
    # from so a buyer can tell a declared contact from a scraped one.
    description = og_tag(html, "og:description") or ""
    scraped = [e for e in EMAIL_IN_TEXT.findall(description)
               if e.lower() not in {x.lower() for x in record["emails"]}]
    record["emailsFromDescription"] = dedupe(scraped)

    for key in ("categories", "emails", "phones", "websites", "addresses",
                "socialHandles", "services"):
        record[key] = dedupe(record[key])
    return record


def parse_transparency(html: str) -> dict:
    """The page transparency tab: numeric id, creation date, advertising status."""
    out: dict[str, Any] = {
        "pageCreationDate": None,
        "isRunningAds": None,
        "adStatusText": None,
        "transparencyPageId": None,
    }
    for block in iter_json_blocks(html):
        for node in walk(block):
            if not node.get("field_section_type"):
                continue
            for field in (node.get("profile_fields") or {}).get("nodes") or []:
                if not isinstance(field, dict):
                    continue
                field_type = field.get("field_type") or ""
                value = text_of(field.get("title"))
                if not value:
                    continue
                if field_type == "creation_date":
                    out["pageCreationDate"] = value
                elif field_type == "page_id":
                    out["transparencyPageId"] = value
                elif field_type == "ad_status":
                    out["adStatusText"] = value
                    lowered = value.lower()
                    if "isn't currently running ads" in lowered or "is not currently running ads" in lowered:
                        out["isRunningAds"] = False
                    elif "running ads" in lowered:
                        out["isRunningAds"] = True
    return out


def flatten_contact(record: dict) -> dict:
    """Add the single-value convenience columns a spreadsheet actually wants."""
    out = dict(record)
    out["primaryCategory"] = (record.get("categories") or [None])[0]
    out["email"] = (record.get("emails") or [None])[0]
    out["phone"] = (record.get("phones") or [None])[0]
    out["website"] = (record.get("websites") or [None])[0]
    out["address"] = (record.get("addresses") or [None])[0]
    out["hasEmail"] = bool(record.get("emails"))
    out["hasPhone"] = bool(record.get("phones"))
    out["hasWebsite"] = bool(record.get("websites"))
    out["hasAddress"] = bool(record.get("addresses"))
    # A blunt but honest completeness score: how many of the four contact
    # channels this business actually publishes. It ranks a lead list; it does
    # not pretend to measure lead quality.
    out["contactScore"] = sum(
        (out["hasEmail"], out["hasPhone"], out["hasWebsite"], out["hasAddress"])
    )
    return out


def matches_filters(record: dict, filters: dict) -> bool:
    if filters.get("requireEmail") and not record.get("hasEmail"):
        return False
    if filters.get("requirePhone") and not record.get("hasPhone"):
        return False
    if filters.get("requireWebsite") and not record.get("hasWebsite"):
        return False
    if filters.get("requireAnyContact") and not record.get("contactScore"):
        return False
    minimum = filters.get("minFollowers")
    if isinstance(minimum, int):
        followers = record.get("followers")
        # A page whose follower count could not be read cannot be shown to clear
        # the bar, so it is dropped rather than admitted on a guess.
        if not isinstance(followers, int) or followers < minimum:
            return False
    needle = (filters.get("categoryContains") or "").strip().lower()
    if needle:
        haystack = " ".join(record.get("categories") or []).lower()
        if needle not in haystack:
            return False
    return True


def summarise(records: Iterable[dict]) -> dict:
    records = list(records)
    return {
        "pagesProcessed": len(records),
        "withEmail": sum(1 for r in records if r.get("hasEmail")),
        "withPhone": sum(1 for r in records if r.get("hasPhone")),
        "withWebsite": sum(1 for r in records if r.get("hasWebsite")),
        "withAddress": sum(1 for r in records if r.get("hasAddress")),
        "withAnyContact": sum(1 for r in records if r.get("contactScore")),
        "fullyContactable": sum(1 for r in records if r.get("contactScore") == 4),
    }
