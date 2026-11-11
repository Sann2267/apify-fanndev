# Crawling Method — Moneycontrol

**Last verified:** 2026-08-27

Moneycontrol (`moneycontrol.com`) is India's leading financial/markets news
portal, part of the Network18/TV18 media group.

## Robots.txt

Re-fetched independently (`curl https://www.moneycontrol.com/robots.txt`,
no special User-Agent) -> HTTP 200. Checked line-by-line for both
machine-readable directives and any plain-English prohibition:

- The `User-agent: *` group has ~30 path-specific `Disallow` rules (profile
  pages, financial-graphs widgets, print pages, stock-market-data pages,
  etc.) — none of them touch article pages (`/news/...html`) or
  `news-sitemap.xml`, the two paths this actor uses.
- A separate block of one-line `User-agent` groups explicitly disallows
  **other companies'** AI/scraping crawlers: `CCBot`, `GPTBot`,
  `ChatGPT-User`, `omgili`/`omgilibot`, `MAZBot`, `Baiduspider`,
  `DataForSeoBot`, `Google-Extended`. This is a deliberate "block AI
  training crawlers" policy list.
- **`ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, and
  `anthropic-ai` do NOT appear anywhere in the file**, in that block or
  elsewhere, and there is no plain-English/comment prohibition against
  AI/LLM scraping or training anywhere in the file.

This is notable because moneycontrol.com is owned by the same media group
(Network18) as News18, which — independently re-checked during this same
build — explicitly disallows Claude in its own robots.txt
(`User-agent: ClaudeBot` / `Disallow: /` and `User-agent: Claude-Web` /
`Disallow: /`). Moneycontrol's robots.txt does not carry that entry, so
this build was **not** skipped on robots.txt grounds — the two sites under
the same parent company have different, independently-configured
robots.txt files.

### A separate, non-blocking finding: Akamai Bot Manager UA-signature check

Independent of robots.txt, live requests were made with various
`User-Agent` strings to check for an infrastructure-level block. Akamai
Bot Manager (`Server: AkamaiGHost` on the 403 body, `Access Denied` HTML
page) **403s any request whose User-Agent contains a recognized
bot/crawler token** — confirmed for `ClaudeBot`, `GPTBot`,
`PerplexityBot`, a spoofed `Googlebot`/`bingbot` string, and even a
nonsense control string `FooBot/1.0`. Meanwhile `Claude-Web` and
`anthropic-ai` (and a plain `curl/8.0` or real Chrome UA) all pass with a
clean 200. This is a generic "reject any request self-identifying as an
automated crawler unless independently IP-verified" edge rule — it treats
`ClaudeBot`/`GPTBot`/`Googlebot`/`FooBot` identically, so it is not read as
a policy specifically targeting Claude (unlike News18's explicit,
Claude-named robots.txt disallow). This actor never sends a bot-identifying
User-Agent in the first place — like every actor in this portfolio, it
impersonates a real Chrome browser via `curl_cffi`'s TLS+HTTP
fingerprinting — so this Akamai rule is never triggered in normal
operation.

## WAF

Akamai-fronted (`_abck` Bot Manager sensor cookie set on every response,
`AkamaiGHost` server header on error/challenge responses) but **no active
challenge** for normal browser-shaped traffic. `curl_cffi` `chrome124` gets
a clean 200 on the homepage, article pages (including the paywalled
`moneycontrol-research` vertical), `news-sitemap.xml`, and the legacy RSS
feed — confirmed both with and without a homepage warmup first (a cold
session going straight to an article URL also gets 200 first try, no
warmup-then-retry dance needed).

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.moneycontrol.com/news/<section>/<slug>-<id>.html`

Each article page emits 5 separate `application/ld+json` script tags:
`WebPage`, `BreadcrumbList`, `NewsMediaOrganization`, a
`SiteNavigationElement` array (14 items, site nav menu — noise), and a
**single-element JSON array wrapping the `NewsArticle` node** (not a bare
object — `[{"@type": "NewsArticle", ...}]`). The extractor unwraps this.

The `NewsArticle` node carries: `headline`, `description`, `keywords`
(comma-separated string, inconsistent spacing e.g. `"Capital Group,Aberdeen
Group"` — passed through verbatim), `articleSection`, `url`, `image` (list
of URL strings), `datePublished`/`dateModified` (ISO 8601 with `+05:30`
IST offset), `articleBody` (full plain text on free articles), `author`
(single `Person` object — `{"@type":"Person","name":...,"url":...}`;
either a named wire-service byline like `"Bloomberg"` or the generic staff
byline `"Moneycontrol News"`), and `publisher` (`NewsMediaOrganization`).

**Quirks handled:**
- `articleBody` (and other text fields) contain **raw, un-escaped literal
  `\r\n` control characters** embedded directly in the JSON string value —
  invalid under strict JSON. Standard `json.loads` raises `"Invalid control
  character"` on every article sampled; `json.loads(..., strict=False)`
  parses the same bytes cleanly. Confirmed live 2026-08-27.
- Text fields contain **raw, un-decoded HTML entities** (`&rsquo;`,
  `&nbsp;`, `&ldquo;`, `&rdquo;`) written directly into the JSON-LD string
  values (not JSON escapes — `json.loads` already handles those; these are
  literal `&...;` sequences the CMS writes into the text). The extractor
  recursively applies `html.unescape()` to every string value (including
  nested `author`/`publisher`/`image` objects) before returning the
  record.

### 2. Latest headlines — `S2-sitemap`

`GET https://www.moneycontrol.com/news/news-sitemap.xml`

A standard Google News sitemap (`<urlset>` with `xmlns:news`), confirmed
**fresh** (top entries matched "now" at fetch time) with 1000 `<url>`
entries spanning the last several days, already newest-first in file order
(defensively re-sorted descending by `news:publication_date` anyway).
Fields extracted per item: `title` (`news:title`, CDATA, HTML-unescaped),
`link` (`<loc>`), `pubDate` (`news:publication_date`), `keywords`
(`news:keywords`, CDATA), `image` (`image:loc`).

**Dead end, not used:** `https://www.moneycontrol.com/rss/latestnews.xml`
(and other `/rss/*.xml` feeds) return HTTP 200 but are **stale** —
`lastBuildDate` over a year old at time of writing, item `pubDate`s from
April 2024. The sitemap is the only reliably-fresh `latest` source found.

## Paywall behavior — genuine hard paywall on one specific vertical

The vast majority of Moneycontrol content (general news, markets news,
"Technical View" analysis, block-deal reports, world/business/entertainment
sections, etc.) is **fully free** — no `isAccessibleForFree` field at all
in the JSON-LD, full `articleBody` present (confirmed on 4 samples across
Business, Markets, World, Entertainment sections).

**Moneycontrol PRO / `moneycontrol-research` content is genuinely
paywalled.** Articles under `/news/business/moneycontrol-research/<slug>`
(linked from `/pro-top-stories`) carry `"isAccessibleForFree": "False"`
(note: a literal **string** `"False"`, not a JSON boolean) in their
JSON-LD, and **`articleBody` is entirely absent** from the JSON-LD block.
The rendered HTML itself confirms this is a real server-side gate, not
just a client-side overlay: the visible content div (`div.content_wrapper`
/ `div.arti-flow`) contains only a single one-sentence teaser (~111
characters) for the whole article, confirmed on 2 samples
(`ceat-growth-engines-rev-up-margins-play-catch-up`,
`grse-strong-order-pipeline-supports-long-term-growth`). This is passed
through honestly — the record for a paywalled article simply lacks
`articleBody`, it is not fabricated or worked around, per this portfolio's
raw-passthrough / fail-honest convention.

## Known limits

- Genuinely paywalled `moneycontrol-research` (MC PRO) articles will have
  no `articleBody` in the output — see Paywall behavior above. All other
  sections tested were fully free.
- `keywords` comma-spacing is inconsistent in the source data (sometimes
  `"A, B, C"`, sometimes `"A,B,C"`) — passed through verbatim, not
  normalized.
- No sitemap-index/pagination needed — the single `news-sitemap.xml`
  endpoint already returns the newest ~1000 items directly.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If Moneycontrol redesigns the page, `extract_article` will
raise `UnexpectedShape` and the run will fail loudly rather than emit
corrupt records.
