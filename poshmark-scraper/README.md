# Poshmark Scraper

Browse Poshmark listings by brand or category, extract full listing details, and pull seller/closet profiles — no account or API key needed.

## Why use this actor

- Browse any brand or category with sorting (newest, price, most liked) and automatic pagination
- Full listing detail includes the seller's basic profile embedded — no second request needed
- Seller/closet profiles include real aggregate stats: followers, following, total posts, items sold, 5-star rating counts
- No account, login, or API key required
- Respects Poshmark's own `robots.txt` — built entirely on paths it doesn't disallow (see Known limits for what that means in practice)

## How it works

Pick a `mode`:
1. **`browse`** — list items for a brand or category, sorted and paginated.
2. **`listing`** — fetch full detail for one or more specific listing IDs/URLs.
3. **`seller`** — fetch a seller's closet profile and stats by username.

## Input

**Browse by brand:**
```json
{
  "mode": "browse",
  "browseBy": "brand",
  "value": "Nike",
  "sortBy": "price_asc",
  "maxItems": 100
}
```

**Browse by category:**
```json
{
  "mode": "browse",
  "browseBy": "category",
  "value": "Women-Dresses",
  "maxItems": 100
}
```

**Listing detail:**
```json
{
  "mode": "listing",
  "listingIds": ["6a8e29a7571a7e204b947d4f"]
}
```

**Seller profile:**
```json
{
  "mode": "seller",
  "username": "shophopeful"
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"browse"` (default), `"listing"`, or `"seller"`. |
| `browseBy` | string | `browse` mode — `"brand"` or `"category"`. |
| `value` | string | `browse` mode — a brand name (e.g. `"Nike"`, `"lululemon athletica"`) or a `Department-Category` slug (e.g. `"Women-Dresses"`, `"Men-Shoes"`). |
| `sortBy` | string | `browse` mode — `added_desc` (default), `price_asc`, `price_desc`, `like_count`, or `relevance`. |
| `maxItems` | integer | `browse` mode — max listings to return, pagination followed automatically. Default 100. |
| `listingId` / `listingIds` | string / array | `listing` mode — a listing's 24-character ID or full URL. |
| `username` / `usernames` | string / array | `seller` mode. |
| `maxConcurrency` | integer | `listing`/`seller` mode — how many to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Browse / listing mode** — one record per listing (truncated for readability):
```json
{
  "_input": "brand:Nike",
  "_source": "S1-html",
  "id": "6a8e29a7571a7e204b947d4f",
  "title": "Nike Mens Jacket",
  "price": 25,
  "original_price": 150,
  "brand": "Nike",
  "size": "XXL",
  "condition": "...",
  "creator_username": "clarissajohn606",
  "like_count": 3,
  "pictures": [ { "url": "https://...jpg" } ]
}
```

**Seller mode:**
```json
{
  "_input": "clarissajohn606",
  "_source": "S1-html",
  "username": "clarissajohn606",
  "full_name": "Clarissa Johnson",
  "profile_v2": { "description": "Always Open to offers!!", "city": "Charleston", "state": "IL" },
  "aggregates": {
    "followers": 2198,
    "following": 63,
    "posts": 328,
    "items_sold_display": "100+",
    "seller_5_star_rating_comment_count": 12
  }
}
```

A record with `_error` instead means that lookup couldn't complete (e.g. `"_error": "listing_not_found"` or `"_error": "seller_not_found"`).

## Known limits

- **Keyword search is not available.** Poshmark's `robots.txt` disallows `/search` for every crawler, with no exceptions — this actor honors that and does not implement keyword search. Use `browse` mode's brand/category filters instead, which are not disallowed and were confirmed to filter correctly (unlike several query-string filters tried on `/search`, which silently returned unfiltered results).
- **`seller` mode returns profile + stats, not a paginated feed of that seller's current listings.** The closet page's own listings grid loads via a client-side call whose exact endpoint wasn't found during development — this is a documented scope boundary, not a bug.
- **Total match counts for very broad brands/categories are capped around 5,000** by Poshmark itself — not an exact inventory count.
