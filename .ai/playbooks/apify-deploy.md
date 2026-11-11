# Playbook: Apify Deploy & Marketplace Publishing

> **The standard deployment target for production scrapers.** Apify gives you Docker hosting, residential proxy, Dataset storage, scheduling, and (if marketplaced) a billing layer. This playbook covers actor.json + Dockerfile + push + marketplace listing.

## Prereqs

- Apify CLI installed: `npm i -g apify-cli`
- Apify account created at apify.com
- Logged in: `apify login`
- Project structure follows [`stacks/python-apify-actor.md`](../stacks/python-apify-actor.md)

## Minimum file set

```
actor-yourplatform-scraper/
├── .actor/
│   ├── actor.json           # actor metadata
│   ├── input_schema.json    # input validation + UI
│   ├── output_schema.json   # dataset field docs + Output-tab table view
│   └── Dockerfile           # build instructions
├── src/
│   └── ...                  # your Python code
├── requirements.txt
├── README.md
└── .gitignore
```

## `actor.json` essentials

```json
{
    "actorSpecification": 1,
    "name": "yourplatform-scraper",
    "version": "0.1",
    "buildTag": "latest",
    "title": "YourPlatform Scraper",
    "description": "One-liner describing what users get",
    "categories": ["ECOMMERCE", "DATA_PRODUCTS"],
    "dockerfile": "./Dockerfile",
    "input": "./input_schema.json",
    "storages": {
        "dataset": "./output_schema.json"
    }
}
```

`storages.dataset` is a **string path** to a separate dataset-schema file, not an inline object —
see [`skills/actor-output-schema/SKILL.md`](../skills/actor-output-schema/SKILL.md) for the full
`output_schema.json` structure (fields + views) and why a top-level `"output"` key must never be
used instead (it's a different Apify feature and breaks the Output tab).

**Categories** (Apify Marketplace, exact strings):
- `ECOMMERCE`
- `SOCIAL_MEDIA`
- `MEDIA_AND_NEWS`
- `TRAVEL`
- `REAL_ESTATE`
- `JOBS_AND_HR`
- `LEAD_GENERATION`
- `MARKETING`
- `MAPS`
- `DATA_PRODUCTS`
- `BUSINESS`

Pick 1–2 categories max. Marketplace search ranks better with focused tagging.

## `input_schema.json` patterns

### Pattern: URL list + flags

```json
{
    "title": "YourPlatform Scraper",
    "type": "object",
    "schemaVersion": 1,
    "properties": {
        "startUrls": {
            "title": "Start URLs",
            "type": "array",
            "editor": "requestListSources",
            "description": "Direct URLs to scrape.",
            "prefill": [{"url": "https://example.com/page"}]
        },
        "maxResults": {
            "title": "Max results per input",
            "type": "integer",
            "default": 100,
            "minimum": 1,
            "maximum": 10000
        },
        "enrichDetails": {
            "title": "Enrich with detail-page data",
            "type": "boolean",
            "default": false,
            "description": "Slower but richer output."
        }
    },
    "required": ["startUrls"]
}
```

### Pattern: tagged dropdown (mode selector)

```json
{
    "mode": {
        "title": "Scrape mode",
        "type": "string",
        "editor": "select",
        "enum": ["search", "url", "detail", "category", "shop"],
        "enumTitles": ["By keyword search", "By URL", "By product ID", "By category ID", "By shop slug"],
        "default": "search"
    }
}
```

### Pattern: proxy configuration

```json
{
    "proxyConfiguration": {
        "title": "Proxy",
        "type": "object",
        "editor": "proxy",
        "default": {
            "useApifyProxy": true,
            "apifyProxyGroups": ["RESIDENTIAL"]
        }
    }
}
```

In code:
```python
proxy_config = await Actor.create_proxy_configuration(
    actor_proxy_input=input_data.get("proxyConfiguration")
)
```

## Dockerfile (canonical)

```dockerfile
FROM apify/actor-python:3.12

# System deps (if curl_cffi needs binary tweaks)
# Usually none needed — base image is sufficient

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip list --format=freeze > /tmp/installed-versions.txt

COPY . ./

# CMD inherited from base image runs python -m src
```

### Variant: Python + Node sidecar (for TikTok X-Gnarly)

```dockerfile
FROM apify/actor-python:3.12

# Install Node.js 20 alongside Python
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && node --version

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
```

### Variant: Crawlee Python

```dockerfile
FROM apify/actor-python-crawlee:3.11

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
```

## Local smoke test

```powershell
# Set env to use local storage
$env:APIFY_LOCAL_STORAGE_DIR = "./apify_storage"

# Provide input
$inputJson = @'
{"startUrls": [{"url": "https://example.com/test"}], "maxResults": 5}
'@
New-Item -ItemType Directory -Path apify_storage/key_value_stores/default -Force | Out-Null
$inputJson | Out-File -Encoding utf8 apify_storage/key_value_stores/default/INPUT.json

# Run
python -m src
```

Verify:
- [ ] `apify_storage/datasets/default/*.json` has expected records
- [ ] Each record carries envelope tags
- [ ] No silent empty fields (any failure has `_error`)
- [ ] Compute time + RAM within Apify free-tier limits (256 MB / no minute cap on free)

## Push to Apify Cloud

```powershell
cd C:\Han\portfolio\2026\actor-yourplatform-scraper

# Confirm both schemas are valid before spending a build
apify validate-schema

# First push creates the actor in your account
apify push

# Subsequent pushes update the existing actor (matched by name in actor.json)
apify push
```

The CLI:
1. Tars the project (respects `.gitignore` + `.dockerignore`)
2. Uploads tarball
3. Triggers Docker build on Apify infra
4. Reports build URL (open in browser to watch logs)

## Cloud smoke test

Don't trust local smoke alone — cloud environment differs:
- Different egress IP (Apify DC vs your home/office)
- Different proxy availability
- Different timeout behavior
- Different file system permissions

Always run a 1-input smoke test on Apify cloud before declaring done.

```
# Via web UI: Actor → "Run" → paste input JSON → observe output
# Via CLI:
apify call yourplatform-scraper --input '{"startUrls": [{"url": "https://..."}]}'
```

## Marketplace listing (when ready to monetize)

### Pricing model: pick one

| Model | Best for | Apify takes |
| --- | --- | --- |
| **Pay per result** | High-throughput, predictable cost per row | Apify fees + your margin |
| **Pay per event** | Custom events (e.g. detail-page enrichment as a separate event) | Apify fees + your margin |
| **Monthly rental** | Continuous-use customers, premium tier | Apify fees + your margin |
| **Free** | Community / lead-gen | n/a |

**Recommendation for new actors:** start with pay-per-result. Easier to price; easier to compare with competitors on marketplace.

### Recommended pricing benchmarks

| Tier | Per 1,000 results | Examples |
| --- | --- | --- |
| Lightweight | $0.00025–$0.001 | TikTok comments, basic profile scrape |
| Standard | $1–$5 | Social media post detail, e-commerce product |
| Premium | $5–$15 | Reviews with multi-rating, enrichment, multi-source |

### Listing copy template

```markdown
# YourPlatform Scraper — One-line value prop

## Use cases
- Use case 1 (with concrete example)
- Use case 2
- Use case 3

## Features
- ✅ HTTP-only (no browser, low cost)
- ✅ Multi-country support (list specific countries)
- ✅ Configurable concurrency
- ✅ Optional detail enrichment

## Output
Structured JSON with these fields: ...

## Pricing
$X per 1,000 results

## Limitations
- Known limit A
- Known limit B
```

### SEO for marketplace

- **Actor name:** include platform + purpose (`tiktok-profile-scraper`, not `my-scraper-v1`)
- **Description:** include keywords customers search (`tiktok scraper`, `tiktok api`, `tiktok data extraction`)
- **Categories:** stick to 1–2 most relevant — multi-category dilutes ranking
- **README:** customers preview before buying — make it compelling

## Healthcheck schedule (post-launch)

| Cadence | What to verify |
| --- | --- |
| Daily | Top-target smoke test passes |
| Weekly | doc_id / queryId / persisted hashes still valid |
| Monthly | Bundle hash diff for queryId-based scrapers |
| Quarterly | TLS profile pool refresh (rotation pool members may go stale) |
| Quarterly | Schema diff vs upstream (new fields added? required fields removed?) |

Set up Apify schedule to run smoke test on a cron. Configure email alerts on failure.

## Common deployment failures

### Build failure: missing system lib for `curl_cffi`
Add to Dockerfile before `pip install`:
```dockerfile
RUN apt-get update && apt-get install -y libcurl4-openssl-dev && rm -rf /var/lib/apt/lists/*
```

### Build failure: `pydantic` version conflict with `crawlee`
Pin:
```
pydantic>=2.9.0,<2.10.0
```
(Crawlee 0.6.12 breaks on pydantic ≥2.10.3.)

### Runtime: actor immediately exits with no output
Usually a `await Actor.get_input()` call before the `async with Actor:` context. Move to inside.

### Runtime: proxy auth fails (502)
Apify proxy session_id must match `^[\w._~]+$`. UUIDs with dashes fail. Use `secrets.token_hex(8)` instead.

### Runtime: residential pool exhausted (502)
Your Apify plan may have a proxy cap. Check the dashboard. Free tier has very limited residential.

## See also
- [`playbooks/new-scraper-bootstrap.md`](new-scraper-bootstrap.md)
- [`stacks/python-apify-actor.md`](../stacks/python-apify-actor.md)
- [`conventions/dataset-envelope.md`](../conventions/dataset-envelope.md)
