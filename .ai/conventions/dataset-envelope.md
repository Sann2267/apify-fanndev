# Convention: Dataset Output Envelope & Raw-Passthrough Rule

> **Every record pushed to the Apify Dataset (or Kafka topic) follows the same envelope.** This is what makes 85+ actors interoperable. Downstream consumers (Elasticsearch indexers, SQL ETLs, RAG pipelines) trust the envelope and branch on `_source` for strategy-specific logic.

## The envelope (mandatory)

Every record MUST carry at minimum these three meta-fields:

```python
{
    "_input":     "<original input value>",      # for traceability
    "_source":    "S1-graphql",                  # which strategy emitted this
    "_scrapedAt": "2026-05-17T14:23:01Z",        # UTC ISO 8601
    
    # ... raw passthrough payload ...
}
```

### Field semantics

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `_input` | string | ✅ | The exact user-provided value (username, URL, ID) — lets consumers correlate output back to input |
| `_source` | string | ✅ | Strategy tag (`S1-api`, `S2-html`, `S3-embed`, `none`) — see [`skills/multi-strategy-fallback.md`](../skills/multi-strategy-fallback.md) |
| `_scrapedAt` | ISO 8601 UTC | ✅ | When this specific record was emitted |
| `_error` | string | conditional | Present ONLY for failure records (mutually exclusive with payload) |
| `_errorDetail` | string | optional | Free-form diagnostic |
| `_warning` | string | optional | Non-fatal degradation marker (e.g. `min_span_reached_capped`) |

## The raw-passthrough rule

**Output upstream's field shape verbatim.** Do NOT rename, restructure, or normalize:

### ❌ Wrong (renames create downstream coupling)

```python
return {
    "_input": username,
    "_source": "S1-api",
    "user_id":          raw["rest_id"],          # renamed
    "handle":           raw["screen_name"],      # renamed
    "follower_count":   raw["followers_count"],  # renamed
}
```

When upstream adds a new field, you have to discover and add it. When upstream renames `followers_count` → `follower_count`, your downstream breaks.

### ✅ Right (raw passthrough)

```python
return {
    "_input": username,
    "_source": "S1-api",
    "_scrapedAt": utc_now_iso(),
    **raw,                                       # keep upstream's exact field names
}
```

Downstream consumers (SQL, ES, RAG) handle normalization in their layer. New fields automatically flow through. Renames cause exactly ONE point of update (the downstream view), not N actors.

## Per-platform `_source` taxonomy

Use consistent strategy names within a platform:

### Bluesky
- `S1-xrpc` — `public.api.bsky.app/xrpc/...`

### Telegram
- `S1-html` — `t.me/s/<channel>`

### YouTube
- `S1-innertube` — `youtubei/v1/...`
- `S2-html` — watch page `ytInitialData` / `ytInitialPlayerResponse`

### Substack
- `S1-api` — `substack.com/api/v1/...`
- `S2-html` — `window._preloads` parsed from HTML

### Instagram / Facebook / Threads
- `S1-graphql` — POST `/api/graphql` with doc_id
- `S1-web_profile_info` — `/api/v1/users/web_profile_info/` (account specifically)
- `S2-html` — SSR HTML JSON walk
- `S2-embed` — `/p/<shortcode>/embed/captioned/`

### Twitter / X
- `S1-graphql` — guest-token + queryId
- `S2-syndication` — `cdn.syndication.twimg.com/tweet-result`

### Reddit
- `S1-oauth-api` — OAuth installed-app
- `S2-jsonpublic-www` — `www.reddit.com/.../<x>.json`
- `S3-oldjson` — `old.reddit.com/.../<x>.json`

### Mastodon
- `S1-api` — `/api/v1/...` (per-instance)

### Medium
- `S1-json` — `medium.com/<slug>?format=json` (user only)
- `S2-html-apollo` — Apollo state extraction

### Tumblr
- `S1-api` — v2 API with consumer key

### Twitch
- `S1-gql` — `gql.twitch.tv/gql`

### Pinterest
- `S1-resource` — `pinterest.com/resource/<X>Resource/get/`
- `S2-html-inline-state` — `__PWS_INITIAL_PROPS__`

### TikTok
- `api` — signed Web API (X-Bogus + X-Gnarly)
- `ssr` — `__UNIVERSAL_DATA_FOR_REHYDRATION__` SSR HTML
- `embed` — FRONTITY embed fallback

### Online News (varied)
- `S1-jsonld` — JSON-LD primary
- `S2-nextdata` — `__NEXT_DATA__`
- `S3-apollo` — Apollo state
- `S4-html` — CSS selectors
- `S5-trafilatura` — last-resort enrichment

### Bloomberg
- `S1-nextdata`, `S2-preloadedstate`, `S3-ldjson`, `S4-ogmeta`

## Error records — same envelope, no payload

Failures emit records with `_error`, `_source: "none"`, NO payload fields:

```python
{
    "_input":       "deleted_user",
    "_source":      "none",
    "_scrapedAt":   "2026-05-17T14:23:01Z",
    "_error":       "not_found",
    "_errorDetail": "HTTP 404 from S1, S2-embed returned {_error:'no_anon_data'}",
}
```

**Don't drop failures silently.** A consumer that sees `_error: "not_found"` knows the input was processed (and that the entity is gone) — vs missing rows which look like the actor crashed.

## Multi-record-type per run (`recordType` discriminator)

Some scrapers emit different record shapes from one run. Use a `recordType` field on top of the envelope:

```python
# Tokopedia shop scraper emits both shop profile + per-listing records
{"_input": "tokopedia/some-shop", "_source": "S1-graphql", "recordType": "SHOP_PROFILE", ...}
{"_input": "tokopedia/some-shop", "_source": "S1-graphql", "recordType": "SHOP_LISTING", ...}

# Alibaba review scraper:
{"_input": "<product_id>", "_source": "S1-html", "recordType": "AGGREGATE", ...}
{"_input": "<product_id>", "_source": "S2-mtop", "recordType": "REVIEW", ...}

# StockX:
{"recordType": "PRODUCT", ...}
{"recordType": "VARIANT", ...}
{"recordType": "AGGREGATE", ...}
{"recordType": "PER_VARIANT", ...}
{"recordType": "PER_SIZE_72H", ...}
```

Apify Dataset views can filter by `_type` or `recordType` to give consumers distinct tables.

## Timestamp discipline

`_scrapedAt` is always **UTC ISO 8601 with `Z` suffix**:

```python
from datetime import datetime, timezone

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
# Always emit: "2026-05-17T14:23:01Z"
```

❌ Don't use local time (`datetime.now()`)
❌ Don't use millisecond precision unless the consumer needs it
❌ Don't use Unix timestamp (`int(time.time())`)

## Optional: `_attempts` for debugging fallback chains

When S1 → S2 → S3 cascades happen, log what each strategy returned:

```python
{
    "_input": "@somehandle",
    "_source": "S2-html-apollo",            # final winner
    "_attempts": {
        "S1-graphql":     "stale_doc_id",
        "S2-html-apollo": "ok",
    },
    "_scrapedAt": "...",
    # payload...
}
```

Helps ops diagnose "why did 60% of my output come from S2?" without grep'ing actor logs.

## Don't pollute the envelope

❌ Don't add `_actorVersion`, `_runId`, `_apifyDatasetId`, etc. — Apify already tracks these.
❌ Don't add `_userAgent`, `_proxyIp` — security/privacy concerns.
❌ Don't add `_durationMs` — belongs in monitoring, not data.
❌ Don't reuse `_*` prefix for application fields (`_isFavorite`, `_isPremium` — drop the underscore).

The `_*` namespace is reserved for envelope/meta only.

## Where used

This convention is consistent across **all 85+ actors in the portfolio**:
- Apify Marketplace actors (Tokopedia, Shopee, Alibaba, StockX, TikTok, Travel, Real-Estate, Capterra, Ventusky, Google Maps, sosmed suite — 16 platforms, 60+ actors)
- Production pipeline outputs (Tokopedia Kafka, TikTok Crawler Kafka, Shopee shopesss Kafka)
- News scrapers (26 publishers, smart-news-loader with cascading `_source`)
- Bloomberg suite (article, news-feed, news-search)

## See also
- [`skills/multi-strategy-fallback.md`](../skills/multi-strategy-fallback.md)
- [`conventions/error-handling.md`](error-handling.md)
- [`stacks/python-apify-actor.md`](../stacks/python-apify-actor.md)
