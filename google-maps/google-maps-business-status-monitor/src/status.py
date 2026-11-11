"""Business-health signals: claim status, closure, profile completeness.

What an SEO agency is actually shopping for is a business whose Google profile is
neglected: nobody has claimed it, it has no website, no phone, no hours. Those
signals are all present in a `tbm=map` search entry, so a prospecting run costs
one request per twenty businesses rather than one per business.

Claim status is the valuable one and it is read from a link, not a flag: Google
attaches an "Own this business?" action pointing at business.google.com/create
**only when the listing is unclaimed**. Verified against live data, and it
discriminates the way you would expect -- established restaurants came back 1/20
unclaimed while warung (small local eateries) came back 15/20.
"""

from __future__ import annotations

import json
from typing import Any

# The claim call-to-action. `claimbz` is the campaign tag Google puts on that
# link; both are checked because the URL shape changes more often than the tag.
CLAIM_MARKERS = ("business.google.com/create", "claimbz", "Own this business")

# Text Google uses for a closure. Kept separate from the boilerplate below.
PERMANENTLY_CLOSED = "Permanently closed"
TEMPORARILY_CLOSED = "Temporarily closed"

# "Place is closed or not here" is an option in Google's own suggest-an-edit
# menu and appears on EVERY record, open or not. Matching "closed" naively marks
# every business in the dataset as closed -- this was caught in reconnaissance.
CLOSED_BOILERPLATE = ("Place is closed or not here", "Report a legal issue",
                      "Report business conduct", "Suggest an edit")

# A listing that also fails these is a stronger pitch, not just an unclaimed one.
THIN_PROFILE_REVIEW_THRESHOLD = 5


def _raw(record: Any) -> str:
    try:
        return json.dumps(record, ensure_ascii=False)
    except (TypeError, ValueError):
        return ""


def is_unclaimed(record: Any) -> bool:
    """True when Google offers the 'Own this business?' claim action."""
    return any(marker in _raw(record) for marker in CLAIM_MARKERS)


def closure_status(record: Any, lead: dict) -> str:
    """'permanently_closed' | 'temporarily_closed' | 'operational'.

    Read from Google's own status wording. Everything else is reported as
    operational rather than guessed: Google excludes closed businesses from
    search results, so a closure almost only ever surfaces for a place supplied
    directly by URL or ID.
    """
    text = _raw(record)
    for phrase in CLOSED_BOILERPLATE:
        text = text.replace(phrase, "")

    open_now = lead.get("openNow") or ""
    if PERMANENTLY_CLOSED in text or PERMANENTLY_CLOSED in open_now:
        return "permanently_closed"
    if TEMPORARILY_CLOSED in text or TEMPORARILY_CLOSED in open_now:
        return "temporarily_closed"
    return "operational"


def assess(record: Any, lead: dict) -> dict:
    """Score one listing as a Google Business Profile opportunity."""
    unclaimed = is_unclaimed(record)
    closure = closure_status(record, lead)

    has_website = bool(lead.get("website"))
    has_phone = bool(lead.get("phone"))
    has_hours = bool(lead.get("openingHours"))
    reviews = lead.get("reviewsCount") or 0
    rating = lead.get("rating")

    issues: list[str] = []
    if unclaimed:
        issues.append("unclaimed")
    if not has_website:
        issues.append("no_website")
    if not has_phone:
        issues.append("no_phone")
    if not has_hours:
        issues.append("no_opening_hours")
    if reviews < THIN_PROFILE_REVIEW_THRESHOLD:
        issues.append("few_reviews")
    if rating is not None and rating < 4.0:
        issues.append("low_rating")
    if closure != "operational":
        issues.append(closure)

    # Weighted so the pitch-worthy signals dominate. An unclaimed listing is the
    # whole product for a GMB agency; a missing website is the upsell; the rest
    # are supporting evidence that the profile is neglected.
    score = 0
    score += 40 if unclaimed else 0
    score += 25 if not has_website else 0
    score += 10 if not has_phone else 0
    score += 10 if not has_hours else 0
    score += 10 if reviews < THIN_PROFILE_REVIEW_THRESHOLD else 0
    score += 5 if (rating is not None and rating < 4.0) else 0
    # A permanently closed listing is not a sales prospect, whatever else is wrong.
    if closure == "permanently_closed":
        score = 0

    return {
        "claimStatus": "unclaimed" if unclaimed else "claimed",
        "isUnclaimed": unclaimed,
        "businessStatus": closure,
        "isOperational": closure == "operational",
        "hasWebsite": has_website,
        "hasPhone": has_phone,
        "hasOpeningHours": has_hours,
        "reviewsCount": reviews,
        "opportunityScore": score,
        "opportunityIssues": issues,
        "issueCount": len(issues),
    }


def matches_filters(assessment: dict, options: dict) -> bool:
    """Apply the caller's prospecting filters to one assessed listing."""
    if options.get("onlyUnclaimed") and not assessment["isUnclaimed"]:
        return False
    if options.get("onlyWithoutWebsite") and assessment["hasWebsite"]:
        return False
    if options.get("onlyWithoutPhone") and assessment["hasPhone"]:
        return False
    if options.get("onlyClosed") and assessment["isOperational"]:
        return False
    if options.get("excludePermanentlyClosed") and assessment["businessStatus"] == "permanently_closed":
        return False
    minimum = options.get("minOpportunityScore")
    if minimum is not None and assessment["opportunityScore"] < int(minimum):
        return False
    return True


def summarise(rows: list[dict]) -> dict:
    """Area-level rollup: how much unclaimed opportunity is in this market."""
    total = len(rows)

    def pct(n: int) -> float:
        return round(100.0 * n / total, 2) if total else 0.0

    unclaimed = sum(1 for r in rows if r.get("isUnclaimed"))
    no_site = sum(1 for r in rows if not r.get("hasWebsite"))
    no_phone = sum(1 for r in rows if not r.get("hasPhone"))
    both = sum(1 for r in rows if r.get("isUnclaimed") and not r.get("hasWebsite"))
    perm = sum(1 for r in rows if r.get("businessStatus") == "permanently_closed")
    temp = sum(1 for r in rows if r.get("businessStatus") == "temporarily_closed")
    scores = [r.get("opportunityScore", 0) for r in rows]

    return {
        "businessesAssessed": total,
        "unclaimed": unclaimed,
        "unclaimedPercent": pct(unclaimed),
        "withoutWebsite": no_site,
        "withoutWebsitePercent": pct(no_site),
        "withoutPhone": no_phone,
        "unclaimedAndNoWebsite": both,
        "unclaimedAndNoWebsitePercent": pct(both),
        "permanentlyClosed": perm,
        "temporarilyClosed": temp,
        "averageOpportunityScore": round(sum(scores) / len(scores), 2) if scores else None,
        "highOpportunityCount": sum(1 for s in scores if s >= 65),
    }
