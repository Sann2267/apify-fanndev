---
name: session-pool-rotation
description: "Coordinate session (cookie jar), TLS profile, and proxy IP rotation at the correct cadence to stay unblocked. Use when warm-up cookies die on IP rotation, an IP's reputation degrades, or concurrent workers collide on shared sessions."
---

# Session Pool, Sticky Session, Profile Rotation

> **Three knobs determine whether you stay un-blocked: which session (cookie jar), which TLS profile, and which proxy IP.** Most bypass failures aren't about choosing the wrong one — they're about rotating them at the wrong cadence.

## Problem

- Rotating IP mid-session kills warm-up cookies (Akamai, PerimeterX cookie jars are IP-bound).
- Sticking on one IP forever burns its rep score (Skyscanner `_pxhd` flips to suspicious).
- Rotating TLS profile mid-rate-limit window doesn't help if proxy IP is already burned.
- Sharing sessions across workers causes CSRF mismatches.

## Solution: layered isolation — worker → session → proxy → profile

### Rule 1: one session per worker, never shared

```python
import asyncio
from curl_cffi.requests import AsyncSession

class WorkerContext:
    """Per-worker isolation. Created on worker spawn, destroyed on exit."""
    
    def __init__(self, worker_id: int, profile: str, proxy_url: str | None):
        self.worker_id = worker_id
        self.profile = profile
        self.proxy_url = proxy_url
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.warm = False
    
    async def warmup(self, url: str):
        """Visit homepage / specific entity URL to seed cookies."""
        r = await self.session.get(url)
        self.warm = True
        return r
    
    async def close(self):
        await self.session.close()
```

### Rule 2: sticky session per Apify run (no mid-conversation rotation)

```python
import secrets

def build_proxy_url(country: str = "US") -> str:
    """Apify Residential with sticky session_id.
    The session_id keeps the same egress IP for the duration of the run.
    """
    session_id = f"s{secrets.token_hex(8)}"           # Apify-compliant: ^[\w._~]+$
    return f"http://groups-RESIDENTIAL,country-{country},session-{session_id}:{APIFY_PROXY_PASSWORD}@proxy.apify.com:8000"
```

### Rule 3: rotate ON BLOCK only, never preemptively

Premature rotation defeats warm-up. The rule is: stay on one profile/IP until the WAF tells you to move.

```python
class RotationPool:
    def __init__(self, profiles: list[str], reset_url: str):
        self.profiles = profiles
        self.idx = 0
        self.reset_url = reset_url      # warm-up URL to re-seed cookies after rotation
        self._ctx: WorkerContext | None = None
    
    async def get_ctx(self) -> WorkerContext:
        if self._ctx is None:
            await self._spin_up_new_ctx()
        return self._ctx
    
    async def rotate(self):
        """Called on 403/429/block detection — burn current ctx, spin up next."""
        if self._ctx:
            await self._ctx.close()
        self.idx = (self.idx + 1) % len(self.profiles)
        await self._spin_up_new_ctx()
    
    async def _spin_up_new_ctx(self):
        profile = self.profiles[self.idx]
        proxy_url = build_proxy_url()              # fresh session_id each spin-up
        self._ctx = WorkerContext(self.idx, profile, proxy_url)
        await self._ctx.warmup(self.reset_url)
```

### Rule 4: TLS profile rotation has its own decision tree

Different profiles get different **trust budgets** from PerimeterX/Cloudflare at the same IP. When you exhaust one profile, the next may still have headroom.

```python
# Effective rotation ladder for PerimeterX (Bloomberg news-search, verified May 2026):
TLS_LADDER_PERIMETERX = [
    "chrome145",    # highest trust budget
    "chrome142",
    "chrome146",
    "edge101",
    "safari2601",
]
# Auto-blocked: chrome120, chrome131, chrome136, firefox133, firefox144

# Effective ladder for Zillow PerimeterX:
TLS_LADDER_ZILLOW = ["chrome136", "chrome142", "chrome146", "safari260"]
# Blocklisted: chrome120 (stale)
```

### Rule 5: re-instantiate the entire fetcher, not just rotate

When PerimeterX truly blocks, swapping just the TLS profile string isn't enough — the keep-alive connection and TCP socket are also fingerprinted. **Destroy and recreate**:

```python
async def hard_reset_fetcher(pool: RotationPool):
    """For PerimeterX hard limits: destroy keep-alive, fresh TCP, fresh cookies."""
    if pool._ctx:
        await pool._ctx.session.close()
        pool._ctx = None
    # Force GC of underlying curl handle / connection pool
    import gc; gc.collect()
    await pool._spin_up_new_ctx()
```

## Pattern: rate-limit window per IP

Each platform has empirical rate ceilings. Stay below them sticky, not bursty.

| Platform | Per-IP ceiling | Window |
| --- | --- | --- |
| Bluesky public.api | ~300 req/min | Continuous |
| Bluesky api.bsky.app | ~60 req/min | Continuous |
| Reddit OAuth installed | 60 req/min | Documented hard limit |
| Reddit `.json` public | ~10 req/min | Soft, varies by sub |
| Meta `/api/graphql/` (anon) | ~150–200 req/h per residential IP | Then 1000-req soft wall before login-required |
| Google Maps reviews | ~50–100 req/min | Then 429 soft-throttle |
| Twitter guest token | unlimited per token, but tokens themselves TTL 2–4h | per-token |
| TikTok mssdk-sg msToken | rotates per session, validate every ~100 req | per-session |
| Airbnb (DataDome) | ≤ 1 req/sec/IP | Continuous; pace strictly |
| Capterra (Cloudflare) | conservative — no published ceiling, observe 429 | per-IP |

### Pattern: bounded concurrency + jitter

```python
import asyncio, random

async def bounded_scrape(items, fetch_fn, max_concurrency=4, jitter_range=(0.3, 1.5)):
    sem = asyncio.Semaphore(max_concurrency)
    
    async def _one(item):
        async with sem:
            await asyncio.sleep(random.uniform(*jitter_range))
            return await fetch_fn(item)
    
    return await asyncio.gather(*(_one(i) for i in items), return_exceptions=True)
```

## Pattern: per-region/per-bbox session keying

For geospatial search (Zillow, Realtor) — keep one session per region, don't share across geographies (regional cookie state differs).

```python
class RegionalSessionPool:
    """One session per region/bbox key, rotates only on block within that region."""
    def __init__(self):
        self._sessions: dict[str, WorkerContext] = {}
    
    async def for_region(self, region_key: str) -> WorkerContext:
        if region_key not in self._sessions:
            ctx = WorkerContext(...)
            await ctx.warmup(f"https://www.zillow.com/{region_key}/")
            self._sessions[region_key] = ctx
        return self._sessions[region_key]
```

## Apify-specific: session_id naming compliance

Apify proxy session IDs must match regex `^[\w._~]+$`. Don't use UUIDs with dashes or special chars — they get rejected with cryptic 502 errors.

```python
# Good
session_id = "s" + secrets.token_hex(8)

# Bad — dashes break Apify
session_id = str(uuid.uuid4())   # contains '-'
```

## Caveats

- **Don't share `curl_cffi.AsyncSession` across asyncio tasks** — internal curl handle is not thread-safe. One session = one worker.
- **Cookie jar must be IP-stable.** Akamai `_abck`, PerimeterX `_pxhd`, DataDome `_dd_s` all bind to egress IP. Rotating IP mid-session triggers re-challenge.
- **HTTP/3 (`alt-svc`) upgrade silently breaks fingerprint.** Pin h2 by not letting the client see h3 advertisements (most impersonation libs default-disable h3 — verify).
- **Apify Residential session lifespan is ~10 min.** Beyond that, the same `session-XXX` ID gets a different egress IP. For long runs, plan to re-warmup periodically.
- **Datacenter ASN is fingerprinted upstream of TLS for many targets.** No amount of profile rotation saves you if the IP itself is on a known DC range — switch to residential.

## Where used

- Bloomberg news-search (5-layer rotation, IP warmup + dynamic session + fetcher reset + TLS rotation + tiered)
- Real-Estate Zillow (RegionalSessionPool keyed by bbox)
- Travel suite (sticky session per Apify run, 5× rotation max)
- Skyscanner (warmup `.net` then conductor; sticky session)
- StockX (profile rotation on 403/407/429/503)
- Zillow (chrome136 → 142 → 146 → safari260 ladder)
- All Meta scrapers (sticky session for warm-page tokens)

## See also
- [`skills/tls-fingerprinting.md`](../tls-fingerprinting/SKILL.md)
- [`skills/cookie-warmup.md`](../cookie-warmup/SKILL.md)
- [`anti-bot/perimeterx.md`](../../anti-bot/perimeterx.md)
