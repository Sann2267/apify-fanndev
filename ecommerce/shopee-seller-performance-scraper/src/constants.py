"""The one Shopee shop endpoint that answers, and what it actually contains.

Measured 2026-09-20, plain HTTP, no browser, no login.

**`/api/v4/shop/get_shop_detail` is open** — by `username` *and* by `shopid`.
It is the only shop endpoint that answers; `get_shop_base` returns
`service_err`, `get_shop_seo` returns the 403 anti-bot body, and the shop's own
HTML page renders zero product data.

Measured responses:

| Query | Result | Fields |
| --- | --- | --- |
| `username=shopee_id` | 200, 4 KB | **53** |
| `username=samsung.official` | 200, 4 KB | **55** |
| `username=tokopedia` | 200, 3 KB | 50 |
| `shopid=614132689` | 200 | full record |
| `username=xiaomi.official` | 200 | `{"error":2003013,"error_msg":"invalid_username"}` |

That last row is the trap worth knowing: a **200 with an error body**. A brand
having an official store does not mean its username matches the brand name, and
a client checking only the status code records an empty shop instead of a
lookup failure. Hence `NotFound` is raised on `error 2003013`.

Sample of what a real record carries (`samsung.official`):

```
shopid=52635036  rating_star=4.895646  follower_count=3277830
item_count=1788  response_rate=100  response_time=102
ctime=1516089696  is_official_shop=true  shop_location=…
rating_good / rating_normal / rating_bad
```

`response_time` is **seconds**, so 102 means "replies in about 1.7 minutes" —
returned both raw and as minutes. `ctime` is shop creation in Unix seconds,
which is where `shopAgeDays` comes from.

**Gated, for the record:** `search/search_items`, `item/get_ratings`,
`shop/get_shop_seo` — all HTTP 403 with `error 90309999` from the load
balancer, on every TLS profile, with no `Set-Cookie` ever issued.
"""

URL_SHOP_BY_USERNAME = "https://{domain}/api/v4/shop/get_shop_detail?username={username}"
URL_SHOP_BY_ID = "https://{domain}/api/v4/shop/get_shop_detail?shopid={shopid}"

DOMAINS = {
    "ID": "shopee.co.id",
    "SG": "shopee.sg",
    "MY": "shopee.com.my",
    "PH": "shopee.ph",
    "VN": "shopee.vn",
    "TH": "shopee.co.th",
    "BR": "shopee.com.br",
    "TW": "shopee.tw",
    "MX": "shopee.com.mx",
    "CO": "shopee.com.co",
    "CL": "shopee.cl",
}

ACCEPT_LANGUAGE = {
    "ID": "id-ID,id;q=0.9,en;q=0.8",
    "SG": "en-SG,en;q=0.9",
    "MY": "ms-MY,ms;q=0.9,en;q=0.8",
    "PH": "en-PH,en;q=0.9",
    "VN": "vi-VN,vi;q=0.9,en;q=0.8",
    "TH": "th-TH,th;q=0.9,en;q=0.8",
    "BR": "pt-BR,pt;q=0.9,en;q=0.8",
}

MAX_ATTEMPTS = 4
RETRY_DELAY_BASE = 1.5
MIN_BYTES = 200

TLS_LADDER = ("chrome124", "chrome120", "safari17_0", "firefox133")

BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "X-API-SOURCE": "pc",
    "X-Requested-With": "XMLHttpRequest",
}

MODES = ("shop", "reference")

GATE_ERROR = 90309999
INVALID_USERNAME_ERROR = 2003013
