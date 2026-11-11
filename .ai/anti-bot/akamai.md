# Akamai Bot Manager

> **Akamai Bot Manager is comparatively forgiving — `curl_cffi chrome131` + homepage cookie warmup is usually sufficient.** The key insight is the warmup: hitting the API directly returns 403; visiting `/` first sets the `_abck` cookie and unlocks subsequent calls.

## Diagnosis

- Response sets cookie `_abck` (long opaque token, primary trust marker)
- Response sets cookie `bm_sz` (session vendor cookie)
- Response sets cookie `ak_bmsc` (bot management session)
- 403 with body containing `Pardon Our Interruption` or `_abck` invalidation message
- Akamai sensor data POST to `/_bm/_data` is the JS challenge — we don't replicate it; we sidestep with warmup

## Bypass: TLS impersonation + homepage warmup

### The canonical pattern (Tokopedia)

```python
from curl_cffi.requests import AsyncSession

class TokopediaClient:
    def __init__(self):
        self.session = AsyncSession(impersonate="chrome131", timeout=30)
        self._warm = False
    
    async def init_session(self):
        """Idempotent — bootstrap _abck cookie via homepage GET."""
        if self._warm:
            return
        r = await self.session.get("https://www.tokopedia.com/")
        if r.status_code != 200:
            raise RuntimeError(f"Akamai warmup failed: {r.status_code}")
        self._warm = True
    
    async def graphql(self, operation_name: str, variables: dict, query: str):
        await self.init_session()
        return await self.session.post(
            f"https://gql.tokopedia.com/graphql/{operation_name}",
            json=[{
                "operationName": operation_name,
                "variables": variables,
                "query": query,
            }],
            headers={
                "X-Source": "tokopedia-lite",
                "X-Tkpd-Lite-Service": "zeus",
                "X-Device": "desktop",
                "Referer": "https://www.tokopedia.com/",
            },
        )
```

### TLS profile is load-bearing

**Swap `curl_cffi` for `httpx` or `requests` and the same warmup fails with 403.** Akamai's JA3 check is the gate; warmup just sets the trust cookie *for* a recognized fingerprint.

```python
# Works
session = AsyncSession(impersonate="chrome131")

# Fails — instant 403 from gql.tokopedia.com
session = httpx.AsyncClient()
```

### `chrome131` over `chrome120`

`curl_cffi chrome120` is now on Akamai's stale-fingerprint list. `chrome131` is current as of May 2026. Re-evaluate quarterly.

## Header requirements

Beyond TLS, Akamai inspects:
- `User-Agent` — must match the impersonated Chrome version
- `Accept-Language` — must be present
- `sec-ch-ua-*` — automatically set by `impersonate=`
- Custom platform headers (Tokopedia adds `X-Source`, `X-Tkpd-Lite-Service`, `X-Device` — these are not anti-bot, they're API contract)

## Cookie discipline

| Cookie | Role | Lifespan |
| --- | --- | --- |
| `_abck` | Primary trust token, IP-bound | ~24h sliding |
| `bm_sz` | Session vendor cookie | Per-session |
| `ak_bmsc` | Bot management session | Per-session |
| `bm_mi` / `bm_sv` | Sometimes set | Per-deployment |

Cookie jar shared across all calls in a worker. Lose `_abck` → re-warmup.

## Common gotchas

### Gotcha 1: GraphQL `fields[]` whitelist with renamed keys (Tokopedia)

Tokopedia's `shopInfoByID` operation expects a `fields[]` whitelist using **renamed field names** that differ from the GraphQL schema:

```python
# WRONG — uses schema names
{"fields": ["stats", "info", "active_product"]}

# RIGHT — uses Apollo-cache-key names
{"fields": [
    "shopstats",         # not "stats"
    "is_open",
    "other-goldos",
    "closed_info",
    "create_info",
    "favorite",
    "status",
    "active_product",
    "other-shiploc",
]}
```

Discovery: inspect the Apollo cache key in browser DevTools — `shopInfoByID({input: {fields: [...]}})`. Wrong names return empty fields silently (not an error).

### Gotcha 2: Whitespace-sensitive GraphQL queries (Tokopedia)

`REVIEW_LIST_QUERY` is the **exact minified string from the frontend bundle**. Server validates a hash of the query. Reformatting / pretty-printing rejects the request.

```python
# Pass query as a single-line string captured from DevTools — DO NOT format it
REVIEW_LIST_QUERY = "query productReviewList($productID:String!,$page:Int!,...){productrevGetProductReviewList(productID:$productID,page:$page,...){..."
```

### Gotcha 3: Auth-gated query fields

Some fields (`shopNote`, `shopCore.tagLine`, `shopCore.description`, `shopScoreV3`, `shopReputation`, `productrevGetShopRating`) require logged-in session. Anon scraping returns empty.

**Workaround:** use auth-free alternatives:
- `customSEO.description` instead of `shopCore.description`
- `customSEO.bottomContent` instead of `shopCore.tagLine`

## Detection: distinguishing from Cloudflare

- `_abck` cookie present → Akamai
- `bm_sz` cookie present → Akamai
- `cf-ray` header → Cloudflare
- `_dd_s` cookie → DataDome

## What does NOT work

- ❌ `requests`/`httpx` defaults — instant 403
- ❌ Skipping warmup and hitting API directly
- ❌ Sharing `_abck` cookies across proxy IPs (cookie binds to IP)
- ❌ Replicating Akamai sensor_data POST (JS challenge, impractical)

## Verified production matrix

| Target | Library | Profile | Extra |
| --- | --- | --- | --- |
| Tokopedia GraphQL | curl_cffi | chrome131 | Homepage warmup, `X-Source: tokopedia-lite` |
| Tokopedia Production Pipeline | curl_cffi | chrome131 | Same — works in Beanstalk+Kafka workers |

## Caveats

- **Akamai's TLS allowlist is broader than DataDome's.** Most `curl_cffi` profiles work. Pick `chrome131` for safety.
- **Warmup is per-session, not per-call.** Don't re-GET `/` before every API call; just once at session start (and after a `_abck` invalidation).
- **No-captcha-solver policy applies here too.** If Akamai serves a captcha (rare), URL → errors.json, continue.
- **Akamai sensor_data IS replicable** if you really want — open-source projects (`akamai-spoofer`) exist. But warmup + TLS impersonation gets 99% of the way and is far less brittle.

## Where used

- Tokopedia Apify suite (8 actors)
- Tokopedia production pipeline (Beanstalk + Kafka)

## See also
- [`skills/cookie-warmup.md`](../skills/cookie-warmup.md)
- [`skills/tls-fingerprinting.md`](../skills/tls-fingerprinting.md)
- [`stacks/python-apify-actor.md`](../stacks/python-apify-actor.md)
