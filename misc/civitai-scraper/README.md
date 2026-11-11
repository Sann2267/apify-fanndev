# Civitai Scraper

Search and extract Civitai AI model listings, full model/download details, image gallery posts, creators, and tags — no account or API key needed.

## Why use this actor

- One actor covers Civitai's whole public surface: search models, pull full download-ready details for specific models, browse the image gallery, and list creators/tags
- Full model detail includes every version's file list — direct download URLs, file hashes (SHA256, BLAKE3, AutoV2...), virus/pickle-scan results, and base model — everything you need to build a model catalog or mirror
- No account, login, or API key required — this actor talks to Civitai's own official public REST API
- Automatic retries on temporary network hiccups
- Robust pagination — automatically follows Civitai's cursor/page links up to the limit you set, instead of returning just one page
- Honest about limits: `modelId` image filtering is fixed to work correctly even though Civitai's own API silently returns nothing for it (see Known limits) — and generation prompt metadata is never available publicly, which is stated plainly rather than faked

## How it works

Pick a `mode`:
1. **`models`** — search/browse AI models (checkpoints, LoRAs, embeddings, etc.) with filters for query text, tag, username, type, sort order, and time window.
2. **`model-detail`** — fetch full detail (every version, every file, every download URL) for one or more specific model IDs.
3. **`images`** — browse the image gallery, optionally filtered by model, model version, username, or post.
4. **`creators`** — list or search usernames.
5. **`tags`** — list or search tags.

## Input

**Search models:**
```json
{
  "mode": "models",
  "query": "pony",
  "types": ["Checkpoint"],
  "sort": "Most Downloaded",
  "period": "AllTime",
  "maxItems": 50
}
```

**Model detail (by ID):**
```json
{
  "mode": "model-detail",
  "modelIds": ["4201", "257749"]
}
```

**Images:**
```json
{
  "mode": "images",
  "modelId": 4201,
  "sort": "Most Reactions",
  "maxItems": 50
}
```

**Creators / Tags:**
```json
{ "mode": "creators", "query": "civ", "maxItems": 20 }
```
```json
{ "mode": "tags", "query": "anime", "maxItems": 20 }
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"models"` (default), `"model-detail"`, `"images"`, `"creators"`, or `"tags"`. |
| `query` | string | Search term. `models` mode searches names, `creators` mode searches usernames, `tags` mode searches tag names. |
| `tag` | string | `models` mode — exact tag filter. |
| `username` | string | `models`/`images` mode — exact creator filter. |
| `types` | array | `models` mode — filter by model type(s) (`Checkpoint`, `LORA`, `TextualInversion`, etc.). |
| `sort` | string | Sort order — value set differs by mode (see input schema for the full list). |
| `period` | string | `models`/`images` mode — `Day`/`Week`/`Month`/`Year`/`AllTime`. |
| `nsfw` | string | `images` mode — content-rating filter. |
| `modelId` | integer | `model-detail` mode: the model to fetch. `images` mode: only images generated with this model (auto-resolved to its versions — see Known limits). |
| `modelIds` | array | `model-detail` mode — multiple model IDs in one run. |
| `modelVersionId` | integer | `images` mode — only images from this exact model version (faster/more direct than `modelId`). |
| `postId` | integer | `images` mode — only images from this post. |
| `maxItems` | integer | Max results to return (`models`/`images`/`creators`/`tags` modes). Pagination is followed automatically up to this cap. Default 100, max 10,000. |
| `maxConcurrency` | integer | `model-detail` mode — how many model IDs to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default (not required for this endpoint — it's Civitai's own official public API — kept for production robustness). |

## Output

**Models / model-detail mode** — one record per model, full upstream shape (truncated here for readability):
```json
{
  "_input": "4201",
  "_source": "S1-api",
  "_scrapedAt": "2026-08-25T19:03:40Z",
  "id": 4201,
  "name": "Realistic Vision V6.0 B1",
  "type": "Checkpoint",
  "stats": { "downloadCount": 2304987, "thumbsUpCount": 52805 },
  "creator": { "username": "SG_161222", "image": "https://image.civitai.com/..." },
  "tags": ["photorealistic", "anatomical", "realistic"],
  "modelVersions": [
    {
      "id": 501240,
      "name": "V5.1 Hyper (VAE)",
      "baseModel": "SD 1.5 Hyper",
      "files": [
        {
          "name": "realisticVisionV60B1_v51HyperVAE.safetensors",
          "sizeKB": 2082642.47,
          "hashes": { "SHA256": "F47E942AD4C30D863AD7F53CB60145FFCD2118845DFA705CE8BD6B42E90C4A13" },
          "downloadUrl": "https://civitai.com/api/download/models/501240?fileId=418901",
          "virusScanResult": "Success"
        }
      ]
    }
  ]
}
```

**Images mode** — one record per image:
```json
{
  "_input": "4201",
  "_source": "S1-api",
  "_scrapedAt": "2026-08-25T19:06:38Z",
  "id": 12221839,
  "url": "https://image.civitai.com/.../original=true/....jpeg",
  "width": 1024,
  "height": 1536,
  "nsfwLevel": "None",
  "stats": { "likeCount": 346, "heartCount": 113 },
  "meta": null,
  "username": "SG_161222",
  "baseModel": "SD 1.5 Hyper"
}
```

**Creators / Tags mode:**
```json
{ "_input": "civ", "_source": "S1-api", "_scrapedAt": "...", "username": "civitdiff", "modelCount": 1, "link": "https://civitai.com/api/v1/models?username=civitdiff" }
```
```json
{ "_input": "anime", "_source": "S1-api", "_scrapedAt": "...", "name": "anime", "link": "https://civitai.com/api/v1/models?tag=anime" }
```

A record with `_error` instead of the fields above means that item could not be processed (for example, `"_error": "model_not_found"` for a model ID that doesn't exist).

## Known limits

- **`meta` (prompt, sampler, seed, steps, CFG scale) is always `null`.** This is Civitai's own privacy choice on the public API, not a bug — it holds true even for images whose own internal flags say a prompt exists. There is no public, unauthenticated way to retrieve it.
- **`images` mode filtered by `modelId` is automatically fixed.** Civitai's own API silently returns zero results for `/images?modelId=X` even on the most popular models on the platform — a genuine upstream defect (images are actually indexed by model *version*, not model). This actor detects a `modelId` input and transparently resolves it to that model's version IDs first, so you always get correct results. If you already know the exact model version you want, pass `modelVersionId` directly for a faster, single-request lookup.
