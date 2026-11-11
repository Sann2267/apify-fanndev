"""Offline + live checks for the page reviews scraper.

    python test_local.py            # live: read a page with many reviews
    python test_local.py --offline  # parser only, no network
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys

sys.path.insert(0, ".")

from src.fbcore import FacebookSession  # noqa: E402
from src.main import epoch_from_date, read_pages  # noqa: E402
from src.parser import (  # noqa: E402
    _vote,
    matches_filters,
    page_ref,
    parse_reviews,
    summarise,
)
from src.reviews import PageUnavailable, fetch_reviews, fetch_reviews_tab  # noqa: E402


class Log:
    def info(self, message):
        print(f"  [info] {message}")

    def warning(self, message):
        print(f"  [warn] {message}")


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))
    return bool(condition)


def offline_checks() -> bool:
    ok = True
    ok &= check("slug from URL", page_ref("https://www.facebook.com/dominos/reviews") == "dominos")
    ok &= check("bare slug kept", page_ref("dominos") == "dominos")
    ok &= check("reserved path rejected", page_ref("https://facebook.com/groups/x") is None)
    ok &= check("pages read from both inputs",
                read_pages({"pages": ["a"], "startUrls": [{"url": "facebook.com/b"}]}) == ["a", "b"])
    ok &= check("date parsed", epoch_from_date("2026-01-01") == 1767225600)

    # The negative must win: "doesn't recommend" also contains "recommend".
    ok &= check("negative vote read", _vote("Mike  doesn't recommend Domino's Pizza.") is False)
    ok &= check("positive vote read", _vote("Ana  recommends Domino's Pizza.") is True)
    ok &= check("unknown sentence stays null", _vote("Ana a recomandat Domino's.") is None)

    # Shaped like the real payload: the recommend sentence, the written body and
    # the engagement arrive on three separate nodes that share only the post id
    # -- one of them expressing it as a base64 story id.
    post_id = "122258226368098864"
    story_id = base64.b64encode(f"S:_I61552965944326:{post_id}".encode()).decode()
    payload = {
        "titleNode": {
            "post_id": post_id,
            "title": {"text": "Mike Phipps  doesn't recommend Domino's Pizza."},
            "actors": [{"name": "Mike Phipps", "id": "61552965944326"}],
            "attachments": [{"styles": {"attachment": {"tags": ["Disappointing food", "Casual"]}}}],
        },
        "bodyNode": {
            "id": story_id,
            "message": {"text": "Pizza arrived cold."},
            "creation_time": 1_789_862_630,
            "permalink_url": "https://www.facebook.com/mike/posts/x",
        },
        "feedbackNode": {
            "id": base64.b64encode(f"feedback:{post_id}".encode()).decode(),
            "i18n_reaction_count": "4",
            "comments": {"total_count": 2},
        },
    }
    reviews = parse_reviews(payload)
    ok &= check("review parsed", len(reviews) == 1)
    review = reviews[0]
    ok &= check("vote", review["isRecommended"] is False)
    ok &= check("reviewer", review["reviewerName"] == "Mike Phipps")
    ok &= check("body text", review["reviewText"] == "Pizza arrived cold.")
    ok &= check("tags", review["tags"] == ["Disappointing food", "Casual"])
    ok &= check("engagement", (review["reactionCount"], review["commentCount"]) == (4, 2))

    ok &= check("onlyRecommended drops a negative",
                matches_filters(review, {"onlyRecommended": True}) is False)
    stats = summarise([review])
    ok &= check("summary", stats["notRecommended"] == 1 and stats["sampleRecommendPercent"] == 0.0,
                json.dumps(stats))
    return ok


async def live_checks() -> bool:
    ok = True
    async with FacebookSession(log=Log()) as session:
        print("\n-- a page with reviews switched on --")
        html, summary = await fetch_reviews_tab(session, "dominos")
        ok &= check("rating summary read", bool(summary["ratingSummaryText"]),
                    summary["ratingSummaryText"])
        ok &= check("percent parsed", isinstance(summary["recommendPercent"], float),
                    str(summary["recommendPercent"]))
        ok &= check("review count parsed", isinstance(summary["reviewCount"], int),
                    str(summary["reviewCount"]))

        reviews, meta = await fetch_reviews(session, html, summary["reviewsUrl"], 12, log=Log())
        ok &= check("reviews returned", len(reviews) >= 3,
                    f"{len(reviews)} in {meta['requestsMade']} request(s)")
        ok &= check("pagination went past the first batch", len(reviews) > 3, str(len(reviews)))
        votes = [r["isRecommended"] for r in reviews]
        ok &= check("votes read", any(v is not None for v in votes), str(votes[:8]))
        texts = [r for r in reviews if (r["reviewText"] or "").strip()]
        ok &= check("review bodies present", len(texts) >= 2, f"{len(texts)} with text")
        if texts:
            sample = texts[0]
            print("    sample:", json.dumps(
                {k: (str(sample[k])[:70] if sample[k] is not None else None)
                 for k in ("reviewerName", "isRecommended", "createdAtIso", "tags",
                           "reviewText")}, ensure_ascii=False))

        print("\n-- a slug that does not exist --")
        try:
            await fetch_reviews_tab(session, "zz-not-a-real-page-98765")
            ok &= check("missing page raises", False, "no exception")
        except PageUnavailable as exc:
            ok &= check("missing page raises PageUnavailable", True, str(exc)[:60])
    return ok


def main() -> int:
    print("== offline ==")
    ok = offline_checks()
    if "--offline" not in sys.argv:
        print("\n== live ==")
        ok = asyncio.run(live_checks()) and ok
    print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
