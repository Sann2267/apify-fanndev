---
name: multi-strategy-fallback
description: "Design a tiered S1->S2->S3 fallback chain so a scraper degrades gracefully instead of dying on endpoint rotation, tagging each record with the tier that produced it. Use when building or hardening a production scraper that must survive 403s, schema drift, and WAF blocks."
---

# Multi-Strategy Fallback Chain (S1 → S2 → S3)

> **Production scrapers should never have a single point of failure.** When the primary endpoint goes 403, returns null, or rotates schema, you want a graceful fallback chain — not a P1 incident. This is the universal pattern: tier strategies by reliability + cost, tag every record with which tier emitted it.

## Problem

A scraper that hits one endpoint and dies on rotation:
- Breaks silently when the endpoint shape changes
- Has zero telemetry to diagnose why output is empty
- Can't survive temporary WAF blocks
- Forces ops to redeploy on every server-side change

## Solution: cascade strategies, tag results, fail loud only at the end

### The pattern

```python
async def fetch_user(username: str) -> dict:
    """
    S1 = best data quality, may rate-limit
    S2 = wider coverage, less rich
    S3 = degraded but always-on
    """
    # S1: primary
    try:
        data = await _s1_primary(username)
        if data:
            return {**data, "_source": "S1-graphql"}
    except (StaleDocIdError, RateLimited, BlockedByWAF):
        pass
    
    # S2: fallback
    try:
        data = await _s2_fallback(username)
        if data:
            return {**data, "_source": "S2-html-apollo"}
    except (BlockedByWAF, NotFound):
        pass
    
    # S3: degraded but always works
    try:
        data = await _s3_minimal(username)
        if data:
            return {**data, "_source": "S3-embed"}
    except NotFound:
        pass
    
    # Fail loud only after all strategies exhausted
    return {
        "_input": username,
        "_source": "none",
        "_error": "all_strategies_failed",
        "_attempts": {"S1": "blocked", "S2": "blocked", "S3": "not_found"},
    }
```

### Critical rule: `_source` envelope tag

**Every emitted record MUST carry `_source`** indicating which strategy produced it. This is the difference between a debuggable scraper and a black box.

```python
{
    "_input": "bsky.app",
    "_source": "S1-xrpc",         # or "S2-html-apollo" or "S3-embed"
    "_scrapedAt": "2026-05-17T03:14:00Z",
    # ...rest of raw data
}
```

When the dataset suddenly has 80% `_source: "S3-embed"` rows, ops knows S1+S2 are failing and can investigate without you adding logging.

## Tiered strategy taxonomy by site type

| Site type | S1 (primary) | S2 (fallback) | S3 (degraded) |
| --- | --- | --- | --- |
| Public XRPC (Bluesky) | XRPC method call | — | — |
| News (NYT/WSJ/Bloomberg) | JSON-LD | `__NEXT_DATA__` | Apollo state / `og:` meta |
| News (Reuters/Forbes/AP) | DataDome-protected article HTML | RSS feed | Wire-service syndicated copy on partner site |
| Meta (IG/FB/Threads) | warm-page + doc_id GraphQL | SSR HTML JSON walk | Embed page (`/p/.../embed/`) |
| Twitter/X | Guest-token GraphQL | Syndication (`cdn.syndication.twimg.com`) | — |
| TikTok | Web API signed (X-Bogus + X-Gnarly) | SSR HTML universal data | Embed page (FRONTITY) |
| YouTube | innertube POST | HTML watch-page (`ytInitialPlayerResponse`) | RSS feed (channel-id only) |
| Reddit | Installed-app OAuth (60 rpm) | `www.reddit.com/.json` (10 rpm) | `old.reddit.com/.json` |
| Tokopedia | GraphQL `gql.tokopedia.com` | SSR HTML Apollo cache | — |
| Shopee | SEO render (Googlebot UA) | Browser UA SSR | `/api/v4/shop/get_shop_detail` (token-free) |
| StockX | Apollo persisted-query GraphQL | HTML search backdoor (Apollo cache) | — |
| Alibaba | SSR HTML balanced-brace | RFQ subdomain (more permissive) | MTOP signed (review-list only) |
| Real-Estate (Realtor) | Googlebot SSR | `GOOGLE_SERP` verified Googlebot proxy | — |
| Real-Estate (Zillow) | `PUT /async-create-search-page-state` | `GET /search/GetSearchPageState.htm` | `PUT /graphql/` |

## When fallback chains EARN their keep

- **Server-side schema rotation** — S1 broken, S2 still works = zero downtime.
- **Soft block (region/IP-specific)** — S1 from Apify EU residential fails, S2 (different code path) survives.
- **Auth-walled features lit up at random** — Meta toggles per-rollout; fallback covers.
- **Cost optimization** — S1 may be expensive (residential proxy + heavy GQL), S3 may be cheap (RSS). Run S3 first if data quality is acceptable.

## When fallback chains FAIL by design

Sometimes there's no S2/S3:
- Bluesky public-friendly → no need
- Mastodon per-instance API → fallback would be another instance entirely
- Tumblr v2 public API → only one path
- Twitch internal GQL → only one path

**Document this explicitly** in the actor README so reviewers know it's intentional, not negligent.

## Pattern: per-strategy classification before retry

```python
def classify_response(r) -> str:
    """Returns 'ok', 'retry', 'rotate', 'kasada', 'not_found'."""
    if r.status_code == 200:
        body_head = r.content[:8192]
        if any(m in body_head for m in BLOCK_MARKERS):
            return "rotate"
        if r.json() == {"data": []}:        # platform-specific empty marker
            return "rotate"
        return "ok"
    if r.status_code == 404:
        return "not_found"
    if r.status_code == 429 and r.headers.get("x-kasada-tier"):
        return "kasada"
    if r.status_code in (403, 429, 503):
        return "rotate"
    if r.status_code in (500, 502, 504):
        return "retry"
    return "retry"


# Driver
verdict = classify_response(r)
match verdict:
    case "ok":         return r.json()
    case "not_found":  raise NotFound
    case "rotate":     rotate_profile_and_retry()
    case "kasada":     raise KasadaBlocked        # circuit breaker → fail loud
    case "retry":      backoff_and_retry()
```

## Caveats

- **Don't silently swap shapes.** If S1 returns `{rest_id, screen_name, followers_count}` and S2 returns `{user_id, handle, follower_count}`, your downstream pipeline breaks. Either normalize at extraction time OR accept different shapes per `_source` and let consumers branch.
- **Beware infinite loops in rotation.** If every profile in your rotation pool returns "rotate", you'll spin forever. Cap retries (typically 5–8) and fail loud after.
- **S3 is for graceful degradation, not normal operation.** If >30% of your dataset is `_source: "S3"`, S1 and S2 are broken — investigate and fix.
- **Tag every record, including errors.** `_source: "none"` + `_error: "..."` is still a record. Don't drop failures silently.

## Where used

- Reddit suite (S1-oauth → S2-jsonpublic → S3-oldjson)
- Bluesky / Substack / Medium / FB / Threads (S1 / S2 envelope)
- Twitter (S1-graphql / S2-syndication)
- TikTok posts (S1 SSR → S2 signed API → S3 embed)
- Shopee (SEO Googlebot → Browser UA → shop_detail API)
- Online News smart-news-loader (httpx → curl_cffi → primp → scrapling → trafilatura)
- Bloomberg article (NEXT_DATA → PRELOADED_STATE → LD-JSON → og:meta)

## See also
- [`conventions/dataset-envelope.md`](../../conventions/dataset-envelope.md)
- [`conventions/error-handling.md`](../../conventions/error-handling.md)
