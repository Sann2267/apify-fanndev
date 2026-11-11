# Crawling Method — Global Times

**Last verified:** 2026-08-24

## WAF

`globaltimes.cn` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the Google News sitemap
-- no challenge body, no 403.

`robots.txt` is a single 2-line file (`User-agent: *` with **no
`Disallow` at all**, just a `Sitemap:` line) -- no Claude/GPTBot/
anthropic-ai disallow.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.globaltimes.cn/page/<yyyymm>/<id>.shtml`

This is the **first actor in the portfolio with zero ld+json** of any
kind, and almost no useful `<meta>` tags (only `og:image` was present).
Every field is scraped from plain HTML on this legacy CMS:

- `headline` — from `<title>`, with the `" - Global Times"` site-name
  suffix stripped via regex.
- `author` — from `<span class="byline">` (e.g. `"By Xinhua"` or `"By
  Zhang Weilan and Qi Xijia"`), with the `"By "` prefix stripped.
- `publishedRaw` — from `<span class="pub_time">` (e.g. `"Published: Aug
  23, 2026 09:59 PM"`). **Deliberately kept as a raw string, not parsed
  into ISO-8601** -- the format has no explicit timezone and parsing it
  correctly would require hardcoding an assumed locale/timezone, which
  risks silently mis-dating articles; raw passthrough is the safer
  choice per this portfolio's conventions.
- `articleBody` — from `<div class="article_right">`. **Key quirk:** this
  CMS does not wrap paragraphs in `<p>` tags at all (aside from one
  special case, see below) -- the whole body is one long run of text
  nodes separated by `<br>` tags, verified consistent across all 3 sampled
  articles (14-35 reconstructed paragraphs each). The extractor replaces
  every `<br>` with a newline character, then re-groups the resulting
  lines into paragraphs on blank-line boundaries (2+ consecutive newlines
  = a paragraph break).
- Before this `<br>`-to-paragraph reconstruction, every `<p class="picture">`
  element (an image caption) is `.decompose()`d out of the tree first.
  These captions **duplicate the article's opening sentence almost
  verbatim** (confirmed identical wording, differing only by an appended
  photo credit, e.g. `"...Photo: Xinhua"`) across all 3 samples -- without
  this removal, every article would get a spurious near-duplicate first
  paragraph.

No paywall marker of any kind was found (state media, fully open-access).

### 2. Latest headlines — `S2-sitemap`

`GET https://www.globaltimes.cn/sitemap.xml`

Google News sitemap, advertised via `Sitemap:` in `robots.txt`. Standard
shape: `news:title`, `news:publication_date` (proper ISO-8601 with
timezone, unlike the article page's raw `pub_time` string),
`news:keywords` (comma-separated, with a trailing empty element observed
in one sample -- `"cooperation,global,italy,dialogue,china,"` -- filtered
out by stripping and dropping empty strings before building the list).

## Paywall behavior

None observed. Chinese state media, fully open-access with no metering of
any kind found in any sample.

## Known limits

- Only 3 articles sampled in depth (a China-US human-interest feature, a
  tech/robotics education piece, and a trade/manufacturing story). All 3
  happened to share the exact same markup pattern (`<br>`-separated body,
  one `p.picture` caption near the top) -- a structurally different
  article type (e.g. a photo gallery or video-embed page) was not
  sampled and might not fit this extraction path.
- `publishedRaw` is intentionally unparsed (see above) -- downstream
  consumers needing a machine-sortable date should prefer
  `publicationDate` from `latest` mode, or parse `publishedRaw`
  client-side with explicit knowledge of the site's date format and
  implied timezone (Beijing time, UTC+8, inferred from context but not
  explicitly labeled on the page).
- 404s are real HTTP 404s (verified with a synthetic out-of-range article
  ID) -- no soft-404 behavior observed.

## Diff cadence

Quarterly smoke test recommended.
