# Crawling Method — The Star (Kenya)

**Last verified:** 2026-08-26

## robots.txt

Fetched fresh (not reused from the orchestrator's fast screen) as the
mandatory first step, per this project's standing "Babak 14" postmortem (a
past screening bug only checked the LAST `User-agent` line before a shared
`Disallow:` block, causing a false-clean verdict on a site that actually
blocked AI crawlers under one of several groups). `the-star.co.ke/robots.txt`
is the entire file, verbatim:

```
User-Agent: *
Allow: /
```

A **single** `User-agent: *` group, `Allow: /` (fully permissive), no
`Disallow` line at all. No `Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`,
`Claude-SearchBot`, or `anthropic-ai` token appears anywhere in the file.
HTTP 200. Clean — no merged/shared-block ambiguity, no partial-agent trap.

## WAF

`the-star.co.ke` shows **no active challenge**. `curl_cffi` `chrome124` gets
a clean 200 on the homepage, every sampled article page (12+ articles across
7 sections: news, business, sports, opinion, sasa, counties, in-pictures —
including both premium-gated and free templates), the sitemap index, and
individual article sitemaps — on the first try, no profile-ladder escalation
needed. The site is Cloudflare-fronted (`server: cloudflare`, `cf-ray`), but
purely as a CDN — no `cf_clearance`, no `__cf_chl_*`, no JS challenge body,
no "Just a moment..." interstitial on any request made during recon or
testing.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-flight+html`

`GET https://www.the-star.co.ke/<section>[/<subsection>]/YYYY-MM-DD-<slug>`

This site is a Next.js **App Router** build (React Server Components), not
the classic Pages Router this portfolio's `__NEXT_DATA__` anchor targets.
Confirmed absent on every sampled page: no `<script type="application/ld+json">`
tag anywhere, and no `<script id="__NEXT_DATA__">` blob either — both of
this portfolio's usual first-choice anchors are dead ends here.

**Key quirk — JSON-LD lives inside an RSC flight payload.** The `NewsArticle`
structured-data object is embedded inside one of several
`<script>self.__next_f.push([1,"..."])</script>` tags scattered through the
page. The second array element is a JSON-encoded **string** — i.e. the
flight protocol text is escaped one level deeper than ordinary inline JSON
(quotes inside it appear as `\"` in the raw HTML bytes). `extractor.py`
handles this in two balanced-bracket passes (see
`skills/balanced-brace-json.md`):
1. `_iter_next_f_strings()` finds each `push([...])` call, balanced-bracket-
   extracts the full `[1, "..."]` array text, and `json.loads()`s it — this
   single step un-escapes the inner string via the standard JSON decoder
   (no manual `.replace()`/unescape gymnastics needed).
2. `_find_json_ld()` then balanced-brace-extracts the `"jsonLd":{...}` object
   out of the now-plain-JSON flight text and `json.loads()`s it directly.

The resulting node carries `@type: "NewsArticle"`, `headline`,
`datePublished` (ISO 8601 with `+0300` offset, no colon in the offset),
`author` (a single `Person` object, `{"@type":"Person","name":"ELIUD KIBII"}`
— not a list like standardmedia-scraper's template), `image` (a list of
`ImageObject` entries), `publisher`, `mainEntityOfPage`, and `description`
(observed **always `null`** across every sample — this CMS doesn't appear to
populate it). Premium-gated articles additionally carry
`isAccessibleForFree: false` and a `hasPart: {"cssSelector": ".premium-content", ...}`
node; free articles omit both keys entirely rather than setting
`isAccessibleForFree: true`.

**`articleBody` does not exist in the JSON-LD at all** — confirmed on every
sample, both free and premium templates. Body text must come from the
rendered HTML instead.

### 2. Article body — HTML fallback (part of `S1-flight+html`)

Full text comes from `<div class="story-content">` element(s) in the SSR
HTML. **Two distinct shapes, both handled by taking the LAST such div:**

- **Free articles:** exactly one `div.story-content`, holding the lead image
  and the full body together.
- **Premium/paywalled articles:** exactly **two** — an outer one (siblings of
  a `div.premium-gate`) holding only the lead image (shown to everyone), and
  a second one nested inside `<div class="premium-gate"><div
  class="premium-gate__content" aria-hidden="true"><div class="premium-content">`
  holding the real paragraphs. Despite `aria-hidden="true"` and the
  `isAccessibleForFree: false` flag, **the full article text is still
  server-rendered into the HTML** — this is a CSS-driven visual gate only
  (see Paywall behavior below), not a content-stripping paywall.

`_extract_html_body()` selects `soup.select("div.story-content")[-1]` — the
only one when there's one, the full-text one when there are two — then joins
the text of every `<p>` inside it with `\n\n`. Confirmed against 12+ articles
across free and premium templates.

**Key quirk — duplicated lead image caption.** Because the container
selected includes the `<figure>`/image block, the first "paragraph" of
`articleBody` is often the image caption/credit line (e.g. "Jambojet
Managing director Karanja Ndegwa addresses guests..."), and on some articles
it appears **twice** in a row (once from a `<figure>` inside the free/outer
`div.story-content`, once more from a duplicate `<figure>` inside the
premium-gated one, or from stray nested `<figure>` markup even on free
articles). Kept as-is (raw passthrough) rather than heuristically stripped,
consistent with this portfolio's standardmedia-scraper precedent (its own
"Key quirk #3" — no reliable structural marker separates a caption line from
a genuinely short opening sentence).

**Key quirk — mixed `\r\n` and `\n` line endings.** The CMS's own paragraph
text sometimes contains raw `\r\n` line breaks mid-paragraph (a Word-paste
artifact, alongside stray `<o:p></o:p>` tags that `BeautifulSoup` strips
automatically since they carry no text), while the `\n\n` paragraph
separator this extractor adds is a plain `\n`. Both are preserved as-is.

**Genuine bodyless content type — NOT a bug.** The `/opinion/cartoon/`
section (editorial cartoons) renders a `div.story-content` containing only
an image, with **zero** `<p>` text — confirmed on a live sample
(`cartoon-august-24-2026`). `extract_article()` treats an empty string as a
legitimate result here (only a **missing** `div.story-content` container
raises `UnexpectedShape`, per this portfolio's fail-loud convention) — a
genuinely bodyless article shouldn't crash the whole run. The `/in-pictures`
photo-gallery section was spot-checked and, unlike cartoons, DOES carry
narrative body text alongside its photos on the one sample tested — it was
not assumed to be uniformly bodyless.

### 3. Not-found behavior

Two distinct shapes, both mapped to `_error: "not_found"`:

- **Malformed date segment** (last URL path segment doesn't start with
  `YYYY-MM-DD-`, e.g. `/news/9999-99-99-totally-fake-slug`) → real **HTTP
  404**.
- **Well-formed URL, nonexistent slug** (e.g.
  `/news/2026-08-26-this-article-does-not-exist-xyz123`) → **HTTP 200**, but
  the page silently falls back to a generic homepage-shell template: no
  flight jsonLd, no `div.story-content`, and `<title>` is the bare site name
  `"The Star"` — confirmed a **real** article's `<title>` is always its
  headline text verbatim, with no site-name suffix, on every sample. This
  distinguishes the soft-404 from genuine template drift: `extract_article()`
  only raises `UnexpectedShape` when the jsonLd is missing AND the title is
  NOT exactly this soft-404 marker string.

### 4. Latest headlines — `S2-sitemap`

`GET https://www.the-star.co.ke/articles/sitemap/1.xml`

`/sitemap_index.xml` lists 50 numbered `articles/sitemap/N.xml` files (plus
`/sitemap.xml` itself, which only carries 4 static pages — home, search,
privacy-policy, terms — not articles, and `/sections/sitemap.xml`, not
probed). `articles/sitemap/1.xml` was confirmed to carry same-day articles
(items dated the day of the fetch, 2026-08-26, mixed with the prior day).
This is a **plain** XML sitemap (`xmlns=".../sitemap/0.9"`, `loc`/`lastmod`/
`changefreq` only) — no Google News `news:` namespace, no `news:title`, no
per-item category.

**Key quirk — entries are not reliably ordered.** Within one fetch, `lastmod`
timestamps were observed out of order (e.g. an item with an earlier `lastmod`
appearing before one with a later `lastmod`). `extract_sitemap_items()`
sorts all parsed entries by `lastmod` descending before the caller applies
`limit`, so `latest` mode reliably returns the freshest items first
regardless of file order.

**No title field** — a readable `title` is derived from the URL's own
date-slug segment (date prefix stripped, hyphens → spaces, title-cased),
mirroring `expresstribune-scraper`'s precedent for sitemaps without a title
element. This is cosmetic only, not a substitute for the real `headline`
field returned by `article` mode.

No RSS feed was probed for since `/articles/sitemap/1.xml` already satisfies
the `latest`-mode freshness requirement, and no `sitemap:`/`Sitemap:` lines
appear in `robots.txt` to point at anything more specific (Google-News-style
or otherwise).

## Paywall behavior

**No hard paywall for HTTP-only scraping.** `isAccessibleForFree: false` +
a `.premium-content` `hasPart.cssSelector` were observed on at least one
sampled article (the DCP-leader Gachagua political story). But **the full
`articleBody` reconstructed from HTML was NOT truncated or missing** for
that article (3,660 characters, matching the flight payload's own
`article_word_count` analytics field within normal caption/whitespace
variance) — confirmed by comparing directly against a same-day free article
from the same section. Verdict: soft/cosmetic paywall only (a client-side
CSS gate, `aria-hidden="true"` on the gated wrapper), no metering enforced
against a non-browser HTTP client.

## Known limits

- `description` is `null` on every sampled article's JSON-LD node — not a
  bug, this CMS simply doesn't appear to populate the field at all (unlike
  standardmedia-scraper, where it's populated on some sections).
- The leading photo-caption/credit line (sometimes duplicated) in
  `articleBody` is kept as-is rather than stripped — see the HTML-fallback
  quirk above. Downstream consumers wanting clean narrative-only text should
  treat the first one or two `\n\n`-separated chunks as possible caption
  noise if they look caption-shaped.
- Only `/opinion/cartoon/` was directly confirmed to produce a genuinely
  empty `articleBody` (image-only content, zero `<p>` text). Other
  potentially-similar sections (`/video`, `/news/podcasts`,
  `/news/infographics`, `/news/twitter-space`) were not individually
  sampled and might follow the same pattern or might need a different
  strategy entirely if their JSON-LD `@type` isn't `NewsArticle` — this
  would currently raise `UnexpectedShape` rather than silently degrade.
- `author` is always a single `Person` object on every section sampled
  (news, business, sports, opinion, sasa) — no section using a list-of-authors
  shape was found, but this wasn't exhaustively verified across all ~25
  section/subsection combinations linked from the homepage.
- `/sitemap.xml` (the root file referenced generically by convention) does
  NOT carry article URLs on this site — only `/sitemap_index.xml` →
  `/articles/sitemap/N.xml` does. Only sitemap `1` was used/verified for
  freshness; sitemaps `2`-`50` were not sampled (presumably older/paginated
  archives, standard for this pattern).

## Diff cadence

Quarterly smoke test recommended.
