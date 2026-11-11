# Shopee Seller Profile & Performance Scraper

Qualify a Shopee seller before you buy from them, resell for them, or approve
them as a supplier.

Give it usernames, shop IDs, shop URLs — or even **product URLs**, because the
shop ID is embedded in them. Returns the metrics a buyer actually judges on:
follower count, product count, rating breakdown, positive-rating share, chat
response rate, response time, shop age and Official Shop status.

11 country sites. No login, no cookies, no API key.

## What you get

```json
{
  "shopName": "Samsung Official Shop",
  "username": "samsung.official",
  "shopId": 52635036,
  "isOfficialShop": true,
  "followerCount": 3277836,
  "itemCount": 1788,
  "ratingStar": 4.895646,
  "ratingGood": 328451,
  "ratingBad": 1842,
  "positiveRatingPercent": 98.51,
  "responseRate": 100,
  "responseTimeMinutes": 1.7,
  "shopAgeDays": 3169,
  "location": "KOTA JAKARTA SELATAN"
}
```

Four figures are computed for you because nobody wants to do them by hand:

| Field | Derived from |
| --- | --- |
| `positiveRatingPercent` | good ÷ (good + normal + bad) |
| `responseTimeMinutes` | Shopee reports **seconds**; 102 s → 1.7 min |
| `shopAgeDays` | `ctime` Unix timestamp → days since |
| `ratingTotal` | the three counters summed |

## Four ways to identify a shop

| Input | Example | Resolved as |
| --- | --- | --- |
| Username | `samsung.official` | username |
| Numeric ID | `52635036` | shop ID |
| Shop URL | `shopee.co.id/shop/52635036` | shop ID |
| Storefront URL | `shopee.co.id/tokopedia` | username |
| **Product URL** | `shopee.co.id/product-i.1457622087.44421234179` | **shop ID `1457622087`** |

That last row matters: the **Shopee Flash Sale & Price Drop Monitor** in this
portfolio emits exactly those product URLs, so you can pipe its output straight
into this Actor to profile every seller running a flash sale.

## The trap this Actor is built around

Shopee answers **HTTP 200 with an error body** when a username does not exist:

```json
{"error": 2003013, "error_msg": "invalid_username"}
```

A client that checks only the status code records an empty shop and reports a
real brand as having no followers, no rating and no products. This Actor emits
`recordType: "NOT_FOUND"` and tells you which lookup failed.

This is not hypothetical — `xiaomi.official` returns exactly that on
`shopee.co.id`. A brand having an official store does **not** mean its username
matches its brand name. When a username fails, look the shop up by numeric ID.

## Reliability

`get_shop_detail` is the **only** Shopee shop endpoint that answers a plain
HTTP client. Measured 2026-09-20:

| Endpoint | Result |
| --- | --- |
| **`shop/get_shop_detail`** (username **and** shopid) | **200**, 50–55 fields ✅ |
| `shop/get_shop_base` | 200 `service_err` |
| `shop/get_shop_seo` | **403** anti-bot |
| `search/search_items` | **403** anti-bot |
| `item/get_ratings` | **403** anti-bot |

The 403s come from Shopee's load balancer with an identical body every time and
**no `Set-Cookie` is ever issued**, so there is no session warm-up that unlocks
them. When an endpoint is refused this Actor emits a `GATED` record naming it,
rather than an empty result — switch on `proxyConfiguration` with a residential
group, since the gate is IP-sensitive.

`_rawFieldCount` rides along on every record (50–55 observed). A sudden drop is
your early warning that Shopee changed the payload.

## Input example

```json
{
  "mode": "shop",
  "country": "ID",
  "shops": [
    "samsung.official",
    "614132689",
    "https://shopee.co.id/product-i.1457622087.44421234179"
  ],
  "proxyConfiguration": { "useApifyProxy": true }
}
```
