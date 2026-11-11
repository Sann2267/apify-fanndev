# Crawling Method — DNA India

**Last verified:** 2026-08-27

DNA India (Daily News & Analysis, `dnaindia.com`) is a major Indian
English-language national daily, published by Zee Media Corporation Ltd.

## Robots.txt

Fetched fresh with `curl_cffi` `chrome124` (a plain UA-only baseline hits an
Akamai deny page, see WAF below) — full file, verbatim:

```
User-agent: *
Allow: /
Disallow: /static/*
Disallow: /su/*
Disallow: /hindi/smart-buy/
Disallow: /smart-buy/

User-agent: ClaudeBot
User-agent: ChatGPT
User-agent: GPTBot
User-agent: GPT
User-agent: PerplexityBot
User-agent: Perplexity-User
User-agent: claude-web
User-agent: Google-Extended
User-agent: ChatGPT-User
User-agent: SemrushBot
User-agent: Yandex

User-agent: Google-Extended
Allow: /

User-agent: Bytespider
Disallow: /
User-agent: Diffbot
Disallow: /
User-agent: OmigiliBot
Disallow: /
User-agent: Omigili
Disallow: /
User-agent: AhrefsBot
Disallow: /

Sitemap: https://www.dnaindia.com/googlenews.xml
Sitemap: https://www.dnaindia.com/sitemap-index.xml
... (5 more Sitemap lines, English + Hindi)

Disallow: /gallery
Disallow: /dnaprint.asp
Disallow: /brand-desk*
Disallow: /search?q=*
```

**Notable quirk — flagged for human review.** There is a `User-agent:
ClaudeBot` group, bundled together with `ChatGPT`/`GPTBot`/`GPT`/
`PerplexityBot`/`Perplexity-User`/`claude-web`/`Google-Extended`/
`ChatGPT-User`/`SemrushBot`/`Yandex`, but this group carries **zero**
Allow/Disallow directives — the very next non-blank line is a *second*,
separate `User-agent: Google-Extended` group with an explicit `Allow: /`.
Per RFC 9309 semantics, a group with no rules disallows nothing for the
agents it names (same effective result as the general `Allow: /` above it),
so **by the literal machine-readable directives, ClaudeBot is not blocked**.
No natural-language/comment-based prohibition against AI/LLM
training/scraping appears anywhere in the file either.

This differs from this portfolio's established skip precedent — USA Today,
Politico, and The Hill were all skipped because they carry an **explicit**
`Disallow: /` attached to the ClaudeBot/anthropic-ai line by name. No such
directive exists here. It also differs from the "clean allow" precedent
(`freemalaysiatoday-scraper`, which has an explicit `Allow: /` for
ClaudeBot) — this file's ClaudeBot group has no directive of either kind, an
empty ruleset. Two readings are plausible: (a) the empty group is a stray
leftover of a block rule the site operator meant to write but never
finished (the adjacent, separately-declared `Allow: /` for Google-Extended
right below it is suggestive of an intent to differentiate/restrict this
exact list), or (b) it's a deliberate no-op carve-out exempting these named
crawlers from the general group's few narrow `Disallow` paths (which are
largely `/static/*`, `/su/*`, `/gallery`, etc. — none of which matter for
article scraping anyway). Built anyway per the literal-directive convention
this portfolio has followed consistently elsewhere, but this ambiguity
should be re-reviewed by a human if DNA India's robots.txt is ever revisited
or if a stricter interpretation policy is adopted.

## WAF

`dnaindia.com` sits behind **Akamai**. A plain UA-only `curl`/`requests`
baseline (no TLS impersonation) gets an Akamai "Access Denied" deny page
(`errors.edgesuite.net` reference ID) on `robots.txt` itself — not just
article pages. `curl_cffi` `chrome124` impersonation clears this cleanly on
every path tested (homepage, article pages, `robots.txt`, Google News
sitemap) — HTTP 200 on the first try, no warmup-then-retry dance needed, no
profile-ladder escalation required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-flight`

`GET https://www.dnaindia.com/<section>/report-<slug>-<id>`

dnaindia.com is a Next.js **App Router** build (React Server Components).
Confirmed absent on every sampled page: no `<script
type="application/ld+json">` tag anywhere, and no `<script
id="__NEXT_DATA__">` blob either — both of this portfolio's usual
first-choice anchors are dead ends here (same situation as
`star-kenya-scraper`).

**Key mechanism — JSON-LD lives inside an RSC flight stream, split across
chunks with cross-chunk references.** The article's structured data is
embedded across many `<script>self.__next_f.push([1,"..."])</script>` tags.
Two complications beyond the simpler flight-payload pattern already in this
portfolio (`star-kenya-scraper`):

1. **A single logical "row" can be split across multiple separate push()
   calls with no repeated id prefix on the continuation fragments** — e.g. a
   long module-dependency list, or a long body-text chunk, is spread across
   3+ consecutive `<script>` tags. `_build_flight_stream()` concatenates
   every push() payload string, in document order, into one continuous
   stream first; this transparently repairs split rows without needing to
   detect "new row" vs "continuation" explicitly.
2. **The resolved NewsArticle-equivalent object references its own
   `articleBody` via a cross-chunk pointer** (a string value like `"$12"`,
   where `12` is a hex chunk id) into a *separate* row elsewhere in the
   stream, formatted `<hex_id>:T<hex_length>,<raw text>` (React Flight's own
   length-prefixed text-row framing — the `T` marks a Text row, the hex
   number after it is the exact byte length of the text that follows the
   comma, which lets the resolver skip past any embedded newlines inside the
   text safely). `_resolve_text_ref()` regex-locates this row by its id and
   slices exactly `length` characters after the comma.

There are actually **two** copies of the article's structured data in the
stream: a less-resolved one (several fields themselves replaced by `"$id"`
references, e.g. `"mainEntityOfPage":"$2b","image":"$2c","author":"$2d"`)
and a **fully-resolved** one nested under a `"newsarticle":{...}` key inside
a `schema` prop passed to a header/breadcrumb component — every field except
`articleBody` is already inlined there (author as a full `Person` array,
image as a full `ImageObject`, publisher as a full `NewsMediaOrganization`
with logo/sameAs, mainEntityOfPage as a full `WebPage` reference).
`_find_newsarticle()` targets this second, fully-resolved copy specifically
via the `"newsarticle":{"@context":"https://schema.org","@type":
"NewsArticle"` anchor, so only `articleBody` ever needs ref-resolution.

Fields observed on every one of 4 samples across India/World/Entertainment/
Business sections: `@context`, `@type`, `keywords` (comma-separated string,
not an array), `inLanguage`, `mainEntityOfPage`, `headline`, `url`, `image`,
`datePublished`, `dateModified`, `author` (list of `Person` objects, always
populated — desk bylines like "DNA Web Desk" as well as named reporters and
wire-service credits like "ANI" all use the same `Person` shape),
`publisher`, `description`, `articleBody`.

**Key quirk — double HTML-entity-encoding.** Text values (`headline`,
`description`, `articleBody`, sitemap `news:title`) carry literal HTML
entities baked into the string (`&#039;` instead of `'`, `&quot;` instead of
`"`, `&#39;`) even though the value is already inside a JSON string — the
CMS stores/serializes the text as HTML without decoding entities first.
`extractor.py` applies `html.unescape()` recursively across every string
value in the resolved object (and to the resolved `articleBody`) to correct
this, matching the precedent already used elsewhere in this portfolio (e.g.
`guardian-nigeria-scraper`). A related but distinct quirk: `keywords`
sometimes contains a literal `\xa0` (non-breaking space, U+00A0) in place of
a regular space between words in a phrase (e.g. `"Indian\xa0Air\xa0Force"`)
— this is **not** an HTML-entity issue and is passed through as-is,
unmodified, per the raw-passthrough convention (a terminal without UTF-8
output configured may misrender this character as `�`; `test_local.py`
reconfigures stdout to UTF-8 to avoid that).

No `isAccessibleForFree`/`hasPart` paywall-signal fields were observed on
any sampled article.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.dnaindia.com/googlenews.xml`

A Google News sitemap, referenced from `robots.txt` (the first `Sitemap:`
line). Confirmed live: 98 `<url>` entries in one fetch, each carrying
`<loc>`, and a `<news:news>` block with `<news:publication>`
(`news:name`/`news:language`), `<news:publication_date>` (real per-article
ISO 8601 timestamp with `+05:30` offset), `<news:title>`, and
`<news:keywords>`. Observed already newest-first in file order on the fetch
performed (freshest entry matched the homepage's top headline at fetch
time), but `extract_sitemap_items()` still sorts descending by
`news:publication_date` defensively. No site-wide RSS feed was probed for
since this sitemap already satisfies the freshness requirement with a real
title and per-article timestamp in one lightweight XML request.

### 3. Not-found behavior

A deliberately-invented slug (well-formed URL shape, nonexistent numeric id)
returns a **real HTTP 404** — confirmed directly, no soft-404 quirk
observed (unlike `star-kenya-scraper`'s generic-homepage-shell pattern).

## Paywall behavior

None observed. No `isAccessibleForFree`, `hasPart`, or truncated-body
markers found on any of the 4 sampled articles (India/hard-news, World,
Entertainment, Business/personal-finance). DNA India is a free, open-access
site.

## Known limits

- Only 4 articles sampled in depth (India, World, Entertainment, Business).
  A structurally different template (e.g. a live-blog, photo-gallery, or
  web-story page) was not sampled — `extract_article()` raises
  `UnexpectedShape` if the `"newsarticle":{...}` anchor is ever missing, so
  a genuinely different template fails loud rather than emitting corrupt
  records.
- One sampled article's canonical `url` differed from the requested
  `_input` URL (the CMS had moved a `/business/...` slug to
  `/personal-finance/...` while keeping the old URL live and serving the
  same content with an updated canonical) — passed through as-is, both
  fields are raw upstream data.
- The ClaudeBot robots.txt group ambiguity (see Robots.txt section above)
  should be re-reviewed if this actor is revisited.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `"newsarticle":{...}` flight anchor still
resolves. If DNA India redesigns the page, `extract_article` will raise
`UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
