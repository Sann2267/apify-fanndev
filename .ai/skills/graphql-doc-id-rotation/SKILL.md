---
name: graphql-doc-id-rotation
description: "Auto-discover and refresh persisted-query hashes (doc_id, queryId, sha256Hash) from the live frontend bundle so a GraphQL scraper survives the vendor's fortnightly rotation. Use when GraphQL calls suddenly return 400/404 'persisted query not found', or when building a Meta/Twitter/Airbnb/StockX GraphQL scraper."
---

# GraphQL `doc_id` / `queryId` Discovery & Rotation

> **Modern GraphQL APIs (Meta, Twitter, Airbnb, StockX, Threads) ship persisted query hashes/IDs that change every 2–4 weeks.** Hardcoding them in your scraper guarantees a P1 incident every fortnight. This pattern auto-discovers them from the live frontend bundle and refreshes on first 400/404.

## Problem

Persisted-query GraphQL servers reject unknown queries to prevent abuse:

- Meta: `doc_id` numeric (15–18 digits)
- Twitter/X: `queryId` ~20-char base64
- Airbnb: SHA-256 of operation
- StockX: SHA-256 in extensions.persistedQuery.sha256Hash

When the value goes stale, you get `PersistedQueryNotFound` (Airbnb), `400 execution error` (Meta), `404` (Twitter), or silent empty data. Hardcoded values rot ~biweekly.

## Solution: trust-but-verify cache + auto-refresh

### Step 1: define the snapshot (last-known-good)

```python
# Volatile! Refresh hash check weekly. Last verified: 2026-05-14.
DOC_ID_SNAPSHOT = {
    # Instagram
    "PolarisProfilePostsQuery":    "9310670392322965",
    "PolarisPostRootQuery":        "8845758582119845",
    "PolarisReelsTabContentQuery": "25981206651899035",
    # IG post detail via web_info shape (preferred — anon-friendly)
    "PolarisPostsByMediaIdQuery":  "6866604656750199",
    
    # Facebook
    "ProfileCometHeaderQuery":     "25964356583202181",
    "PageTimelineFeedQuery":       "<numeric>",
    
    # Threads (Barcelona)
    "BarcelonaProfileQuery":                       "23996318473300828",
    "BarcelonaProfileThreadsTabRefetchableQuery":  "6232751443445612",
    "BarcelonaPostPageQuery":                      "5587632691339264",
}

# Twitter — queryIds change roughly weekly
QUERY_ID_SNAPSHOT = {
    "UserByScreenName":     "IGgvgiOx4QZndDHuD3x9TQ",
    "UserByRestId":         "VQfQ9wwYdk6j_u2O4vt64Q",
    "UserTweets":           "36rb3Xj3iJ64Q-9wKDjCcQ",
    "TweetResultByRestId":  "2Acdg-VztGlHX7MjX67Ysw",
}
```

### Step 2: harvest from live bundle (programmatic)

#### Meta (Threads / FB / IG)

Pull the route bundle and grep for `doc_id`:

```python
import re

async def harvest_meta_doc_ids(session, route_js_url: str) -> dict[str, str]:
    """
    Threads: https://www.threads.com/static/js/<route>.js
    IG/FB:   similar paths visible in network tab of warmup load
    """
    r = await session.get(route_js_url)
    # Pattern: ...{"id":"<digits>","name":"BarcelonaProfileQuery"...
    # Reversed: ...name:"BarcelonaProfileQuery","id":"<digits>"...
    discovered = {}
    for m in re.finditer(
        r'"(\w+Query)","id":"(\d{14,18})"',
        r.text,
    ):
        discovered[m.group(1)] = m.group(2)
    for m in re.finditer(
        r'"id":"(\d{14,18})","name":"(\w+Query)"',
        r.text,
    ):
        discovered[m.group(2)] = m.group(1)
    return discovered
```

#### Twitter/X

Twitter ships ~158 ops per bundle. The bundle URL is in `main.<hash>.js` referenced from the homepage HTML.

```python
async def harvest_twitter_queries(session) -> dict:
    """Returns {operation_name: {queryId, features, fieldToggles, operationType}}"""
    r = await session.get("https://x.com/home", impersonate="chrome131")
    main_js_url = re.search(
        r'(https://abs\.twimg\.com/responsive-web/client-web/main\.[a-f0-9]+\.js)',
        r.text,
    ).group(1)
    
    bundle = (await session.get(main_js_url)).text
    
    ops = {}
    for m in re.finditer(
        r'queryId:"([A-Za-z0-9_-]+)",'
        r'operationName:"(\w+)",'
        r'operationType:"(\w+)",'
        r'metadata:\{featureSwitches:\[([^\]]*)\],fieldToggles:\[([^\]]*)\]\}',
        bundle,
    ):
        qid, name, op_type, fs_raw, ft_raw = m.groups()
        ops[name] = {
            "queryId":      qid,
            "features":     [s.strip('"') for s in re.findall(r'"([^"]+)"', fs_raw)],
            "fieldToggles": [s.strip('"') for s in re.findall(r'"([^"]+)"', ft_raw)],
            "operationType": op_type,
        }
    
    # Also harvest bearer from the bundle
    bearer = re.search(r'AAAAAAAAAAAAAAAAAAAAA[A-Za-z0-9%]{60,}', bundle).group(0)
    return ops, bearer
```

#### Airbnb (SHA-256 operation hash)

Airbnb ships hashes in `__NEXT_DATA__` chunk references. The trick is to grep the right webpack chunk (operation name shows up adjacent to its hash):

```python
async def harvest_airbnb_op_hash(session, operation_name: str) -> str | None:
    """E.g. operation_name = 'StaysSearch' or 'StaysPdpSections'"""
    # 1. Fetch a search page to find chunk URLs in __NEXT_DATA__
    r = await session.get("https://www.airbnb.com/s/Bali/homes", impersonate="chrome131")
    chunks = re.findall(r'/_next/static/chunks/(\d+-[a-f0-9]+\.js)', r.text)
    
    for chunk in chunks:
        js = (await session.get(f"https://www.airbnb.com/_next/static/chunks/{chunk}")).text
        # Pattern: ...operationName:"StaysSearch",operationId:"<sha256>"...
        m = re.search(
            rf'operationName:"{operation_name}",operationId:"([a-f0-9]{{64}})"',
            js,
        )
        if m:
            return m.group(1)
    return None
```

#### StockX (Apollo persisted query SHA-256)

StockX's `GetMarketData` hash:

```
589955a4e8c0e714c09999d857089ebc54569d0fe216e5e8538cade33572eb16
```

Harvested from the Apollo Iron client bundle in the same way as Airbnb. Rotate when StockX deploys a major schema change.

### Step 3: trust-but-verify wrapper

```python
class DocIdCache:
    """Persistent cache with TTL + invalidate-on-fail semantics."""
    
    def __init__(self, kv_store=None, ttl_seconds=24 * 3600):
        self.snapshot = DOC_ID_SNAPSHOT.copy()
        self.kv = kv_store  # Apify KeyValueStore optional
        self.ttl = ttl_seconds
    
    async def get(self, name: str) -> str | None:
        # Try cache (Apify KV store) first
        if self.kv:
            cached = await self.kv.get_value(f"doc_id:{name}")
            if cached and cached["expires"] > time.time():
                return cached["value"]
        return self.snapshot.get(name)
    
    async def invalidate(self, name: str):
        """Call when a request with this doc_id returned 400/404."""
        self.snapshot.pop(name, None)
        if self.kv:
            await self.kv.set_value(f"doc_id:{name}", None)
    
    async def refresh(self, harvest_fn):
        """harvest_fn returns dict[name] = value. Merge into snapshot."""
        discovered = await harvest_fn()
        self.snapshot.update(discovered)
        if self.kv:
            for name, value in discovered.items():
                await self.kv.set_value(
                    f"doc_id:{name}",
                    {"value": value, "expires": time.time() + self.ttl},
                )
```

### Step 4: call site retries on stale ID

```python
async def graphql_call(name: str, variables: dict, cache: DocIdCache, harvest_fn):
    doc_id = await cache.get(name)
    if not doc_id:
        await cache.refresh(harvest_fn)
        doc_id = await cache.get(name)
        if not doc_id:
            raise RuntimeError(f"Cannot resolve doc_id for {name}")
    
    resp = await _post_graphql(doc_id, variables)
    
    if resp.status_code in (400, 404) or "execution error" in resp.text:
        # Stale — invalidate and retry once
        await cache.invalidate(name)
        await cache.refresh(harvest_fn)
        doc_id = await cache.get(name)
        resp = await _post_graphql(doc_id, variables)
    
    return resp.json()
```

## Healthcheck cadence

| Platform | Cadence | What to check |
| --- | --- | --- |
| Meta (IG/FB/Threads) | Weekly | Smoke test 1 doc_id per service, alarm on shape change |
| Twitter | Daily | Bundle hash diff (`main.<hash>.js` URL changes → new harvest) |
| Airbnb | Bi-weekly | First `PersistedQueryNotFound` triggers chunk re-harvest |
| StockX | Quarterly | Apollo client major version bumps tied to UI redesigns |

## Caveats

- **Don't share doc_id snapshots between Threads/IG/FB** — same operation names exist on different platforms with different IDs.
- **Threads `BarcelonaProfileQuery` returns `execution error`** even when the doc_id is fresh — Meta is gating it heavily. Prefer SSR HTML path (S1-html) over GraphQL (S2) for Threads profile.
- **Variables shape matters as much as doc_id.** A fresh doc_id with wrong variable types returns `noncoercible_variable_value`. Inspect the variable schema via the bundle (look for `__typename: "GraphQLVariableType"` or similar) or via DevTools capture.
- **`__a=1`, `__hs`, `__rev`, `__spin_*` form fields must accompany** the doc_id in Meta POST — see [`skills/warm-page-token-harvest.md`](../warm-page-token-harvest/SKILL.md).
- **Twitter's feature toggles change weekly.** A new feature added without you knowing returns 400 "missing feature". Always re-harvest features from the bundle, never hardcode the list.

## Where used

- Instagram suite (PolarisPostsByMediaIdQuery = `6866604656750199` validated for post-detail)
- Facebook suite (ProfileCometHeaderQuery = `25964356583202181` for NASA page)
- Threads suite (Barcelona triple — Profile / ProfileThreadsTab / PostPage)
- Twitter suite (158 ops harvested, FALSE_FORCED_FEATURES list, syndication S2 fallback)
- Airbnb scraper (StaysSearch + StaysPdpSections SHA-256 with auto-refresh)
- StockX scraper (GetMarketData persisted hash)

## See also
- [`skills/warm-page-token-harvest.md`](../warm-page-token-harvest/SKILL.md)
- [`skills/multi-strategy-fallback.md`](../multi-strategy-fallback/SKILL.md)
- [`playbooks/reverse-engineer-internal-api.md`](../../playbooks/reverse-engineer-internal-api.md)
