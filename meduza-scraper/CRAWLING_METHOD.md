# Crawling Method — Meduza

**Last verified:** 2026-08-26

## robots.txt

Re-fetched fresh (not reused from the earlier research-doc check) and read
every `User-agent:` group's `Disallow:` lines individually -- not just the
last one before a shared `Disallow` block (see `.ai/CLAUDE.md` re: the
"Babak 14" false-clean bug where a screening script only checked the last
`User-agent` line).

```
User-agent: Twitterbot

User-agent: *
Disallow: /insite/
Disallow: /embed/
```

75 bytes total (`Content-Length: 75`, confirmed via `curl -sI`). Two groups:
`Twitterbot` (no rules at all) and `*` (disallows only `/insite/` and
`/embed/`). **No mention of `Claude`, `ClaudeBot`, `Claude-Web`,
`Claude-User`, `Claude-SearchBot`, or `anthropic-ai` anywhere in the file,
in any group.** Article paths (`/news/`, `/feature/`, `/short/`, `/video/`,
and their `/en/`-prefixed equivalents) are not disallowed for any UA.
Clean -- not a stop condition.

## WAF

`meduza.io` sits behind Cloudflare (`Server: cloudflare`, `cf-ray` header,
`__cf_bm`/`_cfuvid` cookies on every response) but **never issues an active
JS challenge**. `curl_cffi chrome124` gets a clean `200` on:
- both homepages (`meduza.io/`, `meduza.io/en`)
- 4 article pages across `/news/`, `/feature/`, `/short/`, `/video/` and
  both editions
- both RSS feeds (`/rss/all`, `/rss/en/all`)
- a synthetic not-found URL (real `404`, not a soft-404)

The full profile ladder (`chrome124`, `chrome116`, `chrome99_android`,
`safari17_0`, `edge101`) was run against both homepages before settling on
one profile -- all five returned identical `200`s with identical byte
lengths, confirming there is no JA3-specific gate to work around.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

### A false-positive worth documenting

Meduza injects Cloudflare's **passive** bot-management beacon into the
`<head>` of every page it serves -- `window.__CF$cv$params` and a
`<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js">` reference
-- on ordinary `200`s *and* real `404`s alike, not just on active
challenges. The portfolio's default `BLOCK_MARKERS` list (copied from
rt-scraper/tass-scraper) includes the literal substring `"challenge-platform"`
as a block signal. On Meduza that makes `is_blocked()` true for **every**
response, including a confirmed-real synthetic-404 test, causing an
infinite retry-then-`RuntimeError` loop with no actual block occurring.
Fixed in `src/client.py` by dropping that one marker for this actor (kept
`"Just a moment"`, `"cf-mitigated"`, and the 403/429/503 status check,
which still catch a real challenge). Worth checking for on any other
Cloudflare-fronted target that reuses this marker list.

## Data sources

### 1. Article pages — `S1-html`

`GET https://meduza.io/<section>/<yyyy>/<mm>/<dd>/<slug>` (Russian edition)
or `GET https://meduza.io/en/<section>/<yyyy>/<mm>/<dd>/<slug>` (English
edition) -- identical page shape on both.

The page emits exactly **one** `<script type="application/ld+json">` block.
Its `@type` varies by section:
- `/news/` and `/short/` → `NewsArticle`
- `/feature/` → `Article`
- `/video/` → `VideoObject`

That block carries `headline`, `description`, `image` (a single
`ImageObject`, not an array -- passed through as-is), `author`/`publisher`
(both `NewsMediaOrganization`, `name: "Meduza"` in every sample checked --
wire-style organizational attribution, no distinct individual journalist
byline observed; the extractor still reads whatever `name` is present),
`datePublished`, `dateModified`, `inLanguage` (`ru-RU` or `en-US`) -- but
**no `articleBody`**.

Full text comes from HTML `div.GeneralMaterial-module-article > p`. This
container class is **not** webpack-hashed (used verbatim across every
sample, both editions); the `<p>` tags inside it do carry a hashed class
(e.g. `SimpleBlock-module_p__7aRnT`) but that hash is never matched on --
only the tag name is used, exactly like rt-scraper/tass-scraper's pattern.

**`/short/` and `/video/` pages do not populate this container with `<p>`
tags.** `/short/` renders its body text into the `alt` attribute of a
lazy-loaded placeholder `<img>` instead (an HTML-encoded string, including
embedded `<a>` tags, sitting in an `alt=""` attribute -- not a supported
extraction target in this version). `/video/` pages have no textual body at
all. Both degrade to a metadata-only record (`articleBody: null`,
`_warning: "no_body_extracted_non_article_layout"`) rather than raising --
this is their normal shape, not schema drift. A `NewsArticle` or `Article`
page (the two types that *are* expected to always carry a body) with an
empty extracted body **does** raise `UnexpectedShape` and fail the run
loudly, per this portfolio's error-handling convention.

#### The AI-translation disclosure quirk (English edition only)

Every EN-edition article sampled during recon that was translated from a
Russian original appends a boilerplate disclosure as three ordinary `<p>`
tags inside the same `GeneralMaterial-module-article` container:

> "At Meduza, we are committed to transparency about our use of artificial
> intelligence in the newsroom. The story you're reading was written by
> one of our living, breathing journalists and translated from Russian
> using an AI model configured to follow our strict editorial standards...
> If you find any errors in this translation, please contact us at
> reports@meduza.io... To read Meduza's exclusive content in English,
> please subscribe to our newsletter."

Since it lives in the exact same `<p>` tags as real content (no
distinguishing wrapper class -- confirmed via BeautifulSoup extraction,
not just a raw-HTML string search, which false-negatived because of how
the page's inline JS re-escapes quotes), it must be filtered by substring
match. `src/constants.py` `AI_DISCLOSURE_MARKERS` holds three lowercase
substrings used to drop matching paragraphs before joining `articleBody`.
Confirmed present on every EN sample checked, confirmed absent on every RU
sample checked. This is disclosed as a normal editorial practice by
Meduza, not a defect -- but it is boilerplate, not article content, so it
does not belong in `articleBody`.

### 2. Latest headlines — `S2-rss`

- `GET https://meduza.io/rss/all` -- Russian edition, `<language>ru</language>`
- `GET https://meduza.io/rss/en/all` -- English edition, `<language>en</language>`
  (there is also `/rss/en/news`, a narrower "news only" feed excluding
  `/feature/` pieces -- not used here since `/rss/en/all` is a superset)

Standard RSS 2.0: `title`, `link`, `guid` (identical to `link`), `pubDate`,
and `description` -- unlike rt-scraper's feed, Meduza's `<description>` is
**only a short 1-3 sentence teaser**, not the full article. There is no
`<content:encoded>` full-body element on this feed (confirmed by
inspecting the raw item XML for both editions). `latest` mode returns
teaser + metadata only; call `article` mode against `link` for full text.

`<link>` in the RSS feed is already the clean canonical article URL, no
tracking query params to strip (unlike rt-scraper's `?utm_source=rss`).

An input field `language` (`"en"` default, `"ru"` alternative) switches
between the two feeds in `latest` mode.

## Paywall behavior

None found. Body length was consistent across all samples (short news
briefs ~150-500 chars, features 2,000-5,000+ chars) with no truncation
pattern, no `isAccessibleForFree` field in ld+json, and no
subscribe/paywall gating on content access -- the only "subscribe" strings
found in the page are (a) the anonymous visitor's daily-digest-email
subscription state (`"subscribed": false` in the client-side Redux-style
state blob, unrelated to article access) and (b) inline article text
referencing a *third-party* outlet's paywall (The Bell), not Meduza's own.
Meduza is donation-funded, consistent with fully open access.

## Russian vs. English edition decision

**Both are supported by the same extractor** -- `meduza.io/...` and
`meduza.io/en/...` share an identical ld+json shape and an identical
`div.GeneralMaterial-module-article` HTML container, so no separate code
path was needed. The English edition is used as the **default/prefill**
(input schema `url` example, `latest` mode's default `language: "en"`) to
match this portfolio's existing convention for Russian outlets (rt-scraper
and tass-scraper both default to their English editions for consistency
with downstream English-language pipelines).

Trade-off, made explicit: the Russian edition is Meduza's original,
full-volume output (every story, written directly in Russian). The English
edition is a **curated, partly AI-translated subset** (see the disclosure
quirk above) that lags the Russian original and does not cover 100% of
Russian-edition stories. Anyone who wants full-volume, unmediated original
coverage should point `article`/`latest` mode at the Russian URLs/feed
(`language: "ru"`); anyone who wants English-readable output without a
separate translation step should use the default English edition.

## Known limits

- `/short/` pages: body text lives in an `<img alt="...">` attribute, not
  extracted in this version -- returns metadata only with `_warning`.
- `/video/` pages: no textual body exists on the page at all -- returns
  metadata only with `_warning`.
- `author`/`publisher` were `"Meduza"` (organization) in every sample
  seen; a byline-attributed piece with an individual reporter's name in
  ld+json was not sampled and might have a different shape -- the
  extractor still handles that case since it reads whatever `name` is
  present.
- 404s are real HTTP 404s (verified with a synthetic out-of-range article
  slug, on both `meduza.io/news/...` and `meduza.io/en/news/...`) -- no
  soft-404 behavior observed.
- `/rss/en/all` and `/rss/all` are teaser-only; full text requires a
  follow-up `article`-mode call against the item's `link`.
- Samples: 2 RU articles (`/news/`, `/feature/`), 2 EN articles (`/news/`,
  `/feature/`), 1 RU `/short/`, 1 RU `/video/`, plus both RSS feeds and a
  synthetic 404 on both editions. A live-blog/podcast-page layout was not
  sampled.

## Diff cadence

Quarterly smoke test recommended.
