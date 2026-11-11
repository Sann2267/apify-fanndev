# Crawling method

## Target

Substack (`*.substack.com` and any custom domain a publication has mapped,
e.g. `www.noahpinion.blog`) — a hosted newsletter platform. Objective:
convert a post (or a whole publication's archive) to clean Markdown for AI
ingestion (RAG / embeddings / LLM context), HTTP-only, no login.

## Recon (2026-08-29)

Live-tested against `noahpinion.substack.com` (subdomain) and its mapped
custom domain `www.noahpinion.blog`, with `curl_cffi` (`impersonate="chrome131"`),
no proxy, no warmup request, no cookie jar:

| Endpoint | Result |
|---|---|
| `GET /api/v1/archive?sort=new\|top&offset=<n>&limit=<n>` | `200 JSON` — paginated post-metadata list. `body_html` is always `null` here. Offset past the end returns `200 []` (clean pagination stop condition, not an error). |
| `GET /api/v1/posts/<slug>` | `200 JSON` — full post detail including `body_html`. |
| `GET /api/v1/publication`, `/api/v1/publication/self` | `403 "Not authorized"` — requires an authenticated session. Out of scope. |
| `GET /` (homepage) | `200 HTML` — embeds `window._preloads = JSON.parse("...")`, whose `pub` key is the full publication profile (name, subdomain, custom_domain, hero_text, author, subscriber-count order of magnitude, etc.), unauthenticated. Used as the S2-html fallback for publication metadata. |
| Same endpoints via the custom domain (`www.noahpinion.blog`) instead of the `*.substack.com` subdomain | Identical `200` responses — the API is proxied per-host, not just on the `.substack.com` apex. |

**No WAF was ever triggered** — every request above returned a clean response
to a plain, unauthenticated request with an ordinary Chrome TLS profile. No
challenge page, no CAPTCHA, no `403`/`429` from anything other than the
genuinely-requires-auth endpoints above. This matches this project's own
`.ai/project/sosmed-platforms.md` prior notes on Substack ("No auth, no
significant rate-limit").

### Paywall behavior (`audience: "only_paid"`)

For posts marked `only_paid`, the public (unauthenticated) `/api/v1/posts/<slug>`
response's `body_html` is **upstream's own free-preview truncation** — cut off
mid-paragraph, not the full post. Confirmed live:

- Free post (`audience: "everyone"`): `body_html` = 61,018 chars, ends with
  the article's own closing paragraph (share button HTML follows, stripped —
  see below).
- Paid post (`audience: "only_paid"`): `body_html` = 13,688 chars, ends
  mid-sentence with no closing content.

This actor does **not** attempt to bypass that paywall (no login, per this
project's constraints, and it would be against Substack's own access
control for a public/anonymous scraper regardless). Each record's
`content_truncated` field (`audience == "only_paid"`) tells consumers
plainly whether `markdown`/`body_html` is the full post or a preview.

### Body cleanup before Markdown conversion

`body_html` includes Substack's own injected CTA boilerplate at the end of
every post — `<p class="button-wrapper">` "Subscribe now" / "Share" /
"Leave a comment" buttons, and the `<div><hr></div>` divider that used to
separate them from the article body. These are stripped
(`extractor.clean_body_html`) before conversion to `markdownify` so the
`markdown` field is clean author prose, not scraper-visible chrome. Images
are kept (`![alt](src)`) — nothing about the actual article content is
removed, only the platform's own UI cruft.

## Chosen stack

- `curl_cffi` (`impersonate="chrome131"`) — matches portfolio default; no
  WAF means any HTTP client would have worked, kept for consistency and in
  case of a future block.
- `BeautifulSoup4` (`lxml` parser) — strip boilerplate elements before
  conversion.
- `markdownify` — HTML → Markdown (ATX headings, `-` bullets).
- No browser automation anywhere in this actor.

## Mode design

One actor, `mode` input (per this project's established pattern — see
`luma-scraper`, `bluesky-scraper`):

- **`post`** — one or more specific post URLs → one Markdown record each.
- **`archive`** — one or more publications → paginate the full archive,
  fetch every post's detail, one `PUBLICATION_PROFILE` record (S2-html) +
  one `POST` record per post (S1-api), same shape as `post` mode's output.

Rejected: separate actors per mode (`substack-post-scraper`,
`substack-archive-scraper`, ...) — unnecessary maintenance/monetization
overhead for two operations that share ~90% of their code and both exist to
serve the same "newsletter → Markdown" objective.
