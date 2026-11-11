"""Turn an Ad Library payload into flat ad records.

Used here only as a page-discovery channel: Facebook's own page search endpoints
return 404 to logged-out clients, but the Ad Library publishes every advertiser's
page name, id and profile URI, which is a keyword-addressable list of businesses
active enough to be spending money.

Both the server-rendered page and the GraphQL pagination reply carry the same
node shape, so one parser serves both: every dict that owns an `ad_archive_id`
is an ad, wherever in the tree it sits. That is deliberate -- the Ad Library
nests results as
`ad_library_main.search_results_connection.edges[].node.collated_results[]`,
and Facebook has moved that path before. Searching for the key that names the
thing survives a path change; walking the path does not.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from src.fbcore import dedupe, find_nodes, iter_json_blocks, text_of

AD_LIBRARY_URL = "https://www.facebook.com/ads/library/?id={}"


def _iso(stamp: Any) -> str | None:
    """Facebook's epoch seconds -> ISO 8601 UTC, or None for anything else."""
    if not isinstance(stamp, (int, float)) or isinstance(stamp, bool):
        return None
    if not 946_684_800 < stamp < 4_102_444_800:  # 2000-01-01 .. 2100-01-01
        return None
    return (
        datetime.fromtimestamp(int(stamp), tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _running_days(start: Any, end: Any) -> int | None:
    """How long the ad has been live, in whole days.

    `end_date` is filled in for running ads too -- it is the current end of the
    flight, not the day it stopped -- so this is "days on air so far" for an
    active ad and "days it ran" for an inactive one. The `isActive` field is
    what tells the two apart; this number alone does not.
    """
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return None
    if end < start:
        return None
    return int((end - start) // 86_400)


def _media(snapshot: dict) -> dict:
    """Image and video URLs, gathered from the three places Facebook puts them.

    A carousel ad keeps its creatives in `cards[]` and leaves `images`/`videos`
    empty, so an actor that reads only the top level reports zero media for the
    format that has the most.
    """
    images: list[str] = []
    videos: list[str] = []
    previews: list[str] = []

    def take(container: Any) -> None:
        if not isinstance(container, dict):
            return
        for key in ("original_image_url", "resized_image_url", "image_url"):
            if container.get(key):
                images.append(container[key])
        for key in ("video_hd_url", "video_sd_url"):
            if container.get(key):
                videos.append(container[key])
        if container.get("video_preview_image_url"):
            previews.append(container["video_preview_image_url"])

    for entry in snapshot.get("images") or []:
        take(entry)
    for entry in snapshot.get("videos") or []:
        take(entry)
    for card in snapshot.get("cards") or []:
        take(card)

    return {
        "imageUrls": dedupe(images),
        "videoUrls": dedupe(videos),
        "thumbnailUrls": dedupe(previews),
    }


def _cards(snapshot: dict) -> list[dict]:
    """Per-card copy for carousel ads -- each card is its own headline and CTA."""
    out = []
    for card in snapshot.get("cards") or []:
        if not isinstance(card, dict):
            continue
        entry = {
            "title": card.get("title"),
            "body": card.get("body"),
            "caption": card.get("caption"),
            "ctaText": card.get("cta_text"),
            "linkUrl": card.get("link_url"),
            "linkDescription": card.get("link_description"),
        }
        if any(entry.values()):
            out.append(entry)
    return out


def parse_ad(node: dict) -> dict:
    """One ad node -> one flat record."""
    snapshot = node.get("snapshot") or {}
    start = node.get("start_date")
    end = node.get("end_date")
    archive_id = str(node.get("ad_archive_id") or "")
    impressions = node.get("impressions_with_index") or {}
    media = _media(snapshot)

    page_url = snapshot.get("page_profile_uri")
    page_id = str(node.get("page_id") or snapshot.get("page_id") or "") or None

    # Branded content: the ad is posted by a creator's page but paid for by a
    # brand. An advertiser-scoped search therefore legitimately returns rows
    # whose pageName is somebody else's -- the brand is in `branded_content`.
    # Surfacing both is the difference between "the filter leaked" and "this is
    # an influencer ad the brand is paying for".
    sponsor = snapshot.get("branded_content") or {}
    if not isinstance(sponsor, dict):
        sponsor = {}

    record = {
        "adArchiveId": archive_id or None,
        "adLibraryUrl": AD_LIBRARY_URL.format(archive_id) if archive_id else None,
        "isActive": node.get("is_active"),
        "pageId": page_id,
        "pageName": snapshot.get("page_name") or node.get("page_name"),
        "pageUrl": page_url,
        "pageProfilePictureUrl": snapshot.get("page_profile_picture_url"),
        "pageCategories": snapshot.get("page_categories") or [],
        "pageLikeCount": snapshot.get("page_like_count"),
        "pageIsDeleted": node.get("page_is_deleted"),
        "isBrandedContent": bool(sponsor.get("page_id")),
        "sponsorPageName": sponsor.get("page_name"),
        "sponsorPageId": str(sponsor["page_id"]) if sponsor.get("page_id") else None,
        "sponsorPageUrl": sponsor.get("page_profile_uri"),
        "startDate": _iso(start),
        "endDate": _iso(end),
        "startDateEpoch": start if isinstance(start, (int, float)) else None,
        "runningDays": _running_days(start, end),
        "adText": text_of(snapshot.get("body")),
        "title": snapshot.get("title"),
        "caption": snapshot.get("caption"),
        "linkDescription": snapshot.get("link_description"),
        "linkUrl": snapshot.get("link_url"),
        "ctaText": snapshot.get("cta_text"),
        "ctaType": snapshot.get("cta_type"),
        "displayFormat": snapshot.get("display_format"),
        "byline": snapshot.get("byline"),
        "disclaimerLabel": snapshot.get("disclaimer_label"),
        "publisherPlatforms": node.get("publisher_platform") or [],
        "collationCount": node.get("collation_count"),
        "collationId": node.get("collation_id"),
        "categories": node.get("categories") or [],
        # Present only on ads Meta classifies as political or issue-based;
        # commercial ads carry nulls here and that is Facebook's answer, not a
        # parse failure -- see README.
        "impressionsText": impressions.get("impressions_text"),
        "spendText": node.get("spend"),
        "currency": node.get("currency") or None,
        "reachEstimate": node.get("reach_estimate"),
        "totalActiveTime": node.get("total_active_time"),
        "targetedCountries": node.get("targeted_or_reached_countries") or [],
        "containsSensitiveContent": node.get("contains_sensitive_content"),
        "containsDigitalCreatedMedia": node.get("contains_digital_created_media"),
        "cards": _cards(snapshot),
    }
    record.update(media)
    record["imageCount"] = len(record["imageUrls"])
    record["videoCount"] = len(record["videoUrls"])
    record["hasVideo"] = record["videoCount"] > 0
    record["adTextLength"] = len(record["adText"]) if record["adText"] else 0
    record["adTextWordCount"] = len(re.findall(r"\w+", record["adText"] or ""))
    return record


def ad_nodes(root: Any) -> list[dict]:
    """Every ad node in a parsed payload, de-duplicated by archive id."""
    seen: set[str] = set()
    out: list[dict] = []
    for node in find_nodes(root, "ad_archive_id", "snapshot"):
        key = str(node.get("ad_archive_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(node)
    return out


def parse_page(html: str) -> dict:
    """Server-rendered Ad Library search page -> ads, total count and cursor."""
    ads: list[dict] = []
    seen: set[str] = set()
    total: int | None = None
    cursor: str | None = None
    has_next = False

    for block in iter_json_blocks(html):
        for node in ad_nodes(block):
            key = str(node["ad_archive_id"])
            if key in seen:
                continue
            seen.add(key)
            ads.append(parse_ad(node))
        for node in find_nodes(block, "search_results_connection"):
            connection = node["search_results_connection"]
            if not isinstance(connection, dict):
                continue
            if isinstance(connection.get("count"), int):
                total = connection["count"]
            info = connection.get("page_info") or {}
            if info.get("end_cursor"):
                cursor = info["end_cursor"]
                has_next = bool(info.get("has_next_page"))

    return {
        "ads": ads,
        "totalMatchingAds": total,
        "cursor": cursor,
        "hasNextPage": has_next,
    }


def parse_graphql(payload: dict) -> dict:
    """Pagination reply -> the same shape as parse_page."""
    ads: list[dict] = []
    seen: set[str] = set()
    cursor: str | None = None
    has_next = False

    for node in ad_nodes(payload):
        key = str(node["ad_archive_id"])
        if key in seen:
            continue
        seen.add(key)
        ads.append(parse_ad(node))

    for node in find_nodes(payload, "page_info"):
        info = node["page_info"]
        if isinstance(info, dict) and info.get("end_cursor"):
            cursor = info["end_cursor"]
            has_next = bool(info.get("has_next_page"))

    return {"ads": ads, "cursor": cursor, "hasNextPage": has_next, "totalMatchingAds": None}


def matches_filters(ad: dict, filters: dict) -> bool:
    """Post-fetch filters, applied to what Facebook actually returned."""
    if filters.get("onlyActive") and not ad.get("isActive"):
        return False
    if filters.get("onlyWithVideo") and not ad.get("hasVideo"):
        return False
    minimum = filters.get("minRunningDays")
    if isinstance(minimum, int):
        days = ad.get("runningDays")
        # An ad whose flight dates are missing cannot be shown to clear the bar,
        # so it is dropped rather than admitted on a guess.
        if not isinstance(days, int) or days < minimum:
            return False
    needle = (filters.get("adTextContains") or "").strip().lower()
    if needle:
        haystack = " ".join(
            str(ad.get(field) or "")
            for field in ("adText", "title", "linkDescription", "caption")
        ).lower()
        if needle not in haystack:
            return False
    return True


def summarise(ads: Iterable[dict]) -> dict:
    """Totals worth seeing without opening the dataset."""
    ads = list(ads)
    active = sum(1 for ad in ads if ad.get("isActive"))
    with_video = sum(1 for ad in ads if ad.get("hasVideo"))
    advertisers = {ad.get("pageId") for ad in ads if ad.get("pageId")}
    durations = sorted(d for d in (ad.get("runningDays") for ad in ads) if isinstance(d, int))
    median = durations[len(durations) // 2] if durations else None
    return {
        "adsCollected": len(ads),
        "activeAds": active,
        "inactiveAds": len(ads) - active,
        "adsWithVideo": with_video,
        "distinctAdvertisers": len(advertisers),
        "medianRunningDays": median,
    }
