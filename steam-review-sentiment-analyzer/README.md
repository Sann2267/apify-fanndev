# Steam Review & Sentiment Analyzer

Turn Steam reviews into a ready-made sentiment report: the official score, recent vs lifetime trend, review-bomb detection, sentiment per language, positivity by playtime, the complaints players upvote most, and full review exports. No login, no API key.

## Why use this actor

- **Answers in one row per game.** Summary mode returns Steam's score, the 30-day and 3-month trend, review-bomb months, the score in each language, and the words that separate negative reviews from positive ones.
- **Every review, not just the first page.** Newest-first reaches the full review history. A date window stops the scan early, so daily incremental runs stay cheap.
- **Scores Steam does not show you.** You get the score of key buyers vs Steam buyers, positivity by hours played, Steam Deck vs desktop, and reviews whose text contradicts their thumbs-up.
- **Review-bomb detection.** It flags months where negative share and review volume both jump far above the game's own baseline. On HELLDIVERS 2 it flags May 2024, the month of the PlayStation-account review bomb.
- **Five modes in one actor:** summary, reviews, history, languages and user reviews.
- Stable JSON with automatic retries. Export to JSON, CSV or Excel, or schedule it on Apify.

## How it works

1. Enter games as Steam app IDs, store links or plain names ("Stardew Valley").
2. Pick a mode. **Summary** is the default.
3. The actor reads Steam's public review data, applies your filters (language, purchase type, playtime, dates, positive/negative), and computes the analytics.
4. You get one clean dataset with a `recordType` on every row, plus ready-made table views for summaries, reviews, and history/languages.

You have no scrapers, browsers or blocks to babysit. If Steam slows the actor down, it paces itself and retries automatically.

## Modes

| Mode | Output | One row per |
| --- | --- | --- |
| `summary` | Sentiment report | game |
| `reviews` | Full review text, author stats, playtime, votes, text sentiment | review |
| `history` | Positive/negative counts per month, plus daily counts for the last 30 days, with review-bomb flags | period |
| `languages` | Score and share for each of Steam's 30 review languages | language |
| `userReviews` | Every public review a Steam user has written | review |

## Input

```json
{
    "mode": "summary",
    "apps": ["1091500", "https://store.steampowered.com/app/553850/HELLDIVERS_2/", "Stardew Valley"],
    "sampleSize": 300,
    "proxyConfiguration": {"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}
}
```

```json
{
    "mode": "reviews",
    "apps": ["1091500"],
    "maxReviewsPerApp": 2000,
    "sortBy": "recent",
    "language": "english",
    "startDate": "2026-10-01",
    "endDate": "2026-10-05",
    "minPlaytimeHours": 50
}
```

```json
{ "mode": "userReviews", "steamUsers": ["https://steamcommunity.com/profiles/76561198112703551"], "maxReviewsPerApp": 50 }
```

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | `summary`, `reviews`, `history`, `languages` or `userReviews` |
| `apps` | array | App IDs, store or community links, or game names. A name is matched to the first Steam search result, and the row records that in `resolvedFrom: "name"`. |
| `steamUsers` | array | Profile links, SteamID64s or custom profile names (userReviews mode) |
| `maxReviewsPerApp` | integer | Cap per game or user (reviews / userReviews) |
| `sortBy` | string | `recent` (newest first, reaches every review), `updated`, or `all` (most helpful: Steam limits this order to reviews from the last 365 days) |
| `language` | string | `all` or a Steam language code such as `english`, `schinese` or `brazilian`. Unknown codes are rejected, not silently ignored. |
| `purchaseType` | string | `all`, `steam` (what the store score counts) or `non_steam_purchase` (key activations) |
| `reviewType` | string | `all`, `positive` or `negative` (reviews mode) |
| `startDate` / `endDate` | date | Only reviews posted in this window |
| `minPlaytimeHours` / `maxPlaytimeHours` | integer | Hours the author had played when writing the review |
| `helpfulDayRange` | integer | Window for the most-helpful order (max 365) |
| `includeOffTopicReviews` | boolean | Include reviews from periods Steam marked as off-topic |
| `textSentiment` | boolean | Adds a sentiment score to English reviews and flags text that contradicts the thumb |
| `sampleSize` | integer | Summary: how many newest reviews feed the playtime, Steam Deck and refund breakdowns (0 = totals and trend only) |
| `languages` | array | Summary: languages to break down (default: the 11 largest). Languages mode: default is all 30. |
| `country` | string | Store country for prices and name search (default `us`) |
| `maxConcurrency` | integer | Games processed in parallel |
| `proxyConfiguration` | object | Residential proxy support. It is optional, but it makes large jobs much faster. |

## Output

### Summary (real output, HELLDIVERS 2, truncated)

```json
{
  "_input": "553850",
  "_source": "S1-appreviews+histogram",
  "_scrapedAt": "2026-10-10T21:24:51Z",
  "recordType": "SUMMARY",
  "appId": 553850,
  "appName": "HELLDIVERS™ 2",
  "appType": "game",
  "storeUrl": "https://store.steampowered.com/app/553850/",
  "developers": [
    "Arrowhead Game Studios"
  ],
  "publishers": [
    "PlayStation Publishing LLC"
  ],
  "releaseDate": "Feb 8, 2024",
  "comingSoon": false,
  "isFree": false,
  "price": "$39.99",
  "priceCurrency": "USD",
  "discountPercent": 0,
  "genres": [
    "Action"
  ],
  "metacriticScore": null,
  "storeRecommendationsTotal": 841340,
  "appDetailsAvailable": true,
  "resolvedFrom": "appId",
  "steamScore": {
    "review_score": 6,
    "review_score_desc": "Mostly Positive",
    "total_positive": 643258,
    "total_negative": 197776,
    "total_reviews": 841034,
    "positiveRatio": 0.7648
  },
  "allPurchasesScore": {
    "review_score": 6,
    "review_score_desc": "Mostly Positive",
    "total_positive": 882506,
    "total_negative": 283771,
    "total_reviews": 1166277,
    "positiveRatio": 0.7567
  },
  "nonSteamPurchaseShare": 0.2789,
  "trend": {
    "rollupType": "month",
    "firstReviewPeriod": "2024-02-08T00:00:00Z",
    "lastReviewPeriod": "2026-10-10T00:00:00Z",
    "lifetime": {
      "recommendations_up": 559185,
      "recommendations_down": 345886,
      "positiveRatio": 0.6178,
      "reviewScoreDesc": "Mixed"
    },
    "last30Days": {
      "recommendations_up": 3494,
      "recommendations_down": 556,
      "positiveRatio": 0.8627,
      "reviewScoreDesc": "Very Positive"
    },
    "last3Periods": {
      "recommendations_up": 9813,
      "recommendations_down": 1860,
      "positiveRatio": 0.8407,
      "reviewScoreDesc": "Very Positive"
    },
    "recentVsLifetimeDelta": 0.2449
  },
  "reviewBombCandidates": [
    {
      "periodStart": "2024-05-01T00:00:00Z",
      "recommendations_up": 114571,
      "recommendations_down": 228757,
      "negativeShare": 0.6663,
      "baselineNegativeShare": 0.1498,
      "volumeVsMedian": 43.57
    }
  ],
  "languageBreakdown": [
    {
      "language": "english",
      "review_score": 8,
      "review_score_desc": "Very Positive",
      "total_positive": 663037,
      "total_negative": 160776,
      "total_reviews": 823813,
      "positiveRatio": 0.8048,
      "shareOfAllReviews": 0.7064
    },
    {
      "language": "schinese",
      "review_score": 4,
      "review_score_desc": "Mostly Negative",
      "total_positive": 38134,
      "total_negative": 78916,
      "total_reviews": 117050,
      "positiveRatio": 0.3258,
      "shareOfAllReviews": 0.1004
    },
    "... 9 more"
  ],
  "recentSample": {
    "sampleSize": 300,
    "sampleOldestReview": "2026-10-09T11:39:02Z",
    "sampleNewestReview": "2026-10-10T21:01:42Z",
    "reviews": 300,
    "positiveRatio": 0.86,
    "byPlaytimeAtReview": [
      {
        "bucket": "0-2h",
        "reviews": 5,
        "positiveRatio": 0.4
      },
      {
        "bucket": "2-10h",
        "reviews": 54,
        "positiveRatio": 0.8333
      },
      "... 3 more"
    ],
    "medianPlaytimeAtReviewHours": {
      "positive": 34.8,
      "negative": 46.2
    },
    "steamDeck": {
      "yes": {
        "reviews": 4,
        "positiveRatio": 1.0
      },
      "no": {
        "reviews": 296,
        "positiveRatio": 0.8581
      }
    },
    "textSentiment": {
      "englishReviewsScored": 157,
      "avgCompound": 0.3754,
      "labels": {
        "positive": 103,
        "neutral": 35,
        "negative": 19
      },
      "recommendedButNegativeText": 12,
      "notRecommendedButPositiveText": 9
    }
  },
  "complaintAnalysis": {
    "basis": "most helpful English reviews, last 365 days",
    "reviewsAnalysed": {
      "positive": 100,
      "negative": 100
    },
    "topNegativeTerms": [
      {
        "term": "arrowhead",
        "reviews": 49,
        "share": 0.49,
        "shareOtherSide": 0.08,
        "lift": 5.56
      },
      {
        "term": "balance",
        "reviews": 37,
        "share": 0.37,
        "shareOtherSide": 0.03,
        "lift": 9.5
      },
      {
        "term": "players",
        "reviews": 41,
        "share": 0.41,
        "shareOtherSide": 0.08,
        "lift": 4.67
      },
      "... 12 more"
    ],
    "topPositiveTerms": [
      {
        "term": "friends",
        "reviews": 26,
        "share": 0.26,
        "shareOtherSide": 0.11,
        "lift": 2.25
      },
      {
        "term": "democracy",
        "reviews": 19,
        "share": 0.19,
        "shareOtherSide": 0.09,
        "lift": 2.0
      },
      "... 13 more"
    ],
    "mostHelpfulNegative": [
      {
        "recommendationid": "224415064",
        "votes_up": 9867,
        "playtimeAtReviewHours": 543.5,
        "createdAt": "2026-04-30T09:37:29Z",
        "excerpt": "I genuinely cannot understand how you keep getting this wrong.\n\nYou had lightning in a bottle and decided to pry the lid off yourself. You consistently snatch defeat from the jaws of victory, and at t...",
        "reviewUrl": "https://steamcommunity.com/profiles/76561198159787357/recommended/553850/"
      },
      "... 4 more"
    ],
    "mostHelpfulPositive": [
      "... 5 more"
    ]
  },
  "sampleFilters": {
    "language": "all",
    "purchase_type": "all",
    "playtime_filter_min": null,
    "playtime_filter_max": null
  }
}
```

### Review (real output, truncated)

```json
{
  "_input": "1091500",
  "_source": "S1-appreviews",
  "recordType": "REVIEW",
  "appId": 1091500,
  "appName": "Cyberpunk 2077",
  "reviewUrl": "https://steamcommunity.com/profiles/76561199166668401/recommended/1091500/",
  "createdAt": "2026-10-10T20:38:02Z",
  "playtimeAtReviewHours": 72.7,
  "recommendationid": "237406104",
  "author": {"steamid": "76561199166668401", "personaname": "H3rbatka_", "num_reviews": 2, "...": "4 more"},
  "language": "polish",
  "review": "Bardzo fajna gra mozna robic duzo fajnych rzeczy jak sie chce fajne buildy fajne samochody tylko brakuje mi ciekawszych opcji customizowania samochodow troche. historia wysmienita i postacie tez...",
  "voted_up": true,
  "votes_up": 0,
  "weighted_vote_score": 0.5,
  "steam_purchase": true,
  "received_for_free": false,
  "refunded": false,
  "written_during_early_access": false,
  "primarily_steam_deck": false,
  "textSentiment": null,
  "sentimentMismatch": null
}
```

Text sentiment is computed for English reviews only, so this Polish review has `null`.

### History (real output: the flagged month)

```json
{
  "recordType": "HISTORY",
  "appId": 553850,
  "appName": "HELLDIVERS™ 2",
  "period": "month",
  "periodStart": "2024-05-01T00:00:00Z",
  "recommendations_up": 114571,
  "recommendations_down": 228757,
  "totalReviews": 343328,
  "positiveRatio": 0.3337,
  "reviewScoreDesc": "Mostly Negative",
  "isReviewBombCandidate": true
}
```

### Language (real output)

```json
{
  "recordType": "LANGUAGE",
  "appName": "HELLDIVERS™ 2",
  "language": "schinese",
  "purchase_type": "steam",
  "review_score_desc": "Mostly Negative",
  "total_reviews": 67447,
  "positiveRatio": 0.3135,
  "shareOfAllReviews": 0.0802,
  "positiveRatioVsAllLanguages": -0.4513,
  "rank": 2
}
```

### User review fields

`steamProfileUrl`, `personaName`, `userTotalReviews`, `appId`, `recommendationid`, `voted_up`, `hoursOnRecord`, `hoursAtReviewTime`, `postedDate`, `lastEditedDate`, `votes_up`, `votes_funny`, `awardsCount`, `countedInOverallScore`, `review`, `textSentiment`.

### Error rows

Failed inputs are never dropped silently. They come back as rows with `_error`: `not_found` (no such game or profile), `private_profile`, `no_reviews` (nothing matches your filters), or `invalid_input`.

## Good to know

- **Three totals that don't match, and why.** `steamScore` counts Steam purchases only, which is the number on the store page. `allPurchasesScore` adds key activations. `trend` comes from Steam's review graph, which *includes* review-bomb periods that the store score leaves out. That is why HELLDIVERS 2 shows "Mixed" lifetime in `trend` but "Mostly Positive" in `steamScore`.
- **Most-helpful order covers one year at most.** Use `recent` to export a game's complete history.
- **Some reviews have no text.** Steam allows thumbs-only reviews, so `review` can be an empty string.
- **Speed.** Steam serves 100 reviews per request. Without a proxy, one run reads about 4,500 reviews per minute. With residential proxies, each game gets its own pace.
- **User reviews** need a public profile. Private profiles return `private_profile`.
