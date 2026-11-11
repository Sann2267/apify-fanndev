# Crawling method — Instagram merchant profiles

Recon date: **2026-09-01**. Every claim below was measured live, anonymously.

## Why this is not an "Instagram Shop" scraper

The original brief was an Instagram Shop product & catalog extractor. That
surface does not exist publicly any more, so building it was not possible.
The evidence:

| Probe | Result |
| --- | --- |
| `GET /nike/shop/`, `/zara/shop/` | 200 but **redirected to `/accounts/login/`** |
| `GET /explore/shop/` | same login redirect |
| `GET /nike/products/` | route ignored — renders the ordinary profile page |
| `GET /shop/` | just an account literally named `@shop`, not a shop directory |
| `web_profile_info` for nike, h&m, sephora (+2 more) | **zero** `shopping` / `catalog` / `merchant` / `storefront` keys |
| `product_type` on every post inspected | only ever `clips` or `igtv` — Instagram's **media** type, not a product |
| `edge_media_to_tagged_product` | does not exist; only `edge_media_to_tagged_user` (tagged people) |

This is consistent with Meta winding Instagram Shopping down. It is a
missing data surface, not a WAF problem — no fingerprint, header or token
work can recover data the platform no longer publishes. The one shop-shaped
thing left is behind a login, which is out of scope here.

What *is* public, and what this actor extracts, is the merchant's business
profile and **bio links** — for a merchant the bio link is the storefront
(Linktree, Shopee, Tokopedia, WhatsApp, own webstore).

Note for anyone extending this: `product_type` on a post looks like a
shopping field and is not one. Do not build product logic on it.

## Access and the three-strategy ladder

Instagram serves anonymous requests, but unevenly — which is why one source
is not enough.

| Strategy | Source | Gives | Reliability observed |
| --- | --- | --- | --- |
| **S1** | `GET /api/v1/users/web_profile_info/?username=` with `X-IG-App-ID` | Richest. **Only** source of business email/phone/contact-method, business address with lat/long, and recent posts | Intermittent — returned an empty payload for accounts whose page loaded fine in the same session |
| **S2** | Profile page HTML, `<script type="application/json">` blocks | Core profile, exact follower/following/post counts, bio links | **Worked for every account tested** (818–853 KB pages) |
| **S3** | `og:title` / `og:description` meta tags | Name and counts only, and counts are **rounded** (`680K`) | Always present |

Measured on `@cottonink` in one run: S2 gave `680168` followers, S3 gave
`680000`. S3 rows are tagged `_warning: counts_are_rounded_og_values` rather
than presenting a rounded number as exact.

In a 3-account end-to-end run, **2 of 3 accounts fell through to S2** — so
the fallback is the normal path, not an edge case, and business fields and
posts are genuinely often absent. The actor records which strategy produced
each row in `_source` so a consumer can tell.

The profile page is warmed before the API call: it sets the
`csrftoken`/`ig_did`/`datr` cookies the API expects, and it is the entity
page that must be warmed rather than the site root. Because the warm-up
response *is* S2's data source, the extra request is never wasted.

## Rate limiting

Anonymous access is throttled per IP, and Instagram signals it with a
**200 response that redirects to a login wall** rather than a clean 429 — so
block detection matches on the body, not just the status. During recon, a
burst of profile requests from one IP produced empty API payloads while
`nike` kept working, i.e. throttling is partial and account-specific rather
than an outright ban.

Consequences baked into the actor: profiles are fetched **sequentially with
a delay** (concurrency would trade a working run for a throttled one),
blocks trigger both a fingerprint rotation and a fresh proxy session, and
residential proxy is marked strongly recommended rather than optional.

## Known limits

- **No shop/product/catalog data** — see the top of this document.
- Business contact/address and recent posts come from S1 only, and S1 is the
  minority path in practice.
- `og` counts are rounded; such rows carry `_warning`.
- Private accounts expose no posts, and Instagram CDN media URLs are signed
  and expire — download promptly if the images matter.
- Only public profiles; nothing here reads a logged-in surface.
