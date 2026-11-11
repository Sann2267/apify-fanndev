"""Parse the watch page and classify what the description is selling.

Two jobs, kept apart on purpose:

1. **Extraction** -- pull ``ytInitialPlayerResponse`` out of the HTML. This has
   to be a brace-counting scan, not a regex. A non-greedy ``(\\{.+?\\})`` stops
   at the first closing brace and silently returns a truncated object: during
   recon that produced ``desc=0B`` and an empty title for a video whose
   description was in fact 848 bytes long. The bug looks exactly like "this
   video has no description", which is the worst kind.

2. **Classification** -- decide what a URL or a phrase in that description
   means. Everything here is a stated rule in ``constants.py`` rather than a
   model call, so a user can audit why a link was flagged.
"""

import json
import re
from urllib.parse import parse_qs, urlparse

from src.constants import (
    AFFILIATE_HOSTS,
    AMAZON_HOST_HINT,
    AMAZON_TAG_PARAMS,
    DISCLOSURE_MARKERS,
    DISCOUNT_PATTERN,
    NOISE_HOSTS,
    PROMO_PATTERNS,
    SHORTENER_HOSTS,
    SMART_LINK_HOSTS,
    SPONSOR_PATTERNS,
    SPONSOR_PLATFORM_HOSTS,
)

URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'\)\]]+")
TRACKING_PARAMS = ("tag", "ref", "ref_", "utm_source", "utm_campaign", "utm_medium",
                   "aff", "affid", "affiliate", "irclickid", "clickid", "sub_id",
                   "subid", "partner", "pid", "campaign")


class NoPlayerResponse(Exception):
    """The page never carried the player response."""


def extract_json_blob(body: str, marker: str) -> dict | None:
    """Return the first complete JSON object assigned after ``marker``.

    Brace-counting, string-aware (so a ``}`` inside a quoted value does not end
    the object early). Returns ``None`` rather than raising so callers can
    decide whether a missing blob is fatal.
    """
    start = body.find(marker)
    if start < 0:
        return None
    start = body.find("{", start)
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(body)):
        char = body[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(body[start:index + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_video(body: str) -> dict:
    """Pull every field this Actor needs out of one watch page."""
    player = extract_json_blob(body, "ytInitialPlayerResponse")
    if not player:
        raise NoPlayerResponse("ytInitialPlayerResponse absent")

    details = player.get("videoDetails") or {}
    micro = (player.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    captions = (
        ((player.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {})
        .get("captionTracks") or []
    )

    return {
        "videoId": details.get("videoId"),
        "title": details.get("title"),
        "channelName": details.get("author"),
        "channelId": details.get("channelId"),
        "description": details.get("shortDescription") or "",
        "viewCount": _as_int(details.get("viewCount")),
        "lengthSeconds": _as_int(details.get("lengthSeconds")),
        "keywords": details.get("keywords") or [],
        "isLiveContent": bool(details.get("isLiveContent")),
        "publishDate": micro.get("publishDate"),
        "uploadDate": micro.get("uploadDate"),
        "category": micro.get("category"),
        "captionLanguages": [c.get("languageCode") for c in captions if c.get("languageCode")],
    }


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().lstrip("www.")
    except ValueError:
        return ""


def _match_table(host: str, table: dict) -> str | None:
    if host in table:
        return table[host]
    for known, label in table.items():
        if host.endswith("." + known) or known in host:
            return label
    return None


def classify_links(description: str) -> list[dict]:
    """Every URL in the description, with what it appears to be.

    The ordering of these branches is the whole point. ``affiliate`` is the
    narrowest bucket and is checked first; a smart link or a bare shortener is
    deliberately *not* allowed to fall into it, because those carry no
    commission and flagging them turns every music video into a brand deal.
    """
    seen: dict[str, dict] = {}
    for raw in URL_IN_TEXT.findall(description):
        url = raw.rstrip(".,;:!?)")
        if url in seen:
            seen[url]["occurrences"] += 1
            continue

        host = _host(url)
        network = _match_table(host, AFFILIATE_HOSTS)
        smart = _match_table(host, SMART_LINK_HOSTS)
        shortener = _match_table(host, SHORTENER_HOSTS)
        platform = _match_table(host, SPONSOR_PLATFORM_HOSTS)
        is_noise = any(host == n or host.endswith("." + n) for n in NOISE_HOSTS)

        query = {}
        try:
            query = parse_qs(urlparse(url).query)
        except ValueError:
            pass
        tracking = sorted(k for k in query if k.lower() in TRACKING_PARAMS)

        # An Amazon link is affiliate only when it carries an associate tag.
        amazon_tag = None
        if AMAZON_HOST_HINT in host:
            for param in AMAZON_TAG_PARAMS:
                if query.get(param):
                    amazon_tag = query[param][0]
                    network = network or "amazon-associates"
                    break

        if network:
            kind = "affiliate"
        elif smart:
            kind = "smart-link"
        elif shortener:
            kind = "shortened"
        elif platform == "known-sponsor":
            kind = "sponsor-landing"
        elif platform:
            kind = "creator-platform"
        elif is_noise:
            kind = "social"
        elif tracking:
            kind = "tracked"
        else:
            kind = "other"

        seen[url] = {
            "url": url,
            "host": host,
            "kind": kind,
            "network": network or smart or shortener or platform,
            "trackingParams": tracking,
            "amazonTag": amazon_tag,
            "occurrences": 1,
        }
    return list(seen.values())


def find_promo_codes(description: str) -> list[str]:
    codes: list[str] = []
    for pattern in PROMO_PATTERNS:
        for match in re.finditer(pattern, description, re.IGNORECASE):
            code = match.group(1).strip()
            # A "code" that is an ordinary English word is almost always a
            # false positive from loose phrasing.
            if code.upper() in {"HERE", "BELOW", "THIS", "LINK", "ABOVE", "NOW"}:
                continue
            if code not in codes:
                codes.append(code)
    return codes


def find_sponsors(description: str) -> list[str]:
    names: list[str] = []
    for pattern in SPONSOR_PATTERNS:
        for match in re.finditer(pattern, description, re.IGNORECASE):
            name = re.sub(r"\s+", " ", match.group(1)).strip(" .,-")
            if 2 <= len(name) <= 40 and name not in names:
                names.append(name)
    return names


def find_disclosures(description: str) -> list[str]:
    lowered = description.lower()
    return [marker for marker in DISCLOSURE_MARKERS if marker in lowered]


def find_discounts(description: str) -> list[int]:
    return sorted({int(m) for m in re.findall(DISCOUNT_PATTERN, description, re.IGNORECASE)})


def build_record(video: dict) -> dict:
    """Assemble the monetisation view of one video."""
    description = video["description"]
    links = classify_links(description)
    affiliate = [l for l in links if l["kind"] == "affiliate"]
    sponsor_landing = [l for l in links if l["kind"] == "sponsor-landing"]
    smart_links = [l for l in links if l["kind"] == "smart-link"]
    shortened = [l for l in links if l["kind"] == "shortened"]
    codes = find_promo_codes(description)
    sponsors = find_sponsors(description)
    disclosures = find_disclosures(description)

    # The flag is never a bare boolean: every record carries the list of
    # signals that produced it, so a user can see *why* a video was flagged
    # and filter on the signal they trust rather than on our judgement.
    signals: list[str] = []
    if affiliate:
        signals.append("affiliate-link")
    if codes:
        signals.append("promo-code")
    if sponsors:
        signals.append("sponsor-mention")
    if disclosures:
        signals.append("disclosure-marker")
    if sponsor_landing:
        signals.append("sponsor-landing-link")

    return {
        **video,
        "descriptionLength": len(description),
        "links": links,
        "linkCount": len(links),
        "affiliateLinks": affiliate,
        "affiliateLinkCount": len(affiliate),
        "affiliateNetworks": sorted({l["network"] for l in affiliate if l["network"]}),
        "sponsorLandingLinks": sponsor_landing,
        "smartLinks": smart_links,
        "shortenedLinks": shortened,
        "shortenedLinkCount": len(shortened),
        "promoCodes": codes,
        "discountPercents": find_discounts(description),
        "sponsorMentions": sponsors,
        "disclosureMarkers": disclosures,
        "monetisationSignals": signals,
        "isMonetisedDescription": bool(signals),
    }


def parse_channel_video_ids(body: str, limit: int) -> list[str]:
    """Video IDs from a channel's /videos tab, newest first, order preserved.

    Reads the raw page rather than the re-serialised blob. Both were measured on
    2026-09-20 and the blob is the unreliable one: on one fetch of
    ``@mkbhd/videos`` the parsed ``ytInitialData`` object was structurally valid
    -- ``contents``, ``header``, ``metadata`` all present -- and still contained
    **zero** video IDs, while the raw body held 30. The grid is populated in a
    region the top-level parse does not always cover, so scanning the text is
    the surface-accurate choice here.

    The scan starts at the ``ytInitialData`` assignment so IDs from earlier
    scripts (topbar, prefetch hints) cannot leak in.
    """
    start = body.find("ytInitialData")
    region = body[start:] if start >= 0 else body

    ids: list[str] = []
    for vid in re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', region):
        if vid not in ids:
            ids.append(vid)
        if len(ids) >= limit:
            break
    return ids
