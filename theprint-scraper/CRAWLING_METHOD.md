# Crawling Method — The Print (theprint.in)

**Last verified:** 2026-08-26

The Print (`theprint.in`) is an Indian digital-first news outlet founded by
Shekhar Gupta, covering politics, policy, defence, opinion, and world news.

## Robots.txt

```
User-agent: *

Allow: /

Disallow: *LINK*
Disallow: *newnewssitemap.xml?yyyy*
Disallow: *?p=*
Disallow: */search/*
Disallow: *?s*
Disallow: /category/theprint-valuead-initiative/
Disallow: /theprint-valuead-initiative/
Disallow: /category/brandstand/
Disallow: /category/adon/
Disallow: /category/brandstand/adon/
Disallow: /*?tdb-loop-page=
Disallow:  /page/*/?s=

User-agent: GPTBot
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: Google-Extended
Allow: /

Sitemap: https://theprint.in/googlenews.xml
Sitemap: https://theprint.in/sitemap_index.xml
```

`User-agent: *` is `Allow: /` with only search/tracking/ad-vertical paths
disallowed (none of which this actor touches — article URLs and
`/googlenews.xml` are both untouched by any `Disallow` line). Only `GPTBot`
and `CCBot` get an explicit blanket `Disallow: /`; `Google-Extended` is
explicitly `Allow: /`. **No `Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/
`Claude-SearchBot`/`anthropic-ai` user-agent group of any kind, and no
plain-English AI/LLM-training prohibition** (the file has no comments at
all to carry one). Independently re-fetched live during this build
(`curl_cffi` `chrome124`, `GET https://theprint.in/robots.txt` → HTTP 200,
body exactly as above) — confirmed crawlable.

## WAF / bot-check

`theprint.in` sits behind **CloudFront** in front of a custom origin-side
bot check (`X-Powered-By: luroConnect` observed on challenge responses).
**The deciding factor is CDN cache state, not TLS/JA3 fingerprint.**
`curl_cffi` `chrome124` (and every other profile tried during the original
recon — `chrome131`, `chrome99_android`, `safari17_0`, `edge101`) returns
full article HTML instantly whenever CloudFront already has the page cached
(`X-Cache: Hit from cloudfront`). Whenever CloudFront has **not** cached the
page (`X-Cache: Miss from cloudfront`), the origin returns a tiny (~1.8 KB)
`200 OK` "Just a moment…" JS interstitial — **note the HTTP status is 200,
not 403** — that sets a static, non-cryptographic cookie
(`__lc_ch=<epoch>:<hex>`) and reloads. Reproducing that cookie by hand does
**not** clear the check (confirmed: setting the exact cookie value and
re-requesting stays on the challenge) — this is not a solvable HTTP-only
challenge, it is purely a function of whether the CDN edge has already
cached the page.

**Practical impact — re-confirmed live during this build:**

- **Real, previously-published article URLs usually cache-HIT** and return
  full content on the first `curl_cffi chrome124` request with no special
  handling. Two 2-day-old articles sampled from a local (non-proxied) IP
  both returned `X-Cache: Hit from cloudfront` and full HTML instantly.
  **Confirmed this is genuinely per-edge, not a fixed per-article state:**
  the same 2-day-old Reuters-wire URL that consistently cache-HIT from the
  local IP consistently cache-MISSed (4/4 attempts, including with
  `apifyProxyCountry: "IN"`) when fetched through Apify's residential
  proxy pool during cloud smoke testing, while two other same-age articles
  fetched through the same proxy pool in the same runs succeeded fine (2/3
  hit rate in that small cloud sample — consistent with the ~60-90%
  organic-traffic-dependent range from the original recon, just now also
  confirmed specifically over the production proxy path, which does not
  necessarily share a CloudFront edge/POP with a local dev machine's ISP).
  **Practical takeaway: article-mode success rate depends on real traffic
  to that specific article, not on the actor's own logic** — retrying a
  failed URL a few minutes to hours later (allowing organic/CDN-refresh
  traffic to populate that edge's cache) is the only lever, there is no
  code fix for this.
- **Brand-new articles (published within the last few minutes) are
  frequently a cache MISS.** Confirmed directly: the single freshest item on
  the Google News sitemap at build time (published seconds earlier) hit the
  challenge on every one of 5 retries and exhausted the client's retry
  budget. An article from ~2 minutes earlier in the same sitemap batch
  succeeded fine. This is a timing race, not a permanent block — the same
  URL becomes fetchable once an organic visitor (or the CDN's own crawl)
  populates the cache, typically within minutes.
- **A fabricated/never-existed article slug ALSO always cache-MISSes**
  (confirmed with an invented slug + invented numeric ID) and hits the same
  "Just a moment" interstitial on every retry, **not a real HTTP 404**. This
  is a genuine limitation, not a bug: there is no HTTP-only way to
  distinguish "this article doesn't exist" from "this real article hasn't
  been cached yet" on this site, because the bot-check layer intercepts the
  request before the origin's WordPress application layer ever gets to
  decide 200-vs-404. `client.get()` exhausts retries and raises
  `RuntimeError` in both cases; `main.py` reports this as
  `_error: "blocked_or_transient"` rather than `"not_found"`. In practice
  this only affects genuinely-invalid/deleted URLs — real article inputs
  (the actor's normal use case) are unaffected.
- `latest` mode is **entirely unaffected** by any of the above — it reads
  `/googlenews.xml` directly and never opens individual article pages.

`chrome124` is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even though every profile currently works
identically here (the gate is cache state, not fingerprint).

### Follow-up investigation (2026-08-26): exhaustive HTTP-layer ladder — negative result

A dedicated investigation re-tested whether **any** HTTP-layer lever moves
`article`-mode reliability, using a fixed 8-URL test set spanning
seconds-old to years-old articles (2 brand-new, 2 few-hours-old, 2
~1-2-days-old, 2 weeks/years-old archive pieces — the archive pieces
included specifically because near-zero ongoing organic traffic means
CloudFront's cached copy has likely expired, making them "cold" in the
cache sense regardless of publish age). Every combination below was run
against the full 8-URL set and graded per-URL, not aggregated:

- **Full `curl_cffi` impersonate ladder** (20 profiles: `chrome99` through
  `chrome133a`, both Android variants, `edge99`/`edge101`, 4 Safari
  desktop/iOS profiles, `firefox133`/`firefox135`) — **byte-for-byte
  identical outcome on every one of the 20 profiles**: the same 7/8 URLs
  blocked (`Miss from cloudfront`), the same 1/8 URL a clean hit (`Hit from
  cloudfront`).
- **`primp`** (rquest/BoringSSL Rust stack, a different TLS implementation
  from curl_cffi's) across 8 impersonate profiles (`chrome_124` through
  `chrome_146`, `firefox_133`/`135`, `safari_18`, `safari_15_3`,
  `edge_131`) — **identical outcome again**, same 7/8 blocked, same 1/8 hit.
- **`scrapling`'s HTTP-only `Fetcher`** (curl_cffi-backed, not the
  Camoufox browser fetcher) with `stealthy_headers=True` (auto-generates a
  full realistic header set — `Accept`, `Accept-Language`, `Sec-Fetch-*`,
  `Referer: https://www.google.com/` — matched to the impersonated browser,
  rather than the portfolio's minimal 2-header default) on `safari2601` and
  `chrome124`, plus an `http3=True` variant — **identical outcome once
  more**.
- **Homepage warmup vs. no warmup**: for each of the 6 blocked URLs, a
  fresh session that went straight to the article was compared against a
  fresh session that `GET /` first (200 OK, confirmed) and then requested
  the same article — **no difference**, both blocked every time.
- **Same-session repeat requests to the same cold URL** (up to 3 attempts
  per URL with 2s/5s spacing, plus a longer poll — 6 attempts at 15s
  intervals, ~90s total — against the single freshest sitemap entry) —
  **never flipped to a hit**; `X-Cache` stayed `Miss from cloudfront` on
  every attempt. This confirms the earlier finding that the challenge
  response does not itself warm the edge cache — only real organic (or
  CDN-crawl) traffic does, and that takes longer than a request-level retry
  budget can wait.

**Total: 34 distinct HTTP-layer configurations (library × profile × header
realism × warmup × retry timing) tested against the same 8-URL set, zero
variance in outcome.** This is a materially stronger negative result than
the original recon (which tried a handful of `curl_cffi` profiles) — it
rules out TLS/JA3 fingerprint, the underlying TLS stack/implementation
(BoringSSL-via-curl_cffi vs. BoringSSL-via-rquest/primp), header realism,
HTTP/3 vs HTTP/2, session warmup, and short-window retry as levers,
individually or in combination. **No code changes were made** — `client.py`
keeps `curl_cffi` `chrome124` with the existing 5-retry exponential backoff,
since nothing tested outperforms it. The only working lever remains time
(waiting for organic/CDN traffic to populate that edge's cache), which is
already documented above and is not something any HTTP client library can
shortcut.

Caveat: this round of testing ran from a single local/non-proxied IP in one
session, so it cannot speak to per-POP cache variance across Apify's
residential proxy pool (the original recon's 4/4-miss-through-proxy vs.
2/3-hit-through-proxy result on different articles) — only to whether
switching HTTP tooling changes the outcome for a **fixed** IP/edge at a
**fixed** point in time, which it does not.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://theprint.in/<section>/<slug>/<numeric-id>/`

The page (WordPress + tagDiv "Newspaper" theme + Yoast SEO) emits **one**
`<script type="application/ld+json">` block: a Yoast-style `@graph` array of
cross-referenced nodes — `Article`, `WebPage`, `ImageObject`,
`BreadcrumbList`, `WebSite`, `Organization`, `Person`.

The `Article` node carries `headline`, `datePublished`, `dateModified`,
`wordCount`, `commentCount`, `keywords`, `articleSection`, `thumbnailUrl` —
but **no `articleBody`**. `Article.author` is a list of `{"@id": ...}` refs
that resolve against the graph to inline `Person` nodes (name + avatar +
author archive URL); `Article.publisher` is a bare
`{"@id": "...#organization"}` ref that resolves to the graph's own
`Organization` node (`name: "ThePrint"`), with a `<meta property="og:site_name">`
fallback if that node is ever absent. No double-HTML-escaping quirk
observed in the graph's text values on any sample checked;
`html.unescape()` is applied defensively to every text value pulled from
the graph anyway.

Full body text comes from HTML: `div.td-post-content` (the tagDiv Newspaper
theme's article-body block). Unlike a simple single-level container, this
theme nests the actual paragraphs two levels down inside an unclassed
wrapper `<div>` (`div.tdb-block-inner > div` with no class), interleaved
with sibling `div.code-block` ad-slot placeholders that carry no `<p>` tags
at all — so a full (recursive) `find_all("p")` on `div.td-post-content`
picks up every real paragraph and no ad copy, with no extra scoping needed
(confirmed: zero `<p>` tags carry any `class` attribute, i.e. no
image-caption `<p>` tags leak into the body text either).

`description` comes from `<meta name="description">`, falling back to the
graph's `WebPage.description`. **Both were empty/absent on 2 of the 4
articles sampled during this build** (both wire-sourced pieces) — this is a
genuine per-article gap on ThePrint's side, not an extraction bug; the
field is emitted as `null` rather than a fabricated value.

**Invisible watermark characters on Reuters wire content.** One Reuters
wire article's body (`.../zelenskiy-says-russia-is-not-ready-for-ceasefire-on-grain-ships/...`)
was found to contain scattered zero-width Unicode characters interleaved
into ordinary words — `U+200B` ZERO WIDTH SPACE ×2, `U+200C` ZERO WIDTH
NON-JOINER ×1, `U+2060` WORD JOINER ×1 (e.g. `"major​players"`,
`"it​saw"`) — invisible when rendered, present in the raw text.
Cross-checked against a PTI-wire article and two ThePrint staff-written
articles: **none of the three showed any zero-width characters** — this
appears specific to (some) Reuters-sourced wire content, plausibly a
Reuters-side anti-leak/plagiarism-tracing watermark baked into the wire
feed rather than anything ThePrint's CMS adds. Per this portfolio's raw
passthrough convention, these characters are **left in `articleBody`
as-is** — stripping them would mean silently altering upstream text, and
they don't break JSON encoding (valid UTF-8 throughout). Downstream
consumers doing exact-string matching or display should be aware plain-text
search on affected passages may need Unicode normalization.

A page that 200-OKs but is not an article at all would emit a graph with no
`Article` node — detected explicitly and reported as `_error: "not_article"`
rather than a schema-drift crash (not directly observed on a real static
page during recon, but the same defensive check used by every other
Yoast-graph actor in this portfolio is kept here).

### 2. Latest headlines — `S2-sitemap`

`GET https://theprint.in/googlenews.xml`

The Google News sitemap (referenced from `robots.txt`), confirmed live
during this build: 1000 `<url>` entries spanning roughly the last 2 days of
publishing at the sampled volume. Each `<url>` carries `loc`,
`news:news/news:publication_date` (real per-article ISO 8601 timestamp,
matching wall-clock time to the minute), `news:news/news:title`,
`news:news/news:keywords` (e.g. `"reuters wire"`, `"PTI wire"` on
wire-sourced pieces, `None`/absent on staff-written pieces), and
`image:loc`. Confirmed already newest-first in file order; sorted
descending by `publication_date` defensively anyway in case that ordering
isn't guaranteed on every fetch.

The site-wide `/feed` RSS and `/wp-json/wp/v2/posts` REST API both return
the SAME edge "Just a moment" challenge body as an uncached article page on
every attempt (a path-level block, not just a cache-state artifact), so the
Google News sitemap is used instead — it was never observed gated the same
way in any sample taken. `sitemap_index.xml` (the regular Yoast sitemap)
also works but only lists per-day archive pages, not individual articles
directly, so `googlenews.xml` remains the more direct source.

## Paywall behavior

**None observed.** "premium"/"Premium" string hits on sampled article pages
all trace to the Yoast SEO Premium plugin comment and an unrelated
video-CTA widget class name (`tvc_go_premium`), not article-body gating. 4
articles sampled in depth across categories (World/Reuters-wire, India/PTI-
wire, Pakistan/staff-written, plus a 2-day-old archive check) all returned
full, naturally-ending body text — no "subscribe to continue reading"
marker, articleBody length consistent with the ld+json `wordCount` field
where present. ThePrint is a free, open-access site.

## Known limits

- **A genuinely non-existent/deleted article slug cannot be distinguished
  from a real article that CloudFront simply hasn't cached yet** — both
  present as the same 200-OK "Just a moment" interstitial, exhausting
  retries into a `blocked_or_transient` error rather than a clean
  `not_found`. See WAF section above.
- **Brand-new articles (published in roughly the last few minutes) may
  transiently fail** in `article` mode until CloudFront's edge caches them
  — retrying the same URL a few minutes later resolves it. `latest` mode is
  unaffected (reads the sitemap directly, never opens article pages).
- `description` is `null` on some wire-sourced articles where ThePrint
  supplies no meta description and the JSON-LD `WebPage` node has none
  either — a genuine upstream gap, not an extraction bug.
- Only 4 articles sampled in depth (World/Reuters, India/PTI, Pakistan
  desk/staff-written, plus one deliberately-invented-slug probe). A
  structurally different template (e.g. a live-blog, video feature, opinion
  page, or podcast page) was not sampled.

## Diff cadence

Quarterly smoke test recommended.
