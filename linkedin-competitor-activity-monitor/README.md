# LinkedIn Top Voice & Competitor Activity Monitor

Point this at any LinkedIn person or company and get their content strategy as numbers: how often they post, in what format, at what length, with which hashtags — and which of those choices actually earns engagement from their audience.

**No cookie, no login, no account at risk.** LinkedIn embeds an account's recent posts, with full text and timestamps, in the page it serves to logged-out visitors. That is the entire data source.

## What you get

One `ACCOUNT` row per person or company:

```json
{
  "accountName": "Satya Nadella",
  "accountType": "PERSON",
  "followers": 12177102,
  "postsAnalysed": 6,
  "daysCovered": 9,
  "postsPerWeek": 4.67,
  "avgReactions": 4378.2,
  "medianReactions": 3574.0,
  "maxReactions": 12195,
  "engagementRatePct": 0.036,
  "mediaMix": { "TEXT": 3, "LINK": 3 },
  "avgTextLength": 600,
  "topHashtags": [],
  "hashtagUsagePct": 0.0
}
```

plus one `POST` row per analysed post with its text, date, reactions, hashtags and length.

**`engagementRatePct` is the number that matters.** Raw reaction counts only tell you who has the bigger audience. Reactions per post divided by followers is what lets you say that a 50-reaction post from a 2,000-follower account is outperforming a 500-reaction post from an account with twelve million.

`medianReactions` sits next to `avgReactions` on purpose: one viral post drags an average badly, and the median is the better read on what a typical post does.

## The two limits, stated plainly

**LinkedIn embeds roughly the last 6–10 posts per account.** Not thirty, not a full archive. That is enough to characterise a posting style — and running this on an Apify schedule turns those snapshots into a real time series — but it is not a backfill tool. Every `ACCOUNT` row carries `postsAnalysed`, `daysCovered`, `firstPostAt` and `lastPostAt` so you always know the window you are looking at.

**Company pages embed no engagement data at all.** Member profiles embed reaction counts with each post; company pages embed only the text and date. Reporting those missing counts as zero would make every company look like it gets no engagement, so this actor leaves them **null** instead, and flags it with `engagementDataAvailable: false`.

Turn on `fetchPostEngagement` to fix it properly: the actor then opens each company post's own permalink and reads the true reaction and comment counts. It costs one extra request per post, which is why it is opt-in rather than always on.

## Universities do not work

LinkedIn blocks `/school/` pages outright for logged-out visitors — HTTP 999 on every path tried, including the `/company/` alias that redirects there. That is structural, not rate limiting: it does not clear with delays, and no proxy changes it. Universities cannot be monitored with this actor, and the input schema says so rather than letting you discover it from an empty dataset.

## Input

```json
{
  "profileUrls": ["satyanadella", "https://www.linkedin.com/in/someone-else"],
  "companyUrls": ["anthropicresearch", "openai"],
  "fetchPostEngagement": true,
  "minReactions": 0
}
```

Handles and slugs work as well as full URLs. `minReactions` drops low performers before the metrics are computed, which turns the question from "what is their average post" into "what does their good content look like".

## Who this is for

- **Social media agencies** — a competitive content report on a client's rivals, produced in one run instead of an afternoon of scrolling.
- **Brand analysts** — posting cadence and format mix tracked over time, on a schedule.
- **Founders and marketers** — find out whether the accounts you are benchmarking against are actually outperforming you, or just bigger.

## Rate gating

LinkedIn answers request bursts with **HTTP 999** and a ~1.5 KB stub page. Three back-to-back requests were enough to trip it in testing; the same URLs answered 200 again after a four-second pause. It is per-IP and per-burst, and it is **not** a TLS fingerprint gate — five browser fingerprints all returned 200 on the same page.

So the actor sleeps a random 3–8 seconds between page loads, backs off exponentially when gated, and rotates fingerprints. If you monitor many accounts in one run and see rate-gate warnings, raise both delay bounds or enable a proxy.

## Related actors

- **LinkedIn Post Engagers Scraper** — who engaged with a specific post, with their comments.
- **LinkedIn Newsletter & Article Scraper** — long-form content and its performance.
