# Crawling Method — The Standard (Kenya)

**Last verified:** 2026-08-26

## robots.txt

Fetched fresh (not reused from a prior check) as the mandatory first step, per this
project's standing "Babak 14" postmortem (a past screening bug only checked the
LAST `User-agent` line before a shared `Disallow:` block, causing a false-clean
verdict on a site that actually blocked AI crawlers under one of several groups).
`standardmedia.co.ke/robots.txt` has **only one `User-agent` group**, so there is
no merged/shared-block ambiguity to worry about:

```
User-agent: *
Disallow:

sitemap: https://www.standardmedia.co.ke/sitemaps/googlenews.php
sitemap: https://www.standardmedia.co.ke/mainsitemap
sitemap: https://www.standardmedia.co.ke/business/businesssitemap
sitemap: https://www.standardmedia.co.ke/sports/googlenews
sitemap: https://www.standardmedia.co.ke/farmkenya/sitemap
sitemap: https://www.standardmedia.co.ke/entertainment/sitemap
sitemap: https://www.standardmedia.co.ke/health/healthsitemap
sitemap: https://www.standardmedia.co.ke/evewoman/evewomansitemap
```

`Disallow:` is empty — every path is allowed. No `Claude`, `ClaudeBot`,
`Claude-Web`, `Claude-User`, `Claude-SearchBot`, or `anthropic-ai` token appears
anywhere in the file. File is 517 bytes, HTTP 200, `Last-Modified: Mon, 09 Sep
2024`. Clean.

## WAF

`standardmedia.co.ke` shows **no active challenge**. `curl_cffi` `chrome124` gets
a clean 200 on the homepage, every sampled article page (10+ articles across 6+
sections), and the Google News sitemap — on the first try, no profile-ladder
escalation needed. The site is Cloudflare-fronted (`server: cloudflare`,
`cf-ray`, `cf-cache-status`), but the only cookies ever set are a Laravel
`XSRF-TOKEN` / `thestandardmediagroup_session` pair (ordinary framework session
plumbing — the CMS backing this site is Laravel-based) — no `cf_clearance`,
no `__cf_chl_*`, no JS challenge body, no `Just a moment...` interstitial.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide default.

## Data sources

### 1. Article pages, main templates — `S1-jsonld`

`GET https://www.standardmedia.co.ke/<section>/article/<id>/<slug>`

Most sections (`national`, `opinion`, `crime-and-justice`, `politics`,
`education`, `explainers`, `branding-voice` [sponsored content], `asia`,
`xn-iraki` [columnist], `health`, and presumably others not individually
sampled) emit a top-level `NewsArticle` ld+json node (not wrapped in `@graph`)
that carries **`articleBody` with the full article text inline** — no HTML
scraping needed. Also present: `headline`, `articleSection` (list, e.g.
`["Crime and Justice"]`), `image` (list of URL strings), `datePublished`/
`dateModified` (ISO 8601 with `+03:00` offset), `author` (list of `Person`
objects with `name`/`url`), `isAccessibleForFree` (bool), and a `hasPart` node
naming a `.paywall` CSS selector (Piano-style paywall metadata — see Paywall
behavior below).

**Key quirk #1 — double HTML-entity escaping.** `articleBody` is emitted
double-escaped on the wire: confirmed on raw response bytes, a literal
`&nbsp;` in the source content is served as literal `&amp;nbsp;` inside the
JSON string value (i.e. the CMS ran the content through an HTML-escaper
*after* it already contained HTML entities, escaping the leading `&` a second
time). A single `html.unescape()` only recovers `&nbsp;`; two passes are
needed to recover the real `\xa0` character. `extractor.py`'s
`_clean_body_text()` always applies `html.unescape()` twice — this is safe/
idempotent for ordinary text (e.g. a literal `"H&M"` is unaffected by either
pass, since there's no entity pattern to match).

**Key quirk #2 — unescaped control characters.** The same ld+json blocks
contain raw, unescaped `\r\n` bytes inside JSON string values (also confirmed
on the wire, not a library decoding artifact). Standard-library `json.loads`
rejects this by default with `Invalid control character at: ...`; the
extractor parses with `json.loads(raw, strict=False)` to tolerate it.

**Key quirk #3 — leading photo caption/credit line.** `articleBody` on this
template starts with the lead photo's caption and credit as its own line
(e.g. `"Kitui County Chief Officer Gladys Mami Kivoto... [Joh Muia,
Standard]"`) before the real narrative begins. This is kept as-is (raw
passthrough) rather than stripped — unlike ghanaweb's trailing promo-noise
truncation, there was no reliable structural marker to distinguish "caption
line" from "short opening sentence" without risking false positives on
genuinely short lead paragraphs.

### 2. Article pages, evewoman template — `S2-html`

The `evewoman` (lifestyle) section uses a **different article template**: its
`NewsArticle` ld+json node has **no `articleBody` key at all** (only
`headline`/`description`/`image`/`author`/dates/`articleSection`/`publisher`),
and uses `@context: "http://schema.org"` (note: `http`, not `https`, unlike
the main template's `https://schema.org`). Confirmed on multiple evewoman
URLs — this is a genuine template split, not an unsampled edge case; every
other section sampled (10+ articles via the Google News sitemap, spanning
`national`/`opinion`/`crime-and-justice`/etc.) had a populated `articleBody`
in ld+json and used S1 instead.

Full text for this template comes from `div.story-body` in the HTML (aliased
by a `div.content-body` wrapper one level up — either selector reaches the
same text; `div.story-body` is tried first). Proper `<p class="paragraph-
style">` tags are used (unlike ghanaweb's `<br>`-only legacy template), but
interspersed with empty `<p></p>` spacer tags and inline ad blocks
(`<div class="ad" id="div-gpt-ad-...">` containing a `<script>` GPT call)
that must be stripped before joining paragraphs — `_extract_html_body()`
`.decompose()`s `script`/`style`/`iframe`/`ins`/`div.ad`/`div[id^='div-gpt-
ad']` elements first, then joins the text of all remaining non-empty `<p>`
tags with `\n\n`.

The evewoman article's canonical URL (`mainEntityOfPage`/`@id`) also differs
from the crawled URL — it canonicalizes to insert an extra subsection segment
(e.g. input `.../evewoman/article/2001555613/...` canonicalizes to
`.../evewoman/wellness/article/2001555613/...`). Both URL forms serve the
same content; `canonicalUrl` in the output record carries the ld+json value
for reference.

### 3. Latest headlines — `S2-sitemap`

`GET https://www.standardmedia.co.ke/sitemaps/googlenews.php`

Google News sitemap, advertised via `sitemap:` lines in `robots.txt`.
Confirmed same-day freshness (all sampled items dated the day of the fetch,
2026-08-26) across a broad section mix — 88 URLs observed in one fetch,
spanning `national`, `opinion`, `crime-and-justice`, and more. Standard
`news:` sitemap shape: `loc`, `news:title`, `news:publication_date` (date
only, no time component, unlike ghanaweb's full ISO-8601-with-timezone),
`news:language`, plus `image:loc`/`image:caption` and a top-level `lastmod`.
`section` is derived from the first URL path segment (e.g. `national`,
`opinion`) since the feed carries no explicit category element of its own.

**Other sitemaps in robots.txt were probed and rejected:**
- `/business/businesssitemap` — returns the **exact same generic feed** as
  `/sitemaps/googlenews.php` (byte-for-byte-similar content, same mixed
  sections), not business-specific content. Misconfigured on their end;
  redundant with the primary feed.
- `/sports/googlenews` — returns article URLs **missing the `/article/`
  path segment** (e.g. `/national/2001556152/inside-...` instead of
  `/national/article/2001556152/inside-...`). Confirmed broken: fetching
  that malformed shape returns a real HTTP 404. Not usable.
- `/entertainment/sitemap` — returns an empty `<urlset>` (0 `<url>`
  elements, 139-byte response).
- `/health/healthsitemap` — DOES work and carries genuine health-specific
  URLs (`/health/health-science/article/...`), but wasn't adopted as the
  primary feed since `/sitemaps/googlenews.php` already covers a broad
  cross-section mix and matches the single-feed pattern used elsewhere in
  this portfolio (see ghanaweb-scraper). Available as a future per-section
  enhancement if needed.
- `/mainsitemap`, `/farmkenya/sitemap`, `/evewoman/evewomansitemap` — not
  probed in depth; `/farmkenya/sitemap` returned only 10 category-landing
  URLs (not article URLs) in a spot check.

No RSS feed was probed for since the Google News sitemap already satisfies
the `latest`-mode requirement with same-day freshness.

## Paywall behavior

**No hard paywall for HTTP-only scraping.** `isAccessibleForFree` varies
`true`/`false` across sampled articles (both values observed across
`national`, `opinion`, `crime-and-justice` sections), and a `hasPart` node
names a `.paywall` CSS selector — this is Piano-style paywall *metadata*
intended to drive a client-side visual paywall overlay in the browser. But
**`articleBody` in the ld+json is NOT truncated for `isAccessibleForFree:
false` articles** — full-length body text (observed 5,000–8,400+ characters)
was present regardless of the flag's value across 8 sampled articles pulled
from the Google News sitemap. Verdict: soft/cosmetic paywall only, no
metering enforced against a non-browser HTTP client.

## Not-found behavior

Two distinct shapes observed, both mapped to `_error: "not_found"`:

- **Malformed path** (missing the `/article/` segment entirely, e.g. the
  broken `sports/googlenews` sitemap URLs) → real **HTTP 404**.
- **Syntactically valid path with an out-of-range numeric ID** (e.g.
  `/national/article/2001999999/...`) → **HTTP 302 redirect to the
  homepage** (`https://www.standardmedia.co.ke/`), which then returns a
  normal 200. `curl_cffi` follows redirects by default, so by the time
  `main.py` sees the response, `status_code` is 200 — the soft-404 is
  detected by comparing the final `response.url` (post-redirect) against
  `BASE_URL`. This is functionally identical to ghanaweb's 410-vs-404
  split in spirit (two different not-found shapes on one site) but
  manifests completely differently on the wire (redirect vs. status code),
  so both cases are checked explicitly in `main.py`/`test_local.py`.

## Known limits

- `articleBody`'s leading photo-caption/credit line (S1-jsonld template) is
  kept as-is rather than stripped — see Key quirk #3 above. Downstream
  consumers that want clean narrative-only text should split on the first
  `\r\n\r\n` and treat everything before it as caption metadata IF that
  first line looks caption-shaped (heuristic left to the consumer since no
  reliable structural marker was found).
- Only the `evewoman` section was confirmed to need the `S2-html` fallback.
  A structurally different template (photo gallery, video feature, live
  blog, or the `farmkenya`/`branding-voice` sections beyond the one
  `branding-voice` sample checked) was not exhaustively sampled and might
  need a third strategy if it lacks both `articleBody` in ld+json AND a
  `div.story-body`/`div.content-body` container — this would currently
  raise `UnexpectedShape` rather than silently degrade, per this
  portfolio's fail-loud convention.
- `description` is `null` on S1-jsonld records for at least one sampled
  section (`crime-and-justice`) — the ld+json node simply omits the key on
  some articles. Not a bug, just an inconsistently-populated upstream field.
- `/business/businesssitemap` and `/sports/googlenews` being broken/
  redundant (see above) means this actor has no verified business- or
  sports-specific latest-mode feed; the general `/sitemaps/googlenews.php`
  feed does include business/sports articles when they're recent enough to
  appear in Google News' rolling window, just not filterable by section
  without fetching `/health/healthsitemap`-style dedicated feeds per
  section (only health's was confirmed working).

## Diff cadence

Quarterly smoke test recommended.
