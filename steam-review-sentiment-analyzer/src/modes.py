"""One async generator per mode. Each yields finished dataset records."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable

from .client import SteamClient, SteamNotFound
from .constants import (
    APPDETAILS_URL,
    COMMUNITY,
    DEFAULT_BREAKDOWN_LANGUAGES,
    HISTOGRAM_URL,
    LANGUAGES,
    REVIEWS_PAGE_SIZE,
    REVIEWS_URL,
    STORESEARCH_URL,
)
from .parsers import (
    app_meta,
    bomb_candidates,
    complaint_analysis,
    error_record,
    histogram_trend,
    history_records,
    parse_user_page,
    query_summary_block,
    review_record,
    sample_analytics,
    text_sentiment,
    mismatch,
    utc_now_iso,
)

log = logging.getLogger("steam.modes")


@dataclass
class Options:
    max_reviews: int = 500
    review_filter: str = "recent"
    language: str = "all"
    purchase_type: str = "all"
    review_type: str = "all"
    day_range: int = 365
    min_playtime_hours: int | None = None
    max_playtime_hours: int | None = None
    include_offtopic: bool = False
    start_ts: int | None = None
    end_ts: int | None = None
    text_sentiment: bool = True
    breakdown_languages: list[str] = field(default_factory=list)
    sample_size: int = 300
    country: str = "us"


class InputError(Exception):
    """The input cannot be turned into a Steam target."""


# ---------------------------------------------------------------- app resolution

_APP_URL = re.compile(r"(?:store\.steampowered\.com|steamcommunity\.com)/app/(\d+)", re.I)


async def resolve_app(client: SteamClient, token: str, opt: Options) -> dict[str, Any]:
    """appId / store URL / community URL / game name -> app metadata dict.

    The reviews endpoint answers a NONEXISTENT appid with a hollow 200
    ("No user reviews", success 1), so existence is decided by appdetails.
    """
    token = token.strip()
    resolved_from = "appId"
    if token.isdigit():
        appid = int(token)
    elif m := _APP_URL.search(token):
        appid = int(m.group(1))
        resolved_from = "url"
    else:
        data = await client.request(STORESEARCH_URL, {"term": token, "l": "english", "cc": opt.country.upper()})
        items = [i for i in (data or {}).get("items") or [] if i.get("type") == "app"]
        if not items:
            raise SteamNotFound(f"No Steam app matches the name {token!r}")
        appid = int(items[0]["id"])
        resolved_from = "name"
        log.info("Resolved %r -> %s (%s)", token, appid, items[0].get("name"))

    details = await client.request(APPDETAILS_URL, {"appids": appid, "cc": opt.country, "l": "english"})
    entry = (details or {}).get(str(appid)) or {}
    if not entry.get("success"):
        # appdetails also fails for some delisted/region-locked apps that still
        # have reviews - fall back to the review counter before calling it gone.
        qs = await _query_summary(client, appid, language="all", purchase_type="all")
        if not qs or not qs.get("total_reviews"):
            raise SteamNotFound(f"Steam has no app {appid} (appdetails success=false, 0 reviews)")
        meta = app_meta(appid, None)
        meta["appDetailsAvailable"] = False
    else:
        meta = app_meta(appid, entry.get("data"))
        meta["appDetailsAvailable"] = True
    meta["resolvedFrom"] = resolved_from
    return meta


# ---------------------------------------------------------------- review API helpers

def _review_params(opt: Options, cursor: str, *, language: str | None = None, purchase_type: str | None = None,
                   num: int = REVIEWS_PAGE_SIZE, review_type: str | None = None) -> dict[str, Any]:
    p: dict[str, Any] = {
        "json": 1,
        "filter": opt.review_filter,
        "language": language or opt.language,
        "purchase_type": purchase_type or opt.purchase_type,
        "review_type": review_type or opt.review_type,
        "num_per_page": num,
        "cursor": cursor,
        "filter_offtopic_activity": 0 if opt.include_offtopic else 1,
    }
    if opt.review_filter == "all":
        p["day_range"] = opt.day_range  # only honoured by filter=all; capped at 365 upstream
    if opt.min_playtime_hours:
        p["playtime_filter_min"] = opt.min_playtime_hours  # HOURS (review payload is minutes)
    if opt.max_playtime_hours:
        p["playtime_filter_max"] = opt.max_playtime_hours
    return p


async def _query_summary(client: SteamClient, appid: int, *, language: str, purchase_type: str) -> dict[str, Any] | None:
    """Totals only (num_per_page=0). review_type must stay 'all' or Steam strips the totals."""
    data = await client.request(
        REVIEWS_URL.format(appid=appid),
        {"json": 1, "num_per_page": 0, "language": language, "purchase_type": purchase_type, "cursor": "*"},
        bucket="reviews",
    )
    if not data or data.get("success") != 1:
        return None
    return data.get("query_summary")


async def iter_reviews(client: SteamClient, appid: int, opt: Options, limit: int,
                       sort: str | None = None) -> AsyncIterator[dict[str, Any]]:
    """Cursor walk with dedupe and every stop condition the API needs.

    filter=all (helpfulness) re-serves rows and repeats cursors on small apps,
    so dedupe + cursor-repeat detection are mandatory, not defensive.
    """
    local = opt if sort is None else Options(**{**opt.__dict__, "review_filter": sort})
    cursor, seen_cursors, seen_ids, yielded = "*", {"*"}, set(), 0
    ts_key = "timestamp_updated" if local.review_filter == "updated" else "timestamp_created"
    chronological = local.review_filter in ("recent", "updated")
    while yielded < limit:
        data = await client.request(REVIEWS_URL.format(appid=appid), _review_params(local, cursor), bucket="reviews")
        if not data or data.get("success") != 1:
            raise SteamNotFound(f"appreviews success={data.get('success') if data else None}")
        page = data.get("reviews") or []
        if not page:
            return
        older_than_window = False
        for r in page:
            rid = r.get("recommendationid")
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            ts = int(r.get(ts_key) or 0)
            if local.end_ts and ts > local.end_ts:
                continue
            if local.start_ts and ts < local.start_ts:
                if chronological:
                    older_than_window = True
                    break
                continue
            yield r
            yielded += 1
            if yielded >= limit:
                return
        nxt = data.get("cursor")
        if older_than_window or not nxt or nxt in seen_cursors:
            return
        seen_cursors.add(nxt)
        cursor = nxt


# ---------------------------------------------------------------- modes

async def run_reviews(client: SteamClient, token: str, opt: Options) -> AsyncIterator[dict[str, Any]]:
    app = await resolve_app(client, token, opt)
    n = 0
    async for r in iter_reviews(client, app["appId"], opt, opt.max_reviews):
        n += 1
        yield review_record(r, app, token, opt.text_sentiment)
    if n == 0:
        yield error_record(token, "no_reviews", "No reviews match the filters (language/purchase type/dates/playtime).",
                           appId=app["appId"], appName=app.get("appName"))


async def run_summary(client: SteamClient, token: str, opt: Options) -> AsyncIterator[dict[str, Any]]:
    app = await resolve_app(client, token, opt)
    appid = app["appId"]
    steam_qs = query_summary_block(await _query_summary(client, appid, language="all", purchase_type="steam"))
    all_qs = query_summary_block(await _query_summary(client, appid, language="all", purchase_type="all"))

    breakdown = []
    base_total = (all_qs if opt.purchase_type == "all" else steam_qs or {}) or {}
    for lang in opt.breakdown_languages or DEFAULT_BREAKDOWN_LANGUAGES:
        qs = query_summary_block(await _query_summary(
            client, appid, language=lang, purchase_type="all" if opt.purchase_type == "all" else "steam"))
        if qs and qs["total_reviews"]:
            breakdown.append({"language": lang, **qs,
                              "shareOfAllReviews": round(qs["total_reviews"] / base_total["total_reviews"], 4)
                              if base_total.get("total_reviews") else None})
    breakdown.sort(key=lambda x: -x["total_reviews"])

    hist = ((await client.request(HISTOGRAM_URL.format(appid=appid), {"l": "english"})) or {}).get("results") or {}

    sample: list[dict[str, Any]] = []
    helpful: dict[str, list[dict[str, Any]]] = {"positive": [], "negative": []}
    if opt.sample_size > 0:
        async for r in iter_reviews(client, appid, opt, opt.sample_size, sort="recent"):
            sample.append(r)
        # Keyword / complaint analysis uses the reviews the community voted
        # most helpful in the last year (English, one page per side) - a 2-day
        # window of newest reviews has too few negatives to say anything.
        for side in helpful:
            topic_opt = Options(**{**opt.__dict__, "review_filter": "all", "language": "english",
                                   "review_type": side, "day_range": 365, "start_ts": None, "end_ts": None})
            async for r in iter_reviews(client, appid, topic_opt, 100):
                helpful[side].append(r)

    non_steam = None
    if steam_qs and all_qs and all_qs["total_reviews"]:
        non_steam = round(1 - steam_qs["total_reviews"] / all_qs["total_reviews"], 4)
    yield {
        "_input": token,
        "_source": "S1-appreviews+histogram",
        "_scrapedAt": utc_now_iso(),
        "recordType": "SUMMARY",
        **app,
        "steamScore": steam_qs,
        "allPurchasesScore": all_qs,
        "nonSteamPurchaseShare": non_steam,
        "trend": histogram_trend(hist) if hist.get("rollups") else None,
        "reviewBombCandidates": bomb_candidates(hist) if hist.get("rollups") else [],
        "languageBreakdown": breakdown,
        "recentSample": sample_analytics(sample, appid, opt.text_sentiment),
        "complaintAnalysis": complaint_analysis(helpful["positive"], helpful["negative"], appid),
        "sampleFilters": {"language": opt.language, "purchase_type": opt.purchase_type,
                          "playtime_filter_min": opt.min_playtime_hours, "playtime_filter_max": opt.max_playtime_hours},
    }


async def run_history(client: SteamClient, token: str, opt: Options) -> AsyncIterator[dict[str, Any]]:
    app = await resolve_app(client, token, opt)
    hist = ((await client.request(HISTOGRAM_URL.format(appid=app["appId"]), {"l": "english"})) or {}).get("results") or {}
    rows = history_records(hist, app, token)
    if not rows:
        yield error_record(token, "no_reviews", "Steam has no review history for this app.",
                           appId=app["appId"], appName=app.get("appName"))
    for r in rows:
        yield r


async def run_languages(client: SteamClient, token: str, opt: Options) -> AsyncIterator[dict[str, Any]]:
    app = await resolve_app(client, token, opt)
    appid = app["appId"]
    base = query_summary_block(await _query_summary(client, appid, language="all", purchase_type=opt.purchase_type))
    base_total = (base or {}).get("total_reviews") or 0
    langs = opt.breakdown_languages or LANGUAGES
    rows = []
    for lang in langs:
        qs = query_summary_block(await _query_summary(client, appid, language=lang, purchase_type=opt.purchase_type))
        if not qs or not qs["total_reviews"]:
            continue
        rows.append({
            "_input": token,
            "_source": "S1-appreviews",
            "_scrapedAt": utc_now_iso(),
            "recordType": "LANGUAGE",
            "appId": appid,
            "appName": app.get("appName"),
            "language": lang,
            "purchase_type": opt.purchase_type,
            **qs,
            "shareOfAllReviews": round(qs["total_reviews"] / base_total, 4) if base_total else None,
            "positiveRatioVsAllLanguages": round(qs["positiveRatio"] - base["positiveRatio"], 4)
            if base and base.get("positiveRatio") is not None and qs["positiveRatio"] is not None else None,
        })
    rows.sort(key=lambda r: -r["total_reviews"])
    if not rows:
        yield error_record(token, "no_reviews", "No reviews in any requested language.", appId=appid,
                           appName=app.get("appName"))
    for rank, r in enumerate(rows, 1):
        yield {**r, "rank": rank}


_PROFILE = re.compile(r"steamcommunity\.com/(id|profiles)/([^/?#]+)", re.I)


def user_base_url(token: str) -> str:
    token = token.strip()
    if m := _PROFILE.search(token):
        return f"{COMMUNITY}/{m.group(1).lower()}/{m.group(2)}"
    if re.fullmatch(r"7656\d{13}", token):
        return f"{COMMUNITY}/profiles/{token}"
    if re.fullmatch(r"[A-Za-z0-9_-]{2,32}", token):
        return f"{COMMUNITY}/id/{token}"
    raise InputError(f"Not a Steam profile URL, SteamID64 or custom URL name: {token!r}")


async def run_user_reviews(client: SteamClient, token: str, opt: Options) -> AsyncIterator[dict[str, Any]]:
    base = user_base_url(token)
    page_no, yielded, seen = 1, 0, set()
    while yielded < opt.max_reviews:
        html = await client.request(f"{base}/recommended/", {"l": "english", "p": page_no}, expect_json=False)
        page = parse_user_page(html)
        if page["state"] == "not_found":
            raise SteamNotFound(page.get("detail") or "profile not found")
        if page["state"] == "private":
            yield error_record(token, "private_profile", "This Steam profile (or its game details) is private.",
                               steamProfileUrl=base)
            return
        if not page["reviews"]:
            if page_no == 1:
                yield error_record(token, "no_reviews", "This profile has no public reviews.", steamProfileUrl=base)
            return
        new = 0
        for r in page["reviews"]:
            key = r["recommendationid"] or (r["appId"], r["postedText"])
            if key in seen:
                continue
            seen.add(key)
            new += 1
            sentiment = text_sentiment(r["review"]) if opt.text_sentiment else None
            rec = {
                "_input": token,
                "_source": "S1-community-html",
                "_scrapedAt": utc_now_iso(),
                "recordType": "USER_REVIEW",
                "steamProfileUrl": page["profileUrl"] or base,
                "personaName": page["persona"],
                "userTotalReviews": page["total"],
                **r,
            }
            if opt.text_sentiment:
                # Profile pages carry no language tag; VADER is English-only, so
                # scores on non-English text are unreliable (documented).
                rec["textSentiment"] = sentiment
                rec["sentimentMismatch"] = mismatch(r["voted_up"], sentiment)
            yield rec
            yielded += 1
            if yielded >= opt.max_reviews:
                return
        if not new or (page["total"] is not None and len(seen) >= page["total"]):
            return
        page_no += 1


Runner = Callable[[SteamClient, str, Options], AsyncIterator[dict[str, Any]]]

# mode -> (runner, input field holding the targets)
MODES: dict[str, tuple[Runner, str]] = {
    "reviews": (run_reviews, "apps"),
    "summary": (run_summary, "apps"),
    "history": (run_history, "apps"),
    "languages": (run_languages, "apps"),
    "userReviews": (run_user_reviews, "steamUsers"),
}


def parse_date(value: Any, end_of_day: bool = False) -> int | None:
    if not value:
        return None
    s = str(value).strip()[:10]
    try:
        d = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise InputError(f"Dates must be YYYY-MM-DD, got {value!r}") from exc
    ts = int(d.timestamp())
    return ts + 86399 if end_of_day else ts
