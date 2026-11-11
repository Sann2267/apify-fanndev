# Kasada / KPSDK

> **Kasada is unique among modern WAFs: it returns HTTP 429 *by design* (not 403) and the bypass is a User-Agent trick, not a TLS impersonation.** Realtor.com is the canonical example — `User-Agent: Googlebot/2.1` makes the same residential IP that just 429'd serve a clean 200 with `__bot=true` cookie.

## Diagnosis

- Response status `429` (not 403)
- Response sets cookie `KP_UIDz` or `KP_RTID`
- Header `x-kasada-tier: <N>` may be present
- Body is empty or tiny challenge stub
- Affects ALL request paths including XHR/api endpoints

**Crucial signal:** if a normal Chrome UA gets sequential 429s across 11+ residential IPs, AND a Googlebot UA on the same IP gets 200, that's Kasada specifically.

## Bypass: Googlebot UA trick (the actual bypass)

Kasada respects Googlebot for SEO indexing. The Googlebot UA sets a server-side `__bot=true` allowlist marker:

```python
GOOGLEBOT_UA = "Googlebot/2.1 (+http://www.google.com/bot.html)"

session = AsyncSession(impersonate="chrome131")  # TLS profile doesn't matter much
session.headers["User-Agent"] = GOOGLEBOT_UA

r = await session.get("https://www.realtor.com/realestateandhomes-search/Austin_TX/")
# 200 OK with full SSR HTML
```

The TLS profile is **not** what bypasses Kasada — the UA is. You can use almost any reasonable TLS impersonation and the trick still works.

## Bypass: verified Googlebot proxy egress

For production reliability (residential UA spoofing can still get caught if IP doesn't match Google's ASN), use Apify's `GOOGLE_SERP` proxy group which routes via verified Googlebot egress:

```python
proxy_url = await Actor.create_proxy_configuration(
    groups=["GOOGLE_SERP"],
).new_url()

session = AsyncSession(
    impersonate="chrome131",
    proxies={"http": proxy_url, "https": proxy_url},
)
session.headers["User-Agent"] = GOOGLEBOT_UA
```

## Avoid the API path

Realtor's API (`/api/v1/hulk_main_srp`) is Kasada-protected and **specifically returns 404 to Googlebot** (Google doesn't index APIs). So scraping the API path with the Googlebot trick fails.

**Solution:** scrape SSR HTML (`/realestateandhomes-search/<slug>/pg-<N>`) which IS Googlebot-indexed and returns full listings. Then parse `__NEXT_DATA__`.

```python
# WRONG — Kasada returns 404 for Googlebot on internal API
api_url = "https://www.realtor.com/api/v1/hulk_main_srp"

# RIGHT — SSR HTML, indexed by Google, served happily
ssr_url = "https://www.realtor.com/realestateandhomes-search/Austin_TX/pg-1"
```

## Circuit breaker pattern

When Kasada IS blocking even with Googlebot trick (rare but happens), don't silently degrade — fail loud:

```python
class KasadaBlocked(Exception):
    """Raised when even Googlebot trick fails. Don't retry — investigate."""


def classify_realtor_response(r) -> str:
    if r.status_code == 200:
        return "ok"
    if r.status_code == 429:
        return "kasada"        # explicit signal
    if r.status_code == 404:
        return "not_found"     # legitimate (URL doesn't exist) OR Googlebot-on-API
    return "retry"


verdict = classify_realtor_response(r)
if verdict == "kasada":
    raise KasadaBlocked(f"Kasada blocked Googlebot UA on {r.request.url}")
```

## SSR trade-off (Realtor specific)

Realtor's SSR HTML has full listings + basic detail, but **NOT** multi-year priceHistory or taxHistory — those are XHR-loaded in the client-rendered version. Trade-off:

| Approach | priceHistory / taxHistory | WAF risk |
| --- | --- | --- |
| Googlebot SSR | ❌ empty (`[]`) | 🟢 Reliable |
| Client-render via Camoufox | ✅ full | 🔴 High effort, expensive |

**Decision rule:** Most use-cases (lead-gen, AVM training, listing intelligence) don't need priceHistory/taxHistory. Emit schema-stable `[]` and document the limit, rather than burning compute on Camoufox.

## Specific Realtor headers (production verified)

```python
HEADERS_REALTOR_SSR = {
    "User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
```

## What does NOT work

- ❌ Chrome UA spoofing from residential Apify proxy (11 sequential 429s observed)
- ❌ Chrome UA from datacenter (fully fingerprinted)
- ❌ Solving Kasada KP_RTID challenge programmatically (server-side validation, no public bypass)
- ❌ Hitting the API endpoint with Googlebot UA (returns 404 by design)
- ❌ Adding `KP_UIDz` cookie manually (server validates ledger)
- ❌ Other crawler UAs (Bingbot/Slurp/DuckDuckBot) — Realtor only allowlists Google

## Verified production matrix

| Target | Strategy | Proxy | Status |
| --- | --- | --- | --- |
| Realtor.com SSR | Googlebot UA + curl_cffi | Apify Residential (or GOOGLE_SERP) | ✅ 5 listings in 6 seconds, zero failures |
| Realtor.com API | — | — | ❌ Returns 404 to Googlebot |
| Realtor.com Camoufox | Browser interception | Residential | Possible but expensive — last resort |

## Caveats

- **The trick can stop working at any time.** Realtor could de-allowlist Googlebot UA tomorrow. Maintain smoke tests.
- **Other Kasada-protected sites may not respect Googlebot.** Some Kasada deployments treat all UAs equally — Realtor's `__bot=true` allowlist is implementation-specific. Test before assuming.
- **Don't combine with `chrome120` impersonation** that contradicts Googlebot's actual TLS signature. Either stay with `chrome131+` (reasonable for "modern Googlebot crawler") or use HTTP/1.1 (Googlebot historically uses h1).
- **Apify `GOOGLE_SERP` proxy group has limited bandwidth** — fine for ~1000 req/hour but not bulk. Mix with regular residential for higher throughput.

## Where used

- Realtor.com all-in-one scraper (xtracto/realtor-all-in-one-scraper)
- Same residential pool that returns 11 sequential 429s with Chrome UA returns 200 with Googlebot UA

## See also
- [`skills/tls-fingerprinting.md`](../skills/tls-fingerprinting.md)
- [`skills/multi-strategy-fallback.md`](../skills/multi-strategy-fallback.md)
- [`lessons-learned.md`](../lessons-learned.md) (Kasada Googlebot discovery story)
