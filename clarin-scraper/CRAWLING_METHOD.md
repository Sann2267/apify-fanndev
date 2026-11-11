# Crawling Method — Clarín

**Last verified:** 2026-08-25

## WAF

`clarin.com` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on homepage (4.1 MB, real Next.js-rendered HTML, not a JS
challenge shell), article pages, and the Google News sitemap -- no
challenge body, no 403.

`robots.txt` disallows only `/api/`, `/redaccionfiler/*`, `/viafoura/*`,
a handful of narrow paths (`/autor/*?`, `/videos/*?`, `/videoloop/*_3_`,
`/prueba-sistemas/`, `/videoamp/`, `/agenda-deportiva/`), `/cdn-cgi/`,
and `/_next/` -- no Claude/GPTBot/anthropic-ai disallow of any kind. It
advertises three `Sitemap:` lines, including a Google News sitemap used
for `latest` mode.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.clarin.com/<section>/<slug>_0_<id>.html`

The page emits **5 separate ld+json blocks**: `BreadcrumbList`,
`Organization`, `NewsMediaOrganization`, `NewsArticle`, and `ItemList` --
the extractor scans all `<script type="application/ld+json">` tags and
picks the one whose `@type` is (or, on this site, **contains** --
`@type` arrives as a list `["NewsArticle"]`, not a bare string like on
tass.com/eluniversal.com.mx) `NewsArticle`.

That block carries `headline`, `description`, `datePublished`,
`dateModified`, `author` (a `Person` list with `name`/`url`/`email`/
`jobTitle` for bylined opinion pieces -- author node uses a bare
`"type"` key, not `"@type"`, unusually -- or a single `Organization`
dict `{"name": "Redacción Clarín"}` for wire-style news), `publisher`
(`Organization`, always `"Clarín"`), `keywords` (comma-separated
string, one sample had a stray leading space on one term -- stripped),
`image` (list of `ImageObject`), `articleSection`, and
**`isAccessibleForFree`** (a genuine, verified-mixed paywall flag, see
below).

The ld+json block **does carry an `articleBody` field, but it is NOT
used** -- recon found its punctuation is corrupted: commas inside
numbers are stripped (`"1,8%"` in the real HTML became `"18%"` in the
ld+json articleBody -- a materially different number on a numbers-heavy
economics story). This is unsafe to ship as-is.

Full text is instead scraped from HTML `#cuerpo` (a `div id="cuerpo"`
nested inside `article#storyBody`). **First false lead**: the ld+json
`hasPart.cssSelector` field advertises `.paywall_content` as "the"
content selector -- but that class is applied to the whole `<body>` tag
site-wide (`<body class="paywall_content">`, confirmed via direct string
search on the raw HTML), not to a real content container. Selecting it
sweeps in every `<p>` on the page (nav, footer, related-article widgets)
and happened to *look* plausible in an early test because the noise
paragraphs sat at predictable positions -- a reminder to verify DOM
ancestry, not just trust a schema.org-advertised selector. `#cuerpo`,
found by walking up from a known body paragraph, is the real container:
confirmed present with the same paragraph count on both free and
paywalled samples -- Clarín server-renders the complete article body
regardless of subscription status; the paywall is a client-side JS/CSS
overlay applied on top, which an HTTP-only fetch never triggers.
`#cuerpo` already excludes, by DOM structure alone (they live in sibling
nodes, not inside it), the "enable JavaScript" noscript warning, the
"Solo suscriptores" paywall badge, and the trailing "Newsletter Clarín"
/ "Edición impresa" CTA blocks -- confirmed on 3 samples. The extractor
still carries exact-match filters for those strings as a defense-in-
depth safety net in case a different article template nests them inside
`#cuerpo`. Inline dateline/wire-style credit lines that DO live inside
`#cuerpo` on some articles (e.g. `"Misiones. Corresponsalía."`, `"D.D."`)
are LEFT IN as real editorial content, matching the "Lee también"
treatment in `eluniversal-scraper`.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.clarin.com/sitemaps/sitemap_google_news.xml`

Google News sitemap: `loc`, `lastmod`, `news:publication_date`,
`news:title` (plain text, not CDATA-wrapped -- unlike eluniversal's
sitemap, no extra unescape needed), `image:loc`, `image:caption`
(CDATA-wrapped, passed through as-is). **No `news:keywords` field** is
present on this sitemap, so `latest` mode output carries no keywords.

## Paywall behavior

**Confirmed genuinely mixed, sampled honestly:**

- 3 breaking-news articles (`informacion-general`, `sociedad`, `mundo`
  sections) — all `isAccessibleForFree: true`.
- 5 `/opinion/` (long-form analysis) articles sampled — 4 were
  `isAccessibleForFree: true`, 1 was `isAccessibleForFree: false`
  ("Insólitos argumentos de Milei..." by Walter Schmidt).
- For the one confirmed paywalled sample: the server-rendered HTML
  `div.paywall_content` contained the exact same full 25-paragraph body
  as the free samples' equivalent containers scaled to their own length
  — no truncation, no "read more to subscribe" cutoff mid-paragraph.
  Only a "Solo suscriptores" badge paragraph is added. This confirms the
  paywall is enforced client-side, not by withholding server HTML.
- `isAccessibleForFree` (and the derived `_paywalled` output field) is
  therefore a genuine, honest signal about the site's own subscription
  gating, but **never** an indicator of truncated or fabricated text —
  `articleBody` is complete either way.

## Known limits

- Only the `/opinion/` section was found to carry paywalled samples in
  this recon pass; other long-form sections (e.g. `revista-viva`) were
  not sampled and may also gate content — the extractor handles them
  identically since it reads the flag directly from ld+json rather than
  assuming a section-based rule.
- 404s are real HTTP 404s (verified with a synthetic out-of-range
  article slug) — no soft-404 behavior observed.
- ld+json `articleBody` is present but intentionally unused due to
  comma-stripping corruption — do not "simplify" the extractor to use it
  without re-verifying this bug is fixed upstream first.
- Only 8 articles sampled in depth (3 breaking news, 5 opinion). All
  shared the same `div.paywall_content > p` markup pattern regardless of
  paywall status. A structurally different article type (e.g. a
  live-blog, photo-gallery, or video-centric page) was not sampled.

## Diff cadence

Quarterly smoke test recommended.
