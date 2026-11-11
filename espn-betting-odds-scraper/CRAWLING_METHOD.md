# CRAWLING_METHOD — espn-betting-odds-scraper

Recon and build: **2026-09-18**. All figures below were measured, not assumed.

Origin: Babak 49 candidate #2 ("sports betting odds"), the row that was marked
`[BUILD]` for a proven-open surface and then left unbuilt when Babak 50 priced
the vein at $53/month. Built here because the surface turned out to carry three
things the money ranking never looked at: **player props** (659 markets on a
single NFL game), **futures boards**, and **both ends of every line**, from which
movement can be derived.

---

## 1. Probe matrix

Plain HTTP, no cookie, no key, residential IP (Indonesia). Ladder order
`chrome124 → firefox133 → safari17_0 → chrome99_android → edge101`; the first
profile won everywhere, so the rest were never needed locally.

| Target | Status | Bytes | Verdict |
| --- | ---: | ---: | --- |
| `sports.core.api.espn.com/v2/sports` | 200 | 1.4 KB | 17 sports |
| `…/leagues/nfl/events?limit=5` | 200 | 684 B | pointers only |
| `…/competitions/<id>/odds` | 200 | 12.7 KB | **2 books, full lines** |
| `…/odds/100/propBets?limit=1000` | 200 | — | **659 props, one page** |
| `…/seasons/2026/futures?limit=100` | 200 | — | 18 markets, 543 book lines |
| `…/competitions/<id>/predictor` | 200 | 3.3 KB | BPI win projection |
| `…/leagues/nfl/providers?limit=200` | 200 | — | 71 sportsbooks |
| `site.api.espn.com/…/nfl/scoreboard` | 200 | 276 KB | 16 events, **`odds: null`** |
| `site.api.espn.com/…/nfl/teams` | 200 | 135 KB | 32 teams, one request |

`site.api.espn.com` was recorded as **403** in Babak 49. It is **200** today —
see corrections below.

No WAF vendor markers appeared in any response. No `cf-ray`, no challenge body,
no captcha. The Actor still carries the TLS ladder because of the Google Hotels
lesson: the profile that wins locally is not always the profile that wins from
Apify's exit IPs.

---

## 2. Gotchas

### 1. The two hosts disagree about how to write a date, and one of them lies

`sports.core.api.espn.com` accepts three forms: `dates=20260920`, `dates=2026`
and the range `dates=20260901-20261001` (49 NFL fixtures).

`site.api.espn.com` accepts the first two and **rejects the range** — but it
does not reject it the same way twice:

| League | Query | Answer |
| --- | --- | --- |
| NFL | `scoreboard?dates=20260901-20261001` | **HTTP 400** |
| EPL | `scoreboard?dates=20260920-20261005` | **HTTP 200, `events: []`** |

The soccer case is the dangerous one: a scraper built on the site host would
report "no Premier League fixtures in that window" and be believed. Every date
window in this Actor is therefore resolved on the core host, and mode
`reference` re-tests both hosts on every run so a change shows up as a diff.

### 2. `$ref` pointers are not fetchable as printed — two separate rewrites

ESPN's core API is HATEOAS: lists return `{"$ref": ...}` and nothing else.
Those pointers need fixing twice before they can be used.

* Every pointer is written with the **`http://`** scheme.
* Pointers inside `site.api.espn.com/…/summary?event=<id>` name the host
  **`sports.core.api.espn.pvt`** — ESPN's internal name, which resolves
  nowhere. In one summary response **436 of 436** pointers carried `.pvt` and
  **zero** carried the public host. Following them verbatim fails every time,
  and the failure looks like a network problem rather than a data problem.

`client.normalize_ref()` does both, and `test_local.py` asserts it.

### 3. `propBets` pages at whatever `limit` you send

`limit=3` → `pageCount: 220`. `limit=25` → 27 pages. `limit=1000` → **1 page,
659 items**. There is no server-side default worth relying on; the page size is
the limit. Everything here requests 1000.

### 4. The feed publishes 659 prop rows for 521 distinct markets

Of 659 rows on one NFL game, **138 are exact duplicates** — same athlete, same
market type, identical `open`, `current`, `provider`, `team` and `lastUpdated`.
Counting rows reports 659 markets where the book offers 521. The Actor keys on
that tuple, drops the repeats and logs how many it dropped. Same family as the
Blibli `_basic` omissions and the Medium hollow-post cache: **a row count is
not evidence of a distinct record.**

### 5. An empty odds list is an answer, not a block

Books post lines close to start time. On 2026-09-18, NFL and MLB fixtures on
the day returned providers; NBA and NHL fixtures six weeks out returned HTTP
200 with `count: 0`. So did every UFC card months ahead. Those fixtures are
emitted with `hasOdds: false` and a note, so "not priced yet" is visibly
different from "not fetched" (which is an `ERROR` record).

### 6. Event id ≠ competition id, and only sometimes

For NFL, NBA, MLB and soccer the two ids matched on every fixture sampled. For
UFC they do **not**: event `600057024` carries competition `401848704`. Code
that builds `/events/<id>/competitions/<id>/odds` from the event id alone works
for four sports and silently 404s on the fifth. The competition id is always
read out of the event payload.

### 7. Name resolution is the real cost, and it collapses

659 props resolve from **47 distinct athletes**; a futures board resolves from
~360 distinct runners. Without a cache the prop job is 659 requests; with one it
is 47. Teams are cheaper still — `site.api…/teams` hands over all 32 in a single
request, though competition-style leagues (UFC, golf, tennis) have no team list
and answer 404, which is why the prefill is best-effort with a per-team
fallback.

### 8. Line movement and implied probability are derived, not published

ESPN publishes `open`, `close` and `current` blocks and leaves the arithmetic to
the reader; it publishes American prices and no probabilities. Both are computed
in `extractor.py`. The vig is deliberately **not** removed — the two sides of a
moneyline sum to slightly over 1, and that excess is the book's margin. The test
asserts the sum lands in 0.95–1.25, which is what a real book looks like and
what a parsing bug does not.

### 9. The live in-play feed writes `0` where it means "nothing"

A fixture can carry two entries for the same sportsbook: the pre-match board and
a `- Live Odds` feed. On a game that is not in play, that second entry returns

```json
{ "overUnder": 0.0, "overOdds": 0.0, "underOdds": 0.0,
  "price": 0.0, "awayTeamOdds": { "moneyLine": 0 }, "spread": 5.5 }
```

— zeros in every price slot **next to a populated, real point spread**, so the
row does not look broken. Averaging `overUnder` across books would pull the
consensus toward zero, and no exception would ever be raised. Those fields are
emitted as `null` and the row carries `hasPlaceholderZeros: true` and
`isLiveOddsFeed: true`, so the repair is visible rather than silent.

Point spreads are deliberately **not** put through the same filter: a spread of
0 is a real pick-em line, especially in soccer.

The live entry is also **time-bound**: it appears on fixtures at or near kick-off
and is absent hours later. A run that returns one book per fixture and a run that
returns two are both correct.

### 10. The same sportsbook has two spellings, so join on the id

Provider `100` is `"Draft Kings"` in the `odds` response and `"DraftKings"` in
the `futures` response — same session, same IP, same minute. Grouping a dataset
by `providerName` would split one book into two. `providerId` is the join key;
the name is passed through as the source writes it.

---

## 3. Corrections to earlier research

| Earlier claim | Measured 2026-09-18 |
| --- | --- |
| Babak 49 #2: "`site.api.espn.com` is **403** from this IP — two hosts, different treatment" | **200.** `/scoreboard` 276 KB, `/teams` 135 KB, `/summary` all answer. The two hosts do differ, but on *content* (the site host has no odds) and on *date grammar*, not on access |
| Babak 50 B: "sports odds — 163 actors sharing $53/month, cheapest vein ever measured" | The price stands, but it was measured against generic scoreboard scrapers. The surface also carries 659 player props per game, full futures boards and both ends of every line — none of which the ranked incumbents sell |

---

## 4. Candidates probed in the same pass and **not** built

| Candidate | Origin | Measured today | Verdict |
| --- | --- | --- | --- |
| **Keyword search volume** | Babak 49 #5, the highest-money row left ($929/mo) | No open surface publishes volume. `api.keywordsur.fr` **DNS gone**; `app.neilpatel.com/api/keyword_info` **401**; `keywordtool.io/search/keywords/google` **404**; Ahrefs' free generator is a client-side esbuild bundle with **zero** API paths in page or bundle; Keyword Planner redirects to `accounts.google.com`. What *is* open is suggestions without volume — Google, Bing, YouTube and Amazon autocomplete all 200 | **SKIP, with evidence.** Volume is a paid/authenticated field everywhere it exists |
| **Google Lens** | Babak 49 #6 | `lens.google.com/uploadbyurl` returns **200 / 92 KB** — and zero result markers: no `AF_initDataCallback`, no `data:image`, no visual-match text, one outbound host (`support.google.com`). A JS shell | **SKIP.** Same false positive shape as Apple Maps in Babak 50 |
| **TikTok Shop** | Babak 49 #4 | `shop.tiktok.com/view/product/<id>` → **5.7 KB `<title>Security Check</title>`** | **SKIP.** Consistent with the TikTok verdict already in portfolio memory |
| **Tech-stack detector** | Babak 49 #7 | Technically open (fetch any site, fingerprint it) and not built here — it is a fingerprint library, not a data surface, and Babak 49's own verdict was "zero data moat" | Deferred, not blocked |
