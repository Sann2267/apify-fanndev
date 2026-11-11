# DataDome

> **DataDome's modern incarnation fingerprints JA3/JA4 aggressively and burns curl-impersonate Chrome profiles fast.** The winning move is **library diversity** — `primp` emits a Rust/rquest JA3 that DataDome hasn't blanket-fingerprinted yet. When `curl_cffi chrome131` returns 403, `primp` random profile silently passes.

## Diagnosis

- Response sets cookie `_dd_s` (with format `rum=N&id=<uuid>&created=<ts>&expire=<ts>`)
- Response sets cookie `datadome` (long opaque token)
- 403 body contains `geo.captcha-delivery.com` reference or DataDome captcha iframe
- 403 with `x-datadome-cid` response header
- 429 with retry-after header

## Bypass strategies

### Strategy 1: `primp` random profile pool — the killer move

`primp` is built on Rust's `rquest` (BoringSSL). Its JA3/JA4 fingerprint differs from `curl_cffi` (curl-impersonate BoringSSL) in subtle ways that bypass DataDome:

```python
import primp, random

DATADOME_WORKING_PROFILES = [
    # Chrome family — all work
    "chrome_100", "chrome_101", "chrome_104", "chrome_105", "chrome_106",
    "chrome_107", "chrome_108", "chrome_109", "chrome_114", "chrome_116",
    "chrome_117", "chrome_118", "chrome_119", "chrome_120", "chrome_123",
    "chrome_124", "chrome_126", "chrome_127", "chrome_128", "chrome_129",
    "chrome_130", "chrome_131", "chrome_132", "chrome_133",
    # Firefox family — also works
    "firefox_109", "firefox_117", "firefox_128", "firefox_133",
    # Safari
    "safari_15_3", "safari_15_5", "safari_15_6", "safari_16", "safari_16_5",
    "safari_17", "safari_17_2", "safari_17_4", "safari_17_5", "safari_18",
    # OkHttp (surprising — works at mobile endpoints)
    "okhttp_4_9", "okhttp_4_10",
]

DATADOME_BLOCKED = [
    "chrome_133_0",    # exact patch version blocked
    "safari_18_2",     # exact patch version blocked
    "okhttp_3_9",
    "okhttp_5",
]

profile = random.choice(DATADOME_WORKING_PROFILES)
client = primp.Client(impersonate=profile, verify=False)
r = client.get("https://www.reuters.com/business/finance/...")
```

### Strategy 2: 27-profile shuffle pool — WSJ / Barron's

For Dow Jones properties (DataDome stricter than typical), shuffle through profile pool per-request, not per-session:

```python
class DDShufflePool:
    def __init__(self, profiles=DATADOME_WORKING_PROFILES):
        self.pool = profiles.copy()
        self._idx = 0
        random.shuffle(self.pool)
    
    def next(self) -> str:
        if self._idx >= len(self.pool):
            random.shuffle(self.pool)
            self._idx = 0
        p = self.pool[self._idx]
        self._idx += 1
        return p

pool = DDShufflePool()

async def fetch_dj(url: str, retries: int = 5):
    for _ in range(retries):
        client = primp.Client(impersonate=pool.next(), verify=False)
        r = client.get(url)
        if r.status_code == 200:
            return r
    raise RuntimeError("All DD profiles exhausted")
```

### Strategy 3: `curl_cffi chrome131` for Airbnb (the exception)

Airbnb's DataDome deployment is older/lighter. `curl_cffi chrome131` works **if combined with**:
- Sticky session (don't rotate session_id mid-conversation)
- ≤ 1 req/sec/IP pace
- Header `x-niobe-short-circuited-product: true`
- Referer chain SRP → PDP (don't jump direct to PDP)

```python
session = AsyncSession(impersonate="chrome131")
await session.get("https://www.airbnb.com/s/Bali/homes")          # SRP
await asyncio.sleep(1.0)
await session.get(
    "https://www.airbnb.com/rooms/12345",                          # PDP
    headers={
        "x-niobe-short-circuited-product": "true",
        "referer": "https://www.airbnb.com/s/Bali/homes",
    },
)
```

### Strategy 4: `primp` for TripAdvisor (DataDome, not Akamai)

TripAdvisor migrated from Akamai to DataDome at some point. Old docs still mention Akamai — they're wrong. `primp` (any profile) passes; `curl_cffi chrome131` has burned JA3 here.

```python
client = primp.Client(impersonate="chrome_131", verify=False)
# 5x session_id rotation in Apify residential
```

## Cookie discipline

| Cookie | Role | Notes |
| --- | --- | --- |
| `_dd_s` | Session token | Required, IP-bound |
| `datadome` | Long-lived trust token | Don't share across IPs |

Keep both in a per-worker cookie jar. Don't reset between calls in the same logical conversation.

## Detection signal: distinguishing from Cloudflare

DataDome and Cloudflare can both return 403. Disambiguate:

- `_dd_s` cookie present → DataDome
- `cf-ray` header present → Cloudflare
- Body contains `captcha-delivery.com` → DataDome
- Body contains `_cf_chl_` → Cloudflare

## What does NOT work

- ❌ `curl_cffi` Chromium profiles against Reuters/Forbes/WSJ/Barron's (burned JA3)
- ❌ Solving DataDome captcha programmatically (high failure rate, expensive)
- ❌ Reusing `_dd_s` cookies across proxy IPs
- ❌ Overriding `Accept-Encoding` (breaks fingerprint)
- ❌ `requests` library (instant 403)

## Caveats

- **`primp` ≠ `curl_cffi`** — installing both can cause version conflicts. Pin one explicitly.
- **`primp` profile naming uses underscores:** `chrome_131`, not `chrome131`. Don't copy from `curl_cffi`.
- **`primp` doesn't ship `safari2601`** — that profile only exists in `scrapling`. If `primp` profiles all fail on PerimeterX-flavored DataDome (Bloomberg-like), escalate to `scrapling`.
- **Apify Residential proxy IS required** for WSJ/Barron's even with `primp`. DataDome blocks datacenter ASN upstream of fingerprinting.
- **DC IP usually works for Reuters/Forbes** — `primp` random profile from Apify datacenter is sufficient. Residential only for the hardest tier (DJ family).
- **DataDome rotates blocked profiles monthly.** Maintain a periodic smoke test against your full pool; remove ones that start returning 403.

## Verified production matrix

| Target | Library | Profile | Proxy |
| --- | --- | --- | --- |
| Reuters | primp | random from pool | Apify DC |
| Forbes | primp | random from pool | Apify DC |
| WSJ | primp | 27-profile shuffle | US Residential |
| Barron's | primp | 27-profile shuffle | US Residential |
| Airbnb | curl_cffi | chrome131 | Residential, sticky session, ≤1 req/sec |
| TripAdvisor | primp | rquest default | Residential, 5× rotation |

## See also
- [`skills/tls-fingerprinting.md`](../skills/tls-fingerprinting.md)
- [`skills/session-pool-rotation.md`](../skills/session-pool-rotation.md)
- [`anti-bot/cloudflare.md`](cloudflare.md) (when CF + DD stacked)
- [`anti-bot/perimeterx.md`](perimeterx.md) (when PX + DD layered)
