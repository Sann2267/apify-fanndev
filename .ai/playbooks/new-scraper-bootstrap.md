# Playbook: New Scraper Bootstrap

> **Workflow for starting a new scraper from zero.** From "user gave me a target URL" to "actor pushed to Apify Marketplace, smoke-tested." Follow this sequence and don't skip steps.

## Step 0 — Clarify scope before writing code

Ask the user:
- [ ] What's the exact target (URL, platform)?
- [ ] What data fields are required vs nice-to-have?
- [ ] What's the expected output: raw passthrough or normalized schema?
- [ ] Throughput target: dozens, thousands, millions per run?
- [ ] Deployment target: Apify Marketplace, internal pipeline, on-prem?
- [ ] Any auth context (account-pool, OAuth, none)?
- [ ] Pricing strategy if Apify Marketplace (`per-result` vs `subscription`)?

If user is vague, suggest defaults (Apify Marketplace, raw passthrough, none auth, residential proxy on) but get explicit signoff.

## Step 1 — Reconnaissance (30 min budget)

Before writing a single line of code, recon the target:

### 1.1 Triage with `curl` + browser DevTools

```bash
# Baseline: does plain curl get 200?
curl -i "https://target.com/some/endpoint"
```

Open Chrome DevTools → Network tab → load the target page in browser. Note:
- Which **XHR/fetch** calls fetch the data you want (vs SSR HTML)?
- Which **cookies** appear on first load (`_abck`, `_dd_s`, `_px3`, etc.)?
- Which **headers** does the browser send (especially custom `x-*` ones)?
- Is the data in `__NEXT_DATA__`, `__APOLLO_STATE__`, or AJAX?
- Are there **JSON-LD blocks** in `<head>`? (Always prefer them if present.)

### 1.2 WAF identification

Use the [`waf-triage.md`](waf-triage.md) decision tree. Result: one of `none`, `cloudflare`, `perimeterx`, `datadome`, `akamai`, `aliyun`, `kasada`, `meta`, `tiktok-mssdk`, `custom`.

### 1.3 Endpoint shape decision

In priority order, look for:
1. **Public XRPC/REST without auth** (Bluesky, Mastodon, Telegram) — easiest, ship in hours
2. **JSON-LD in SSR HTML** — most stable, no auth gymnastics
3. **`__NEXT_DATA__` SSR** — full data inline, schema-stable
4. **Public GraphQL with consumer key** (Tumblr, Reddit installed-app OAuth) — auth-light
5. **Persisted-query GraphQL with doc_id/queryId** (Meta, Twitter, Airbnb) — warm-page + harvest
6. **Internal RPC (batchexecute, MTOP)** — high effort, niche
7. **Mobile-API signature reproduction** (TikTok X-Gnarly) — high effort, recompile risk

Pick the highest tier that carries your required fields.

## Step 2 — Spike: prove ONE working request

Before designing the full scraper, get **one HTTP call** that returns the data you need:

```python
# scratch.py — discard after this step
import asyncio
from curl_cffi.requests import AsyncSession

async def main():
    session = AsyncSession(impersonate="chrome131", timeout=30)
    
    # Warmup (per WAF docs)
    await session.get("https://target.com/")
    
    # The actual call
    r = await session.get("https://target.com/api/...")
    print(r.status_code, len(r.content))
    print(r.json())   # or r.text for HTML

asyncio.run(main())
```

If this fails — iterate on the recon decisions:
- 403/empty? → Wrong TLS profile or missing warmup
- 200 but body is challenge? → Body-marker WAF (Aliyun); add detection
- Right shape but missing fields? → Wrong endpoint, escalate to GraphQL/doc_id
- Required auth field? → Warm-page token harvest (see `skills/warm-page-token-harvest.md`)

**Do not move past this step until ONE request works.** All later complexity builds on this foundation.

## Step 3 — Scaffold the Apify actor structure

Copy the canonical boilerplate from [`stacks/python-apify-actor.md`](../stacks/python-apify-actor.md):

```
actor-{platform}-{purpose}/
├── .actor/
│   ├── actor.json
│   ├── input_schema.json
│   └── Dockerfile
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── main.py
│   ├── client.py          # HTTP wrapper + warmup + retry
│   ├── extractor.py       # parse response → records
│   └── models.py          # Pydantic output models
├── requirements.txt
├── README.md
└── .gitignore
```

## Step 4 — Implement the client

Wrap the spike code into a reusable `Client` class:

```python
# src/client.py
from curl_cffi.requests import AsyncSession

class TargetClient:
    def __init__(self, proxy_url: str | None = None):
        self.session = AsyncSession(
            impersonate="chrome131",
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self._warm = False
    
    async def init_session(self):
        if self._warm: return
        r = await self.session.get("https://target.com/")
        if r.status_code != 200:
            raise RuntimeError(f"Warmup failed: {r.status_code}")
        self._warm = True
    
    async def fetch_entity(self, entity_id: str) -> dict:
        await self.init_session()
        # ... actual call with retry / rotation ...
        return data
```

## Step 5 — Implement the extractor

Separate transport (Client) from parsing (Extractor). The extractor takes raw JSON/HTML, returns structured records:

```python
# src/extractor.py
def extract_record(raw: dict, source: str) -> dict:
    """raw is upstream payload; returns dataset-ready record."""
    return {
        # Raw passthrough fields (don't rename)
        **raw,
        # Envelope tags
        "_source": source,
        "_scrapedAt": datetime.utcnow().isoformat() + "Z",
    }
```

## Step 6 — Implement multi-strategy fallback

Even for "easy" targets, design the fallback chain. See [`skills/multi-strategy-fallback.md`](../skills/multi-strategy-fallback.md).

```python
async def fetch_with_fallback(entity_id: str, client: TargetClient) -> dict:
    # S1
    try:
        data = await client.fetch_primary(entity_id)
        return {**extract_record(data, "S1-api"), "_input": entity_id}
    except (BlockedByWAF, NotFound) as e:
        pass
    
    # S2
    try:
        data = await client.fetch_html_fallback(entity_id)
        return {**extract_record(data, "S2-html"), "_input": entity_id}
    except NotFound:
        pass
    
    # Fail loud
    return {"_input": entity_id, "_source": "none", "_error": "all_strategies_failed"}
```

## Step 7 — Main loop with bounded concurrency

```python
# src/main.py
async def main():
    async with Actor:
        input_data = await Actor.get_input()
        items = input_data["startItems"]
        max_concurrency = input_data.get("maxConcurrency", 4)
        
        proxy_config = await Actor.create_proxy_configuration(
            groups=["RESIDENTIAL"],
            country_code=input_data.get("proxyCountry", "US"),
        )
        
        sem = asyncio.Semaphore(max_concurrency)
        
        async def _process(item):
            async with sem:
                proxy_url = await proxy_config.new_url()
                client = TargetClient(proxy_url)
                record = await fetch_with_fallback(item, client)
                await Actor.push_data(record)
        
        await asyncio.gather(*(_process(i) for i in items), return_exceptions=True)
```

## Step 8 — Define input schema

```json
// .actor/input_schema.json
{
    "title": "Target Platform Scraper",
    "type": "object",
    "schemaVersion": 1,
    "properties": {
        "startItems": {
            "title": "Items to scrape",
            "type": "array",
            "editor": "stringList",
            "description": "URLs, usernames, or IDs depending on platform."
        },
        "maxConcurrency": {
            "title": "Max concurrent workers",
            "type": "integer",
            "default": 4,
            "minimum": 1,
            "maximum": 16
        },
        "proxyCountry": {
            "title": "Proxy country code (ISO 3166-1 alpha-2)",
            "type": "string",
            "default": "US"
        }
    },
    "required": ["startItems"]
}
```

## Step 9 — Dockerfile

```dockerfile
FROM apify/actor-python:3.12

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

CMD ["python", "-m", "src"]
```

## Step 10 — Smoke test locally

```bash
# Set env (Apify-emulated)
$env:APIFY_LOCAL_STORAGE_DIR = "./apify_storage"
$env:APIFY_DEFAULT_DATASET_ID = "default"

# Provide input
mkdir -p apify_storage/key_value_stores/default
echo '{"startItems": ["test-handle"], "maxConcurrency": 1}' > apify_storage/key_value_stores/default/INPUT.json

# Run
python -m src
```

Verify:
- [ ] Output records pushed to `apify_storage/datasets/default/`
- [ ] Each record has `_source` envelope tag
- [ ] Failures emit structured `_error` records (not silent drops)
- [ ] At least one S1 record exists (don't ship if everything degrades to S2)

## Step 11 — Define the output (dataset) schema

Every actor ships a `.actor/output_schema.json` documenting every field its `extract_*` functions
can emit, plus a table view for the Console Output tab. Full structure, wiring, and the
`storages.dataset` vs top-level `"output"` pitfall are in
[`skills/actor-output-schema/SKILL.md`](../skills/actor-output-schema/SKILL.md) — don't hand-roll it
here, do it as its own step:

```json
// .actor/actor.json
{
    "actorSpecification": 1,
    "name": "target-scraper",
    "version": "0.0",
    "buildTag": "latest",
    "title": "Target Scraper",
    "description": "...",
    "dockerfile": "./Dockerfile",
    "input": "./input_schema.json",
    "storages": {
        "dataset": "./output_schema.json"
    }
}
```

Then `apify validate-schema` should print `Success: Dataset schema is valid.` before you move on.

## Step 12 — README + push

- Document the WAF, TLS profile, known limits.
- Push: `apify push` from project root.
- Smoke test on Apify cloud (different IP environment) — DC vs residential can change behavior.

## Anti-Patterns to Avoid

- ❌ Hardcoding doc_id/queryId without a refresh path
- ❌ Single-strategy with no fallback
- ❌ Silent empty returns on missing fields (use `_error: "missing_X"` instead)
- ❌ Mixing transport and parsing in the same function
- ❌ Adding Playwright/Camoufox before exhausting HTTP options
- ❌ Renaming fields (breaks downstream consumer schema-stability)
- ❌ Sharing one HTTP session across asyncio tasks
- ❌ Skipping smoke test on cloud (Apify env differs from local)

## Time budget

| Stage | Time |
| --- | --- |
| Step 0–1 (clarify + recon) | 30 min |
| Step 2 (spike) | 1–4 hours (most variance) |
| Step 3–4 (scaffold + client) | 1 hour |
| Step 5–6 (extractor + fallback) | 1–3 hours |
| Step 7–9 (main loop + schema + Dockerfile) | 1 hour |
| Step 10–12 (test + deploy) | 1 hour |
| **Total greenfield** | **~6–12 hours** for a known WAF target |

If you're at hour 4 still stuck on Step 2 (spike), STOP and re-do WAF triage. The recon was wrong.

## See also
- [`playbooks/waf-triage.md`](waf-triage.md)
- [`playbooks/reverse-engineer-internal-api.md`](reverse-engineer-internal-api.md)
- [`playbooks/apify-deploy.md`](apify-deploy.md)
- [`stacks/python-apify-actor.md`](../stacks/python-apify-actor.md)
