# Substack Newsletter to Markdown Scraper

Convert Substack newsletter posts into clean Markdown — ready to feed into
an AI pipeline (RAG, embeddings, LLM context) — either one post at a time or
a publication's entire archive. No account or login needed.

## Why use this actor

- Turns a newsletter post straight into clean, ready-to-use Markdown —
  title, subtitle, author, and date up top, then the body text, with the
  platform's own "Subscribe"/"Share" buttons stripped out
- Also returns the full original data for every post (title, word count,
  publish date, cover image, author info, and more) alongside the Markdown
- Crawl a single post by URL, or point it at a whole publication and get
  every post in the archive automatically, newest-first or top-first
- No account, login, or API key required
- Honest about paywalled posts — free posts return the full text; posts
  restricted to paying subscribers return the preview text the publication
  itself makes public, clearly flagged so you know which is which (see
  `content_truncated` below)
- Automatic retries on temporary network hiccups

## How it works

Pick a `mode`:
1. **`post`** — give it one or more newsletter post URLs; get back the
   Markdown and full details for each.
2. **`archive`** — give it a publication (its own domain, or just its
   Substack subdomain); get back that publication's profile plus every post
   in its archive, up to the limit you set.

Results stream into your dataset, ready to download as JSON, CSV, or open
directly for your AI pipeline.

## Input

**Single post:**
```json
{
  "mode": "post",
  "url": "https://noahpinion.substack.com/p/the-death-of-market-street"
}
```

**Whole publication archive:**
```json
{
  "mode": "archive",
  "url": "noahpinion.substack.com",
  "sort": "new",
  "maxItems": 50
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"post"` (default) — convert specific post URL(s). `"archive"` — crawl a whole publication. |
| `url` | string | `post` mode: a single post URL. `archive` mode: a publication URL, custom domain, or bare subdomain (e.g. `"noahpinion"`, `"noahpinion.substack.com"`, or `"https://www.noahpinion.blog"`). |
| `urls` | array | Multiple post URLs (`post` mode) or multiple publications (`archive` mode) in one run. |
| `sort` | string | `archive` mode only — `"new"` (default, newest first) or `"top"` (most popular first). |
| `maxItems` | integer | `archive` mode only — max posts per publication. Default 50, max 10,000. Pagination is followed automatically until this cap or the end of the archive. |
| `maxConcurrency` | integer | How many URLs/publications to process in parallel (and, in `archive` mode, that publication's own per-post fetch concurrency). Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default (kept for production robustness; see `CRAWLING_METHOD.md`). |

## Output

**`post` mode / `archive` mode's per-post records** — one record per post
(truncated here for readability; the full original post data is included
on every record alongside `markdown`):
```json
{
  "_input": "https://noahpinion.substack.com/p/the-death-of-market-street",
  "_source": "S1-api",
  "_scrapedAt": "2026-08-28T20:24:29Z",
  "title": "The death of Market Street",
  "subtitle": "How San Francisco turned its most iconic street into a giant empty scar.",
  "slug": "the-death-of-market-street",
  "post_date": "2026-08-26T09:12:35.276Z",
  "canonical_url": "https://www.noahpinion.blog/p/the-death-of-market-street",
  "audience": "everyone",
  "content_truncated": false,
  "wordcount": 2165,
  "publishedBylines": [{ "name": "Noah Smith", "handle": "noahpinion", "...": "5 more fields" }],
  "markdown": "# The death of Market Street\n\nHow San Francisco turned its most iconic street into a giant empty scar.\n\n*Noah Smith · 2026-08-26*\n\nhttps://www.noahpinion.blog/p/the-death-of-market-street\n\n---\n\n[![](https://substackcdn.com/image/fetch/...)](https://substackcdn.com/...)\n\nI still remember the first time I set foot on Market Street. ... <19,560 chars total>",
  "body_html": "<61,018 chars — the raw HTML markdown was converted from>",
  "...": "40+ more original fields (comments, reactions, cover image, etc.)"
}
```

**`archive` mode** — one `PUBLICATION_PROFILE` record per publication, then
one `POST` record per post found (same shape as above, plus `recordType`):
```json
{
  "_input": "noahpinion.substack.com",
  "_source": "S2-html",
  "recordType": "PUBLICATION_PROFILE",
  "name": "Noahpinion",
  "subdomain": "noahpinion",
  "custom_domain": "www.noahpinion.blog",
  "hero_text": "Economics and other interesting stuff",
  "...": "60+ more original fields"
}
```

| Field | Type | Description |
|---|---|---|
| `markdown` | string | The post converted to clean Markdown, with a title/subtitle/author/date header and the platform's own Subscribe/Share buttons stripped out. |
| `content_truncated` | boolean | `true` for posts restricted to paying subscribers — `markdown`/`body_html` is then the publication's own public preview, not the full post. |
| `title` / `subtitle` / `slug` / `post_date` / `canonical_url` | string | Post metadata, passed through as the publication provides it. |
| `audience` | string | `"everyone"` (free) or `"only_paid"` — see `content_truncated`. |
| `wordcount` | integer | The publication's own word count for the full post. |
| `publishedBylines` | array | Author(s) of the post. |
| `body_html` | string | The original HTML `markdown` was generated from. |
| `recordType` | string | `archive` mode only — `"PUBLICATION_PROFILE"` or `"POST"`. |
| `name` / `subdomain` / `custom_domain` / `hero_text` | string | `PUBLICATION_PROFILE` record — the newsletter's own name, domain, and tagline. |

A record with `_error` instead of the fields above means that input could
not be processed (for example, `"_error": "not_found"` for a post that
doesn't exist, or `"_error": "invalid_post_url"` if a URL isn't a Substack
post link).

## Known limits

- **Posts restricted to paying subscribers return a preview, not the full
  text.** This is the publication's own choice, enforced by Substack for
  every anonymous visitor — not something this actor can or should bypass.
  `content_truncated: true` flags exactly which records this applies to.
- **Reader comments are included verbatim when a post has them**, since
  they're part of the same data the publication returns for a post. If your
  pipeline only wants the article text, use the `markdown` field, which
  never includes comments.

## Store positioning (market research, 2026-08-29)

This is a saturated niche — 20+ distinct Substack-scraper sellers were found
on the Store during research for this actor, from 1 to 463 users and up to
~95,000 total runs on the largest listing (`digispruce/substack-scraper`).
Two direct competitors already sell the same "Markdown for AI/RAG" angle
this actor leads with: `brilliant_gum/substack-insights-scraper` ($0.015 per
item, flat — only 242 runs to date) and `benthepythondev/newsletter-scraper`
(multi-platform, $0.001 per item at the FREE tier, marketed "LLM-Ready").
This actor's own differentiation is scope, not novelty: most competitors
bundle in Notes feeds, subscriber-email lead-gen, or nested comment
threads by default — this one stays to post↔Markdown conversion plus an
explicit `content_truncated` paywall flag (a transparency point only one
other listing, `hata1234/substack-scraper`, makes as plainly).

**Category:** Social Media (primary, matching 12 of the 20 comparable
listings) + AI (secondary — shared with the two direct Markdown/RAG
competitors above; not claimed by the lead-gen/email-harvest majority).

**Pricing:** Pay-per-event, single chargeable event
(`apify-default-dataset-item`, covering both `PUBLICATION_PROFILE` and
`POST` records) — no separate Actor-start fee, since this actor has no
warmup/auth cost to recoup (see `CRAWLING_METHOD.md`: no WAF, no login).
Comparable per-full-content-item prices found: $0.001 (`hata1234`,
`benthepythondev` FREE tier), $0.0023 (`automation-lab` "post-with-content"
FREE tier), $0.015 (`brilliant_gum`, an outlier with the lowest traction of
the direct-comparable set). Recommended: **$0.0015 per result** at the FREE
tier, tiering down to $0.0006 at DIAMOND (mirroring `benthepythondev`'s
tier spacing) — inside the sustainable $0.001–$0.0023 cluster, reflecting
that every record here always includes full Markdown content (not a
cheaper metadata-only tier the way `automation-lab`/`digispruce` split
theirs).
