"""Sentiment scoring: VADER text polarity blended with the star rating.

Why a blend rather than either signal alone:

* The rating alone is coarse and often contradicts the text -- a 5-star review
  reading "staff were rude but the food saved it" is not purely positive, and
  3-star reviews are frequently strongly opinionated rather than neutral.
* VADER alone misreads short or idiomatic reviews ("not bad at all") and has no
  opinion at all on an empty rating-only review, which is a large share of
  Google Maps data.

VADER is lexicon-based and English-only, so it is applied only when the review
text is actually English. For other languages we use Google's own English
translation when the response carries one, and otherwise fall back to the
rating, flagging the record so consumers can tell the two apart.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Weights: text carries most of the signal, the rating anchors it.
TEXT_WEIGHT = 0.6
RATING_WEIGHT = 0.4

# When a confident text polarity contradicts an extreme rating, the rating wins.
# A lexicon cannot detect sarcasm -- "Highly thrilling experience" on a 1-star
# cancellation complaint scores +0.94 -- but the star rating is the reviewer's
# own explicit verdict, so it is the better ground truth for satisfaction.
CONFLICT_TEXT_WEIGHT = 0.25
CONFLICT_RATING_WEIGHT = 0.75
CONFLICT_TEXT_CONFIDENCE = 0.5      # |compound| above which the text is "confident"
CONFLICT_RATINGS = {1, 2, 5}        # ratings unambiguous enough to override

# Label cut-offs on the blended [-1, 1] score.
POSITIVE_AT = 0.15
NEGATIVE_AT = -0.15

_analyzer: SentimentIntensityAnalyzer | None = None


def _get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


@dataclass
class Sentiment:
    label: str              # positive | neutral | negative
    score: float            # blended, -1.0 .. 1.0
    method: str             # text+rating | rating-only | translated+rating
    textScore: float | None  # raw VADER compound, when text was scored
    ratingScore: float | None
    language: str | None
    # True when the text polarity contradicted an extreme rating. These are the
    # sarcastic and mixed reviews -- worth surfacing, not just correcting.
    ratingTextConflict: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def _label(score: float) -> str:
    if score >= POSITIVE_AT:
        return "positive"
    if score <= NEGATIVE_AT:
        return "negative"
    return "neutral"


def _rating_score(rating: int | None) -> float | None:
    """Map a 1-5 star rating onto -1 .. 1 (3 stars is the neutral midpoint)."""
    if not rating:
        return None
    return (float(rating) - 3.0) / 2.0


def score_review(
    text: str | None,
    rating: int | None,
    language: str | None = None,
    translated_text: str | None = None,
) -> Sentiment:
    """Score one review. Never raises -- a review with neither text nor rating
    is reported as neutral with method 'none' rather than silently dropped."""
    rating_component = _rating_score(rating)

    scoreable_text: str | None = None
    method = "rating-only"
    if text and (language or "en").lower().startswith("en"):
        scoreable_text = text
        method = "text+rating"
    elif translated_text:
        # Non-English review, but Google shipped an English translation.
        scoreable_text = translated_text
        method = "translated+rating"

    text_component: float | None = None
    if scoreable_text and scoreable_text.strip():
        text_component = _get_analyzer().polarity_scores(scoreable_text)["compound"]

    conflict = False
    if text_component is not None and rating_component is not None:
        conflict = (
            rating in CONFLICT_RATINGS
            and abs(text_component) >= CONFLICT_TEXT_CONFIDENCE
            and (text_component > 0) != (rating_component > 0)
        )
        if conflict:
            blended = (
                CONFLICT_TEXT_WEIGHT * text_component
                + CONFLICT_RATING_WEIGHT * rating_component
            )
        else:
            blended = TEXT_WEIGHT * text_component + RATING_WEIGHT * rating_component
    elif text_component is not None:
        blended = text_component
    elif rating_component is not None:
        blended = rating_component
        method = "rating-only"
    else:
        return Sentiment("neutral", 0.0, "none", None, None, language, False)

    blended = max(-1.0, min(1.0, blended))
    return Sentiment(
        label=_label(blended),
        score=round(blended, 4),
        method=method,
        textScore=round(text_component, 4) if text_component is not None else None,
        ratingScore=round(rating_component, 4) if rating_component is not None else None,
        language=language,
        ratingTextConflict=conflict,
    )


def summarise(records: list[dict]) -> dict:
    """Aggregate per-place sentiment and rating statistics."""
    total = len(records)
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    rating_hist = {str(i): 0 for i in range(1, 6)}
    scores: list[float] = []
    ratings: list[int] = []
    with_text = with_owner_response = with_photos = 0
    likes_total = conflicts = 0

    for record in records:
        sentiment = record.get("sentiment") or {}
        label = sentiment.get("label")
        if label in counts:
            counts[label] += 1
        if isinstance(sentiment.get("score"), (int, float)):
            scores.append(float(sentiment["score"]))
        if sentiment.get("ratingTextConflict"):
            conflicts += 1

        rating = record.get("rating")
        if isinstance(rating, int) and 1 <= rating <= 5:
            rating_hist[str(rating)] += 1
            ratings.append(rating)

        if record.get("text"):
            with_text += 1
        if record.get("ownerResponse"):
            with_owner_response += 1
        if record.get("photos"):
            with_photos += 1
        likes_total += record.get("likesCount") or 0

    def pct(value: int) -> float:
        return round(100.0 * value / total, 2) if total else 0.0

    return {
        "reviewsAnalysed": total,
        "sentimentCounts": counts,
        "sentimentPercent": {k: pct(v) for k, v in counts.items()},
        "averageSentimentScore": round(sum(scores) / len(scores), 4) if scores else None,
        "averageRating": round(sum(ratings) / len(ratings), 3) if ratings else None,
        "ratingHistogram": rating_hist,
        "reviewsWithText": with_text,
        "reviewsWithOwnerResponse": with_owner_response,
        "ownerResponseRatePercent": pct(with_owner_response),
        "reviewsWithPhotos": with_photos,
        "totalLikes": likes_total,
        "ratingTextConflicts": conflicts,
    }
