# Clutch.co — crawling method

Recon and build date: **2026-09-18**. Everything below was measured against the
live site — first from a residential IP in Indonesia, then re-measured from
Apify's datacenter range by the Actor's own `reference` mode, because the two do
not agree. Nothing is carried over from earlier notes without being re-run.
Probe scripts: `scratchpad/probe54.py` through `probe54g.py`, matrix output in
`output/probe54.json`. Shipped as `fanndev/clutch-agency-directory-scraper`
build 0.0.3; all five modes verified on the platform.

## Why this target

`actors_researcher_v2.md` (2026-09-15) ranks clutch.co as recommendation **#2**
in its execution order and the **#1 build** candidate: shelf MRR **$629/month**,
29 sellers of which only **3 actually charge**, and a surface already proven
open. The two paying incumbents charge **FLAT $40** — `epctex/clutchco-scraper`
(13.1% failure rate, u30 down to 7) and `curious_coder/clutch-scraper` (u30 8).

Note this **corrects Babak 49**, which skipped Clutch on a stale verdict of
"37 sellers". The seller count is real but almost all of them charge nothing;
what matters is who collects, and that is three.

## Surface

| Layer | Path | What it carries |
|---|---|---|
| Category listing | `/<slug>`, `/<cc>/<slug>`, `/<slug>/<city>` | Agency rows with every lead attribute. 96,607 companies over 1,933 pages on `/web-developers` alone |
| Profile | `/profile/<slug>` | One `LocalBusiness` JSON-LD block (17.7 KB) + summary strip + focus charts |
| Reviews | `/profile/<slug>?page=N` | ~10 review blocks per page, each with four sub-ratings |
| Category index | `/sitemap-directory-{1..7}.xml` | 10,000 directory URLs per shard, ~70,000 in total |

No login, no cookie handshake, no token. Plain HTTP over one `Session`.

## WAF profile — Cloudflare, gating on TLS **and on the IP**

Full ladder, same URL, same minute — measured twice: locally (residential line,
Indonesia) and again by the Actor's own `reference` mode from Apify's datacenter
range.

| Profile | Local | Apify platform | |
|---|---:|---:|---|
| `safari17_0` | 200 / 1.45 MB | **200 / 2.70 MB** | ✅ both |
| `firefox133` | 200 / 1.45 MB | **200 / 2.70 MB** | ✅ both |
| `chrome124` | **200 / 1.46 MB — local leader** | **403 / 5.9 KB** | 🔄 **flips** |
| `chrome110` | 403 / 5.9 KB | 403 / 5.9 KB | ❌ |
| `edge101` | 403 / 6.0 KB | 403 / 6.0 KB | ❌ |
| `chrome99_android` | 403 / 6.0 KB | 403 / 5.9 KB | ❌ |

Three of six challenged locally — the exact case `.ai/CLAUDE.md` rule 2 warns
about, where one failing profile would have condemned an open site. `chrome131`
was not tried (widely blocklisted in 2026).

**The profile that led locally is refused from the platform.** This is *not* the
PSA/BCPEA pattern where the whole target rejects datacenter IPs and residential
proxy fixes it: clutch.co stays fully open from Apify **with no proxy at all**.
What narrows is the accepted fingerprint set. A local recon matrix is therefore a
starting point, not the final ladder order — the ladder leads with the two
profiles that answer from both, and the client remembers the runtime winner.

### Refusals are transient, and that decides the retry policy

Three builds, in order, because the sequence is the evidence:

| Build | Retry policy | `directory` run |
|---|---|---|
| 0.0.1 | 3 attempts per profile, exponential backoff, one ladder pass | **SUCCEEDED** — but 10 requests / **8 challenges**, ~39 s lost on page 1 |
| 0.0.2 | challenge split from transient error: 2 attempts, then next profile | **FAILED** — 6 requests / **6 challenges**, 0 records |
| 0.0.3 | same ladder, walked **3 rounds** with 6→12 s between rounds | **SUCCEEDED** — **2 requests / 0 challenges** |

0.0.2 was the smarter policy and it failed: it gave up at attempt 6 where 0.0.1
got through on attempt 9. What saved 0.0.1 was not its intelligence, it was its
stubbornness. Two measured facts pull opposite ways — a wrong profile should be
abandoned fast (the gate is per IP), but a refusal is often just a moment — and
both are only satisfiable on **two separate axes**: few attempts per profile, but
the whole ladder repeated over several rounds. A `profile` run on 0.0.3 took
**7 challenges in 9 requests and still finished**.

Generalisable: **do not tighten a retry budget off one successful run.** Measure
which attempt number that run got through on first. If the answer is "the 9th of
9", cutting to 6 deletes the margin that saved it, not the waste.

## robots.txt

```
Disallow: /lp/            /claim-profile*
Disallow: /profile/*?*sort_by= project_cost= service_provided= industry= location= verified=
Disallow: /*?*geona_id= client_budget= industries= hourly_rate= related_services= sort_by= reviews=
```

Plain category paths and `?page=` are not disallowed. The Actor strips every
disallowed parameter from user-supplied URLs before requesting and logs the
names it dropped, and refuses `/lp/` and `/claim-profile` outright.

## Gotchas found (and what each one would have cost)

### 1. `?page=1` returns page **2**

| URL | `<title>` | Ranked IDs |
|---|---|---:|
| `/web-developers` | `Top Web Development Companies…` | 7 |
| `/web-developers?page=1` | `Page 2 - Top Web Development…` | 50 |
| `/web-developers?page=2` | `Page 2 - Top Web Development…` | 50 (identical set) |

Page 1 is the **bare URL**. A `for p in 1..N` loop skips page 1 entirely and
emits page 2 twice — and nothing about it looks broken, because both responses
are full 3 MB pages of real agencies. Same family as the BCPEA `perpage` trap
and the Himalayas filters that are accepted then ignored, but here the wrong
value returns *different valid data* rather than page 1.

### 2. Half of a page is advertising, and the markup says so — quietly

Page 1 of `/web-developers`, 86 rows:

| `data-type` | Rows | Behaviour |
|---|---:|---|
| `Sponsor` | 43 | Paid placement, page 1 only |
| `featured` | 6 (14 on later pages) | Paid, **identical on every page** |
| `Leaders Matrix` | 30 | **Identical on every page** |
| `Directory` | 7 (50 on later pages) | The actual ranking |

Only `Directory` rows are the ranked list. A scraper that treats `.provider-row`
as "the results" reports 86 results per page where there are 50, blends bought
slots into the ranking, and re-emits the same 44 pinned agencies on every single
page — 44 duplicates per page, forever. Measured: pinned IDs on page 3 ∩ page 4
= **41 of 41**; ranked IDs on page 3 ∩ page 4 = **0**.

This is the same "repeated rows" pattern as the 138 duplicate ESPN props and
Blibli's `_basic`, but here the duplication is *by design* and carries its own
label. The Actor emits `rowType`, `isPaidPlacement`, `isPinnedBlock` and
`isRankedResult`, deduplicates pinned rows by provider id, and sorts ranked rows
first so a capped run gets the ranking rather than the advertising.

### 3. The website URL is behind a redirect, and the real one is a query param

Every outbound link is `r.clutch.co/redirect?...&u=<url-encoded destination>`.
The destination sits in `u`, UTM tags attached. 50/50 ranked rows on a test page
yielded a real domain once unwrapped; a scraper that stores the `href` verbatim
stores 50 identical tracking URLs.

### 4. On a profile, JSON-LD's `review` array is **not** the page's review list

Same profile, three URLs, one minute apart:

| URL | HTML `article.profile-review` | JSON-LD `review[]` |
|---|---:|---:|
| `/profile/imaginovation` | 10 | 16 |
| `…?page=1` | 6 | 12 |
| `…?page=99` | **0** | 6 |

A page that renders no reviews at all still ships six of them in its structured
data. Reviews are therefore read from the HTML blocks, which carry a stable
`id="review-<id>"`. The `aggregateRating` in the same block *is* trustworthy and
is used. This is the JSON-LD-first rule meeting its exception: prefer the stable
layer, but verify it describes the page you fetched.

### 5. The featured review repeats on every review page

Page 2 of a profile returned 10 blocks of which **9** were new — the pinned
featured review comes back each time. Deduplicated by `reviewId`.

### 6. Class names lie about content; labels do not

The min-project-size cell is `min-project-size`, not `project-size` — the
obvious guess silently returned `None` for all 86 rows while every neighbouring
field parsed fine. The profile summary strip and the review data strip are read
by their **label text** (`data-tooltip-content`), not by position, because a
review without a project size drops the cell entirely and shifts everything
after it.

## Cost shape

| Mode | Requests | Yield |
|---|---|---|
| `directory` | 1 per page | ~50 ranked agencies + up to 44 pinned/paid, each with the full attribute set |
| `profile` | 1 per agency | Whole profile including service, focus and industry splits |
| `reviews` | 1 per ~10 reviews | Four sub-ratings, project size and length per review |
| `categories` | 2 | 10,000 directory URLs |

One request per 50 fully-attributed leads is the economics that makes the FLAT
$40 incumbents beatable: no per-profile visit is needed for any of the listing
attributes.

## Candidates checked and rejected in the same session

None — clutch.co answered on the first probe. The derivative targets named in
`actors_researcher_v2.md` (`goodfirms.co`, `designrush.com`, `sortlist.com`) were
**not** probed this round and remain open as the same-parser follow-up.
