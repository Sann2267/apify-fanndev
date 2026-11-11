# Crawling Method — Poshmark Scraper

**Last verified:** 2026-08-26

## Architecture decision: one multi-mode actor, three modes

Poshmark's public data splits into three "events" -- browsing listings
by brand/category, a specific listing's full detail, and a seller's
closet/profile -- served by the same server-rendered Vue app, the same
(no) auth, the same client. One actor with a `mode` input follows this
portfolio's established convention (`twitch-channel-scraper`,
`civitai-scraper`, `huggingface-scraper`) rather than three actors
duplicating the same Dockerfile/retry-client/proxy wiring.

## WAF

**None.** `curl_cffi` `chrome124` gets clean 200s on the homepage,
browse pages, listing pages, and closet pages alike — no Cloudflare/
DataDome/PerimeterX challenge of any kind. The only anti-bot-adjacent
signal observed is a passive Sift Science fraud-detection tracking
cookie (`esid=sift:...`) set on every response, which never blocks or
challenges anything it was checked against during this recon.

## `robots.txt` is the load-bearing constraint here, not a WAF

This is the most important finding in this actor, and it directly
shaped the architecture. Poshmark's `robots.txt` is a single flat
`User-agent: *` group (no per-bot carve-out, so the multi-group parser
bug from the news-scraper actors in this portfolio doesn't apply here —
there's only one group). It contains:

```
Disallow: /search
```

This is a blanket rule with no exception for any specific crawler — it
applies to every user-agent, Claude included. Per this project's
policy of respecting explicit `Disallow` directives, **this actor does
not use `poshmark.com/search` at all**, even though it was the first,
most obvious endpoint prototyped during recon and returned rich,
correctly-paginated, correctly-filterable-by-keyword results.

Two things `robots.txt` does **not** disallow, and which turned out to
carry equivalent (in some ways richer) data:

```
poshmark.com/brand/<Brand-Name>        -- NOT disallowed
poshmark.com/category/<Dept-Category>  -- NOT disallowed
poshmark.com/listing/<slug>-<id>       -- NOT disallowed (only /listings plural, and
                                           specific sub-actions like /listing/*/like, are)
poshmark.com/closet/<username>         -- NOT disallowed (only /user and /users are)
```

`/search`, `/user`, `/users`, and `/listings` (plural) are disallowed;
the singular `/listing/<id>` detail path, `/brand/<name>`, `/category/
<slug>`, and `/closet/<username>` are all clean. This actor is built
entirely on the clean set.

## Confirming `/brand`/`/category` are real filters, not decoys

Before committing to this architecture, several guessed query-string
filters on the (unused) `/search` endpoint were tested and found to
**not actually filter** — `?brand=Nike`, `?seller_id=<id>`,
`?closet=<username>`, `?price=[50,100]` all returned unfiltered/
mixed-category results (confirmed by inspecting the `creator_username`/
`brand`/`price` of the returned items — none matched the requested
filter). This mattered doubly here since `/search` turned out to be
off-limits anyway, but it's a useful data point: don't trust an
accepted-without-error query param as evidence it did anything.

By contrast, `/brand/Nike` (its own dedicated path, not a query param on
`/search`) returned **100% Nike items** confirmed by checking `brand` on
every sampled item, and `/category/Women-Dresses?sort_by=price_asc`
returned **100% Dresses/Women items in genuinely ascending price order**
(confirmed against real sampled `price` values). Both use the identical
`gridData`/`more`/`next_max_id` pagination shape.

**Multi-word brand names must be space-encoded, not hyphenated** —
confirmed live: `/brand/lululemon athletica` (or its `%20`-encoded
equivalent) returns correct results; `/brand/lululemon-athletica`
(hyphenated) returns zero results. `src/main.py` URL-encodes the brand/
category value with `urllib.parse.quote(value, safe="-")` rather than
guessing a hyphenation scheme.

## Extraction: `window.__INITIAL_STATE__`

Poshmark is a server-rendered Vue 2 app. Every page type (`/brand/*`,
`/category/*`, `/listing/*`, `/closet/*`) embeds one `window.
__INITIAL_STATE__={...};` blob — the same family of pattern as Next.js's
`__NEXT_DATA__` or Nuxt's `__NUXT__`, just Vuex-flavored. It's 4-5MB of
single-line minified JSON per page, so a regex is fragile and a proper
balanced-brace walk (per `.ai/skills/balanced-brace-json.md`) is used
instead (`extract_initial_state()` in `src/extractor.py`).

The relevant top-level key differs by page type:
- `/brand/<name>` → `$_brand.gridData`
- `/category/<slug>` → `$_category.gridData`
- `/listing/<slug>-<id>` → `$_listing_details.listingDetails` +
  `$_listing_details.listerData` (the seller's basic profile, embedded
  right on the listing page — no second request needed)
- `/closet/<username>` → `$_closet.closetUserInfo.data` (profile +
  `aggregates`: followers, following, posts, items sold, 5-star rating
  counts, share/like/comment totals — all real numbers, confirmed
  against a real seller with 2,198 followers / 328 posts / "100+" items
  sold)

## Pagination

`gridData.more` carries `next_max_id` (an opaque `ENC_...`-prefixed
token, not a plain integer — passed back verbatim as the `max_id` query
param on the next request, never decoded or reconstructed) and
`is_next_max_id_present` (a clean boolean stop condition). Confirmed
live across 2 consecutive pages: 48 distinct new items each page, zero
overlap. `total` in the same object reports Poshmark's own match count,
which appears capped around 5,000 regardless of how many items actually
exist for a very broad brand/category — passed through as `_gridTotal`
on every record rather than treated as an exact number.

## Listing ID / slug behavior

The URL slug preceding a listing's ID is purely cosmetic — confirmed
live: `poshmark.com/listing/x-<real-id>` (a deliberately wrong slug)
returns 200 and redirects to the real canonical URL
(`poshmark.com/listing/Nike-Mens-Jacket-<id>`). This actor's `listing`
mode accepts a bare 24-character ID and constructs the URL as
`/listing/x-<id>`, with no need to know or guess the real slug.

## Not-found behavior (confirmed different per endpoint — don't assume one pattern)

- **Listing**: a genuinely nonexistent 24-char ID returns a real HTTP
  **404**.
- **Closet/seller**: a genuinely nonexistent username returns a real
  HTTP **404**.
- **Brand/category browse**: an invalid/nonexistent brand name returns
  a **soft 200** with `gridData.data: []` (empty list) and a
  synthesized-looking `brandData` object that just echoes the input
  string back as the display name — there is no way to distinguish "this
  brand name is wrong" from "this is a real, valid, currently-empty
  brand" from the response alone, so this actor treats an empty result
  set as a legitimate (if boring) outcome, not an error, consistent
  with how Poshmark itself treats it. `/category/<invalid-slug>`, by
  contrast, **does** return a real 404 — the two browse types are not
  symmetric here.

## Known limits

- `poshmark.com/search` (keyword search) is intentionally not
  implemented — `robots.txt` disallows it for every user-agent. Use
  `browse` mode's brand/category filters instead.
- `seller` mode returns the closet's profile and aggregate stats, not a
  paginated feed of the seller's own current listings — the closet
  page's own listings grid (`$_closet.postsByUser`) is `null` in the
  server-rendered state and is populated by a separate client-side
  AJAX call whose exact endpoint could not be located from the shipped
  JS bundles in the time available (no literal `axios`/`fetch` URL
  string was found in `closet.<hash>.js`; the real call is likely built
  via a shared, more heavily webpack-minified API-client module).
  Combining a seller's known listings via `browse` mode is not a
  substitute (Poshmark's brand/category browse does not support a
  seller-scoping filter — confirmed not working for `?seller_id=`,
  `?closet=`, `?user_id=`, `?creator_id=` query params, all silently
  ignored). This is a legitimate scope boundary, documented rather than
  faked.
- `sort_by`'s full valid value set isn't enumerable via error messages
  (Poshmark silently ignores an invalid value rather than rejecting it,
  unlike Civitai/Hugging Face's Zod-style validation elsewhere in this
  portfolio) — only empirically-confirmed-working values are exposed in
  the input schema.
- Total match counts (`_gridTotal`) reported by Poshmark for very broad
  brands/categories appear capped around 5,000 and should not be treated
  as an exact inventory count.

## Diff cadence

Quarterly smoke test recommended.
