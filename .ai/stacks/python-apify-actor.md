# Stack: Python Apify Actor (Canonical)

> **Copy-paste boilerplate for a new Apify Python actor.** Every production scraper in the portfolio uses this skeleton with minor tweaks. Self-contained per actor (each gets its own copy of shared code) — no monorepo coupling.

## Project layout

```
actor-{platform}-{purpose}/
├── .actor/
│   ├── actor.json
│   ├── input_schema.json
│   └── Dockerfile
├── src/
│   ├── __init__.py
│   ├── __main__.py            # entry: python -m src
│   ├── main.py                # async main() — Actor lifecycle
│   ├── client.py              # HTTP client wrapper + warmup + retry
│   ├── extractor.py           # parse upstream payload → records
│   ├── models.py              # Pydantic output models (optional but recommended)
│   ├── constants.py           # endpoints, headers, profiles
│   └── shared/                # if vendored from other actors
│       └── balanced_brace.py  # e.g. reusable utilities
├── requirements.txt
├── README.md
├── .gitignore
└── .dockerignore
```

**Self-contained rule:** each actor folder must be buildable on its own. Apify build context = single folder. If you have shared utilities, vendor them (copy file) — don't symlink or rely on a parent project.

## `requirements.txt` (canonical)

```
apify>=2.0.0,<3.0.0
curl_cffi>=0.15.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
selectolax>=0.4.0
pydantic>=2.9.0,<2.10.0          # pinned for crawlee 0.6.12 compat
httpx[http2]>=0.27.0              # for low-risk HTTP/2 endpoints
jmespath>=1.0.0
```

Optional add-ons (only when needed):
```
primp>=0.6.0                      # for DataDome
scrapling[fetchers]>=0.4.0        # for PerimeterX-Bloomberg
trafilatura>=2.0.0                # for article body enrichment
dateparser>=1.2.0                 # for "3 weeks ago" style dates
srsly>=2.4.0                      # fast JSON
```

## `src/__main__.py`

```python
import asyncio
from src.main import main

asyncio.run(main())
```

## `src/__init__.py`

```python
# empty
```

## `src/constants.py`

```python
"""Endpoints, headers, profile choices — all in one place."""

# TLS profile (see .ai/skills/tls-fingerprinting.md)
TLS_PROFILE = "chrome131"     # justify in README

# Endpoints
BASE_URL = "https://target.com"
API_URL  = f"{BASE_URL}/api/v1"
WARMUP_URL = f"{BASE_URL}/"

# Default headers (anti-bot + platform contract)
DEFAULT_HEADERS = {
    # Set by curl_cffi impersonate=, included here for documentation:
    # "User-Agent": "...",
    # "Sec-CH-UA": "...",
    # "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Volatile doc_ids (auto-refresh on 400/404)
DOC_ID_SNAPSHOT = {
    # "OperationName": "<doc_id>",  # Last verified 2026-05-17
}

# Retry policy
MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0   # seconds; exponential 1/2/4/8/16
```

## `src/client.py`

```python
"""HTTP client wrapper — handles warmup, retry, profile rotation, block detection."""
import asyncio
import secrets
from curl_cffi.requests import AsyncSession
from src.constants import TLS_PROFILE, WARMUP_URL, DEFAULT_HEADERS, MAX_RETRIES, RETRY_DELAY_BASE


BLOCK_MARKERS = [
    b"_____tmd_____", b"baxia-manager", b"sufei-punish",
    b"Just a moment", b"challenge-platform", b"cf-mitigated",
    b"captcha-delivery.com", b"Pardon Our Interruption",
]


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


class TargetClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)
        self._warm = False
    
    async def init_session(self):
        """Idempotent warmup — bootstrap anti-bot cookies via homepage GET."""
        if self._warm:
            return
        r = await self.session.get(WARMUP_URL)
        if r.status_code != 200:
            raise RuntimeError(f"Warmup failed: {r.status_code}")
        self._warm = True
    
    async def get(self, url: str, **kwargs):
        await self.init_session()
        return await self._with_retry("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs):
        await self.init_session()
        return await self._with_retry("POST", url, **kwargs)
    
    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    # Block detected — backoff, no rotation here (caller handles)
                    await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
                    continue
                return r
            except Exception as e:
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")
    
    async def close(self):
        await self.session.close()


def build_proxy_url(password: str, country: str = "US") -> str:
    """Apify Residential with sticky session."""
    session_id = "s" + secrets.token_hex(8)
    return f"http://groups-RESIDENTIAL,country-{country},session-{session_id}:{password}@proxy.apify.com:8000"
```

## `src/extractor.py`

```python
"""Pure parsing logic — takes raw HTTP response, returns record dict."""
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_record(raw: dict, source: str, input_value: str) -> dict:
    """
    raw         — upstream JSON payload (passthrough)
    source      — envelope tag ("S1-api", "S2-html", etc.)
    input_value — original user input for traceability
    """
    return {
        "_input":     input_value,
        "_source":    source,
        "_scrapedAt": utc_now_iso(),
        # Raw passthrough — do NOT rename fields
        **raw,
    }


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input":     input_value,
        "_source":    "none",
        "_scrapedAt": utc_now_iso(),
        "_error":     error_kind,
        "_errorDetail": detail,
    }
```

## `src/main.py`

```python
import asyncio
from apify import Actor
from src.client import TargetClient, build_proxy_url
from src.extractor import extract_record, extract_error


async def process_one(item: str, proxy_url: str | None) -> dict:
    client = TargetClient(proxy_url=proxy_url)
    try:
        r = await client.get(f"https://target.com/api/v1/items/{item}")
        if r.status_code == 200:
            return extract_record(r.json(), source="S1-api", input_value=item)
        if r.status_code == 404:
            return extract_error(item, "not_found")
        return extract_error(item, f"http_{r.status_code}")
    except Exception as e:
        return extract_error(item, "exception", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}
        items = input_data.get("startItems", [])
        max_concurrency = input_data.get("maxConcurrency", 4)
        
        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        
        sem = asyncio.Semaphore(max_concurrency)
        
        async def _bounded(item):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await process_one(item, proxy_url)
                await Actor.push_data(record)
        
        await asyncio.gather(*(_bounded(i) for i in items), return_exceptions=True)
```

## `.actor/actor.json`

See [`playbooks/apify-deploy.md`](../playbooks/apify-deploy.md) for the full template.

## `.actor/Dockerfile`

```dockerfile
FROM apify/actor-python:3.12

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# CMD inherited from base image — runs python -m src
```

## `.actor/input_schema.json`

```json
{
    "title": "Target Scraper",
    "type": "object",
    "schemaVersion": 1,
    "properties": {
        "startItems": {
            "title": "Items to scrape",
            "type": "array",
            "editor": "stringList",
            "description": "URLs or identifiers depending on platform."
        },
        "maxConcurrency": {
            "title": "Max concurrent workers",
            "type": "integer",
            "default": 4,
            "minimum": 1,
            "maximum": 16
        },
        "proxyConfiguration": {
            "title": "Proxy",
            "type": "object",
            "editor": "proxy",
            "default": {
                "useApifyProxy": true,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        }
    },
    "required": ["startItems"]
}
```

## `.gitignore`

```
__pycache__/
*.pyc
.venv/
venv/
apify_storage/
.env
.DS_Store
*.egg-info/
.pytest_cache/
```

## `.dockerignore`

```
__pycache__
*.pyc
.venv
venv
apify_storage
.git
.gitignore
.github
*.md
!README.md
.pytest_cache
tests/
```

## Optional: Pydantic models

For high-reliability scrapers, validate output shape:

```python
# src/models.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class UserRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")    # raise on unknown fields
    
    _input: str
    _source: str
    _scrapedAt: str
    
    id: str
    username: str
    followers_count: int
    bio: Optional[str] = None
    # ... etc


def validate_or_error(record: dict, input_value: str) -> dict:
    try:
        return UserRecord.model_validate(record).model_dump()
    except Exception as e:
        return {
            "_input": input_value,
            "_source": "none",
            "_error": "validation_failed",
            "_errorDetail": str(e),
        }
```

## Concurrency knobs

| Knob | Typical value | When to adjust |
| --- | --- | --- |
| `maxConcurrency` | 4 | Lower (1) for sticky-session targets; higher (8–16) for low-risk public APIs |
| `MAX_RETRIES` | 5 | Higher (8) for WAF-heavy targets |
| `RETRY_DELAY_BASE` | 1.0s | Higher (2.0) for strict rate-limit windows |
| Jitter range | 0.3–1.5s | Random per-request delay to avoid synchronization patterns |

## Anti-patterns (don't)

- ❌ `pip install` without pinning major versions (breaks builds randomly)
- ❌ Cross-actor imports (`from ../other_actor/shared` — build context is one folder)
- ❌ Skipping `.dockerignore` (uploads `apify_storage/` data, slow build)
- ❌ Logging credentials / proxy passwords
- ❌ Catching `Exception` at top level without re-raising or emitting error record (silent failures)
- ❌ Calling `Actor.push_data()` from inside the warmup path (warmup is internal; only push completed records)

## Where used

This is the canonical layout for **every Python Apify actor in the portfolio**:
- 8 Tokopedia actors
- 4 Shopee actors
- 5 Alibaba actors
- 5 StockX actors
- 26 Online News actors
- 3 Bloomberg actors
- 8 TikTok actors
- 11 Google Maps actors
- 6 Instagram, 4 Threads, 4 X (Twitter), 3 Facebook, 4 Reddit, 8 YouTube, 3 Twitch, 3 Pinterest, 2 Mastodon, 2 Medium, 2 Tumblr, 2 Quora, 3 Substack, 2 Telegram, 4 Bluesky actors
- 5 Travel actors (Airbnb, TA, Skyscanner family)
- 2 Real-Estate actors
- Capterra B2B
- Ventusky weather

## See also
- [`stacks/beanstalk-kafka-pipeline.md`](beanstalk-kafka-pipeline.md) (for high-volume production)
- [`stacks/nodejs-crypto-sidecar.md`](nodejs-crypto-sidecar.md) (when JS-VM tokens needed)
- [`playbooks/apify-deploy.md`](../playbooks/apify-deploy.md)
- [`conventions/dataset-envelope.md`](../conventions/dataset-envelope.md)
