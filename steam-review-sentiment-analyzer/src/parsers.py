"""Pure functions: record builders, sentiment scoring, aggregate analytics, HTML parsing."""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from selectolax.parser import HTMLParser

from .constants import COMMUNITY, PLAYTIME_BUCKETS, STORE

_STOPWORDS = set("""
a about above after again against all also am an and any are aren't as at be because been before being below between
both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each even ever every few
for from further game games get gets getting got had hadn't has hasn't have haven't having he her here hers herself him
himself his how i i'd i'll i'm i've if in into is isn't it it's its itself just let's like lot make makes me more most
much mustn't my myself no nor not now of off on once one only or other ought our ours ourselves out over own play
played playing plays really same she should shouldn't so some still such than that that's the their theirs them
themselves then there there's these they they'd they'll they're they've thing things think this those though through
to too under until up very was wasn't way we we'd we'll we're we've well were weren't what what's when where which
while who whom why will with won't would wouldn't yet you you'd you'll you're you've your yours yourself yourselves
im ive need feel want game's dont doesnt didnt cant isnt wont thats youre theres also get got 10 hours hour time times bit many
""".split())

_TOKEN = re.compile(r"[a-z][a-z']+")
_vader = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_iso(ts: Any) -> str | None:
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ratio(up: int, down: int) -> float | None:
    total = up + down
    return round(up / total, 4) if total else None


def score_desc(up: int, down: int) -> str:
    """Steam's public rating ladder, applied to any (up, down) window."""
    total = up + down
    if total == 0:
        return "No user reviews"
    if total < 10:
        return f"{total} user review{'s' if total != 1 else ''}"
    pct = up / total * 100
    if pct >= 95 and total >= 500:
        return "Overwhelmingly Positive"
    if pct >= 80:
        return "Very Positive" if total >= 50 else "Positive"
    if pct >= 70:
        return "Mostly Positive"
    if pct >= 40:
        return "Mixed"
    if pct >= 20:
        return "Mostly Negative"
    if total >= 500:
        return "Overwhelmingly Negative"
    return "Very Negative" if total >= 50 else "Negative"


def error_record(input_value: str, kind: str, detail: str = "", **extra: Any) -> dict[str, Any]:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        **extra,
        "_error": kind,
        "_errorDetail": detail,
    }


# ---------------------------------------------------------------- sentiment

def text_sentiment(text: str | None) -> dict[str, Any] | None:
    """VADER compound score. VADER is an English lexicon, so callers only pass English text."""
    global _vader
    if not text or not text.strip():
        return None
    if _vader is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _vader = SentimentIntensityAnalyzer()
    s = _vader.polarity_scores(text[:5000])
    c = s["compound"]
    return {
        "compound": c,
        "positive": s["pos"],
        "negative": s["neg"],
        "neutral": s["neu"],
        "label": "positive" if c >= 0.05 else "negative" if c <= -0.05 else "neutral",
    }


def mismatch(voted_up: Any, sentiment: dict[str, Any] | None) -> bool | None:
    """True when the thumb and the wording disagree (e.g. 'Recommended' but the text is negative)."""
    if sentiment is None or voted_up is None:
        return None
    if voted_up and sentiment["label"] == "negative":
        return True
    if not voted_up and sentiment["label"] == "positive":
        return True
    return False


# ---------------------------------------------------------------- reviews

def review_url(steamid: Any, appid: int) -> str | None:
    return f"{COMMUNITY}/profiles/{steamid}/recommended/{appid}/" if steamid else None


def review_record(raw: dict[str, Any], app: dict[str, Any], input_value: str, with_sentiment: bool) -> dict[str, Any]:
    author = raw.get("author") or {}
    sentiment = text_sentiment(raw.get("review")) if with_sentiment and raw.get("language") == "english" else None
    pt = author.get("playtime_at_review")
    rec = {
        "_input": input_value,
        "_source": "S1-appreviews",
        "_scrapedAt": utc_now_iso(),
        "recordType": "REVIEW",
        "appId": app["appId"],
        "appName": app.get("appName"),
        "reviewUrl": review_url(author.get("steamid"), app["appId"]),
        "createdAt": ts_iso(raw.get("timestamp_created")),
        "updatedAt": ts_iso(raw.get("timestamp_updated")),
        "playtimeAtReviewHours": round(pt / 60, 1) if isinstance(pt, (int, float)) else None,
        **raw,  # upstream fields verbatim (author{}, voted_up, votes_up, weighted_vote_score, ...)
    }
    if with_sentiment:
        rec["textSentiment"] = sentiment
        rec["sentimentMismatch"] = mismatch(raw.get("voted_up"), sentiment)
    return rec


def query_summary_block(qs: dict[str, Any] | None) -> dict[str, Any] | None:
    if not qs or "total_reviews" not in qs:
        return None
    up, down = int(qs.get("total_positive") or 0), int(qs.get("total_negative") or 0)
    return {
        "review_score": qs.get("review_score"),
        "review_score_desc": qs.get("review_score_desc"),
        "total_positive": up,
        "total_negative": down,
        "total_reviews": int(qs.get("total_reviews") or 0),
        "positiveRatio": ratio(up, down),
    }


# ---------------------------------------------------------------- histogram

def _rollup_rows(hist: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for r in hist.get("rollups") or []:
        up, down = int(r.get("recommendations_up") or 0), int(r.get("recommendations_down") or 0)
        rows.append({"date": int(r.get("date") or 0), "up": up, "down": down, "total": up + down})
    return rows


def bomb_candidates(hist: dict[str, Any]) -> list[dict[str, Any]]:
    """Periods whose negative share AND volume both jump far above the game's own baseline.

    Heuristic, not Steam's off-topic flag (which is not exposed anywhere public):
    negative share >= baseline + 0.20 (and >= 1.5x baseline), volume >= 2x the
    median period, and at least 50 reviews in the period.
    """
    rows = [r for r in _rollup_rows(hist) if r["total"] > 0]
    if len(rows) < 4:
        return []
    neg_shares = [r["down"] / r["total"] for r in rows]
    base_neg = statistics.median(neg_shares)
    base_vol = statistics.median(r["total"] for r in rows)
    out = []
    for r, ns in zip(rows, neg_shares):
        if r["total"] >= 50 and r["total"] >= 2 * base_vol and ns >= base_neg + 0.20 and ns >= 1.5 * base_neg:
            out.append({
                "periodStart": ts_iso(r["date"]),
                "recommendations_up": r["up"],
                "recommendations_down": r["down"],
                "negativeShare": round(ns, 4),
                "baselineNegativeShare": round(base_neg, 4),
                "volumeVsMedian": round(r["total"] / base_vol, 2) if base_vol else None,
            })
    return out


def histogram_trend(hist: dict[str, Any]) -> dict[str, Any]:
    rows = _rollup_rows(hist)
    recent = hist.get("recent") or []
    r_up = sum(int(x.get("recommendations_up") or 0) for x in recent)
    r_down = sum(int(x.get("recommendations_down") or 0) for x in recent)
    life_up, life_down = sum(r["up"] for r in rows), sum(r["down"] for r in rows)

    def window(n: int) -> dict[str, Any]:
        sel = rows[-n:]
        up, down = sum(r["up"] for r in sel), sum(r["down"] for r in sel)
        return {"recommendations_up": up, "recommendations_down": down, "positiveRatio": ratio(up, down),
                "reviewScoreDesc": score_desc(up, down)}

    life_ratio = ratio(life_up, life_down)
    recent_ratio = ratio(r_up, r_down)
    return {
        "rollupType": hist.get("rollup_type"),
        "firstReviewPeriod": ts_iso(hist.get("start_date")),
        "lastReviewPeriod": ts_iso(hist.get("end_date")),
        "lifetime": {"recommendations_up": life_up, "recommendations_down": life_down,
                     "positiveRatio": life_ratio, "reviewScoreDesc": score_desc(life_up, life_down)},
        "last30Days": {"recommendations_up": r_up, "recommendations_down": r_down,
                       "positiveRatio": recent_ratio, "reviewScoreDesc": score_desc(r_up, r_down)},
        "last3Periods": window(3),
        "last12Periods": window(12),
        "recentVsLifetimeDelta": round(recent_ratio - life_ratio, 4)
        if recent_ratio is not None and life_ratio is not None else None,
    }


def history_records(hist: dict[str, Any], app: dict[str, Any], input_value: str) -> list[dict[str, Any]]:
    bombs = {b["periodStart"] for b in bomb_candidates(hist)}
    out = []
    period = hist.get("rollup_type") or "month"
    series = [(period, r) for r in hist.get("rollups") or []] + [("day", r) for r in hist.get("recent") or []]
    for kind, r in series:
        up, down = int(r.get("recommendations_up") or 0), int(r.get("recommendations_down") or 0)
        start = ts_iso(r.get("date"))
        out.append({
            "_input": input_value,
            "_source": "S1-appreviewhistogram",
            "_scrapedAt": utc_now_iso(),
            "recordType": "HISTORY",
            "appId": app["appId"],
            "appName": app.get("appName"),
            "period": kind,
            "periodStart": start,
            "recommendations_up": up,
            "recommendations_down": down,
            "totalReviews": up + down,
            "positiveRatio": ratio(up, down),
            "reviewScoreDesc": score_desc(up, down),
            "isReviewBombCandidate": kind != "day" and start in bombs,
        })
    return out


# ---------------------------------------------------------------- sample analytics

def _seg(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    up = sum(1 for r in reviews if r.get("voted_up"))
    return {"reviews": len(reviews), "positiveRatio": ratio(up, len(reviews) - up)}


def _median_hours(reviews: Iterable[dict[str, Any]]) -> float | None:
    vals = [(r.get("author") or {}).get("playtime_at_review") for r in reviews]
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(statistics.median(vals) / 60, 1) if vals else None


def _terms(text: str) -> set[str]:
    toks = [t.strip("'") for t in _TOKEN.findall(text.lower())]
    toks = [t for t in toks if len(t) >= 3 and t not in _STOPWORDS]
    grams = set(toks)
    grams.update(f"{a} {b}" for a, b in zip(toks, toks[1:]))
    return grams


def distinctive_terms(pos: list[str], neg: list[str], top: int = 15) -> tuple[list[dict], list[dict]]:
    """Terms that appear in a much larger share of one side's reviews than the other's (document frequency)."""
    df_pos, df_neg = Counter(), Counter()
    for t in pos:
        df_pos.update(_terms(t))
    for t in neg:
        df_neg.update(_terms(t))
    n_pos, n_neg = max(1, len(pos)), max(1, len(neg))
    min_df = max(3, math.ceil(0.02 * min(n_pos, n_neg))) if pos and neg else 3

    def side(df_a: Counter, n_a: int, df_b: Counter, n_b: int) -> list[dict]:
        scored = []
        for term, c in df_a.items():
            if c < min_df:
                continue
            share_a, share_b = c / n_a, df_b.get(term, 0) / n_b
            lift = (share_a + 0.01) / (share_b + 0.01)
            if lift >= 1.5:
                scored.append((share_a - share_b, term, c, share_a, share_b, lift))
        scored.sort(reverse=True)
        return [{"term": t, "reviews": c, "share": round(sa, 4), "shareOtherSide": round(sb, 4), "lift": round(l, 2)}
                for _, t, c, sa, sb, l in scored[:top]]

    return side(df_pos, n_pos, df_neg, n_neg), side(df_neg, n_neg, df_pos, n_pos)


def complaint_analysis(pos: list[dict[str, Any]], neg: list[dict[str, Any]], appid: int) -> dict[str, Any]:
    """Distinctive terms + top excerpts from the most-helpful English reviews of the last 365 days."""
    top_pos, top_neg = distinctive_terms([r.get("review") or "" for r in pos], [r.get("review") or "" for r in neg])
    by_votes = lambda rs: sorted(rs, key=lambda r: -(r.get("votes_up") or 0))[:5]  # noqa: E731
    return {
        "basis": "most helpful English reviews, last 365 days",
        "reviewsAnalysed": {"positive": len(pos), "negative": len(neg)},
        "topNegativeTerms": top_neg,
        "topPositiveTerms": top_pos,
        "mostHelpfulNegative": [_excerpt(r, appid) for r in by_votes(neg)],
        "mostHelpfulPositive": [_excerpt(r, appid) for r in by_votes(pos)],
    }


def _excerpt(r: dict[str, Any], appid: int) -> dict[str, Any]:
    text = (r.get("review") or "").strip()
    return {
        "recommendationid": r.get("recommendationid"),
        "votes_up": r.get("votes_up"),
        "playtimeAtReviewHours": round(((r.get("author") or {}).get("playtime_at_review") or 0) / 60, 1),
        "createdAt": ts_iso(r.get("timestamp_created")),
        "excerpt": text[:400] + ("..." if len(text) > 400 else ""),
        "reviewUrl": review_url((r.get("author") or {}).get("steamid"), appid),
    }


def sample_analytics(reviews: list[dict[str, Any]], appid: int, with_sentiment: bool) -> dict[str, Any]:
    if not reviews:
        return {"sampleSize": 0}
    pos = [r for r in reviews if r.get("voted_up")]
    neg = [r for r in reviews if not r.get("voted_up")]
    created = sorted(int(r.get("timestamp_created") or 0) for r in reviews)

    buckets = []
    for lo, hi in PLAYTIME_BUCKETS:
        sel = [r for r in reviews
               if lo * 60 <= ((r.get("author") or {}).get("playtime_at_review") or 0) < (hi * 60 if hi else 10 ** 12)]
        buckets.append({"bucket": f"{lo}-{hi}h" if hi else f"{lo}h+", **_seg(sel)})

    def flag(name: str) -> dict[str, Any]:
        return {"yes": _seg([r for r in reviews if r.get(name)]), "no": _seg([r for r in reviews if not r.get(name)])}

    out: dict[str, Any] = {
        "sampleSize": len(reviews),
        "sampleOldestReview": ts_iso(created[0]),
        "sampleNewestReview": ts_iso(created[-1]),
        **_seg(reviews),
        "byPlaytimeAtReview": buckets,
        "medianPlaytimeAtReviewHours": {"positive": _median_hours(pos), "negative": _median_hours(neg)},
        "steamDeck": flag("primarily_steam_deck"),
        "writtenDuringEarlyAccess": flag("written_during_early_access"),
        "steamPurchase": flag("steam_purchase"),
        "receivedForFree": flag("received_for_free"),
        "refunded": flag("refunded"),
        "languageMix": dict(Counter(r.get("language") for r in reviews).most_common(10)),
        "avgReviewLengthChars": {
            "positive": round(statistics.mean(len(r.get("review") or "") for r in pos)) if pos else None,
            "negative": round(statistics.mean(len(r.get("review") or "") for r in neg)) if neg else None,
        },
    }
    if with_sentiment:
        scored = [(r, text_sentiment(r.get("review"))) for r in reviews if r.get("language") == "english"]
        scored = [(r, s) for r, s in scored if s]
        labels = Counter(s["label"] for _, s in scored)
        out["textSentiment"] = {
            "englishReviewsScored": len(scored),
            "avgCompound": round(statistics.mean(s["compound"] for _, s in scored), 4) if scored else None,
            "labels": dict(labels),
            "recommendedButNegativeText": sum(1 for r, s in scored if r.get("voted_up") and s["label"] == "negative"),
            "notRecommendedButPositiveText": sum(1 for r, s in scored if not r.get("voted_up") and s["label"] == "positive"),
        }
    return out


# ---------------------------------------------------------------- app metadata

def app_meta(appid: int, data: dict[str, Any] | None) -> dict[str, Any]:
    d = data or {}
    price = d.get("price_overview") or {}
    return {
        "appId": appid,
        "appName": d.get("name"),
        "appType": d.get("type"),
        "storeUrl": f"{STORE}/app/{appid}/",
        "developers": d.get("developers"),
        "publishers": d.get("publishers"),
        "releaseDate": (d.get("release_date") or {}).get("date"),
        "comingSoon": (d.get("release_date") or {}).get("coming_soon"),
        "isFree": d.get("is_free"),
        "price": price.get("final_formatted"),
        "priceCurrency": price.get("currency"),
        "discountPercent": price.get("discount_percent"),
        "genres": [g.get("description") for g in d.get("genres") or []] or None,
        "metacriticScore": (d.get("metacritic") or {}).get("score"),
        "storeRecommendationsTotal": (d.get("recommendations") or {}).get("total"),
    }


# ---------------------------------------------------------------- community user reviews

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_MONTH_RE = "|".join(_MONTHS)
_DATE = re.compile(rf"(\d{{1,2}}) ({_MONTH_RE})(?:,? (\d{{4}}))?|({_MONTH_RE}) (\d{{1,2}})(?:,? (\d{{4}}))?", re.I)


def _parse_steam_date(text: str, now: datetime) -> str | None:
    """'9 October' / '3 March, 2023' / 'October 9, 2023'. No year means the current year."""
    for m in _DATE.finditer(text):
        if m.group(1):
            day, month, year = m.group(1), m.group(2), m.group(3)
        else:
            month, day, year = m.group(4), m.group(5), m.group(6)
        mon = _MONTHS.get(month.lower())
        if not mon:
            continue
        try:
            return datetime(int(year) if year else now.year, mon, int(day)).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def _int_before(text: str, phrase: str) -> int:
    m = re.search(r"([\d,]+) (?:people|person) found this review " + phrase, text)
    return int(m.group(1).replace(",", "")) if m else 0


def parse_user_page(html: str) -> dict[str, Any]:
    """One /recommended/?p=N page -> {state, persona, profileUrl, total, reviews[]}."""
    tree = HTMLParser(html)
    body = tree.body
    body_cls = (body.attributes.get("class") or "") if body else ""
    title = (tree.css_first("title").text() if tree.css_first("title") else "").strip()
    if title.endswith(":: Error"):
        h3 = tree.css_first("h3")
        return {"state": "not_found", "detail": h3.text().strip() if h3 else title}
    if "private_profile" in body_cls or tree.css_first(".profile_private_info"):
        return {"state": "private"}

    name_a = tree.css_first("a.persona_name_text_content")
    paging = tree.css_first(".workshopBrowsePagingInfo")
    total = None
    if paging:
        m = re.search(r"of ([\d,]+) entries", paging.text())
        total = int(m.group(1).replace(",", "")) if m else None

    now = datetime.now(timezone.utc)
    reviews = []
    for box in tree.css("div.review_box"):
        app_a = box.css_first("div.leftcol a")
        title_a = box.css_first("div.title a")
        href = app_a.attributes.get("href", "") if app_a else ""
        m = re.search(r"/app/(\d+)", href)
        vote_btn = box.css_first("[id^=RecommendationVoteUpBtn]")
        rid = (vote_btn.attributes.get("id") or "").replace("RecommendationVoteUpBtn", "") if vote_btn else None
        hours_txt = " ".join((box.css_first("div.hours").text() if box.css_first("div.hours") else "").split())
        h_rec = re.search(r"([\d,.]+) hrs on record", hours_txt)
        h_rev = re.search(r"([\d,.]+) hrs at review time", hours_txt)
        posted = " ".join((box.css_first("div.posted").text() if box.css_first("div.posted") else "").split())
        posted_part, _, edited_part = posted.partition("Last edited")
        header = " ".join((box.css_first("div.header").text() if box.css_first("div.header") else "").split())
        src = box.css_first("img.review_source")
        src_tip = (src.attributes.get("data-tooltip-text") or "") if src else ""
        award = box.css_first(".review_award_count")
        content = box.css_first("div.content")
        title_text = title_a.text().strip() if title_a else None
        reviews.append({
            "appId": int(m.group(1)) if m else None,
            "appUrl": href or None,
            "recommendationid": rid or None,
            "reviewUrl": title_a.attributes.get("href") if title_a else None,
            "voted_up": None if title_text is None else title_text == "Recommended",
            "reviewTitle": title_text,
            "hoursOnRecord": float(h_rec.group(1).replace(",", "")) if h_rec else None,
            "hoursAtReviewTime": float(h_rev.group(1).replace(",", "")) if h_rev
            else (float(h_rec.group(1).replace(",", "")) if h_rec else None),
            "postedDate": _parse_steam_date(posted_part, now),
            "lastEditedDate": _parse_steam_date(edited_part, now) if edited_part else None,
            "postedText": posted or None,
            "votes_up": _int_before(header, "helpful"),
            "votes_funny": _int_before(header, "funny"),
            "awardsCount": int(award.text().strip()) if award and award.text().strip().isdigit() else 0,
            "countedInOverallScore": None if not src_tip else "is counted" in src_tip,
            "review": content.text(separator="\n").strip() if content else None,
        })
    return {
        "state": "ok",
        "persona": name_a.text().strip() if name_a else None,
        "profileUrl": name_a.attributes.get("href") if name_a else None,
        "total": total,
        "reviews": reviews,
    }
