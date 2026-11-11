# Hugging Face Scraper

Search and extract Hugging Face model, dataset, and Space listings, full repo details (files, config, card metadata), and user/organization profiles — no account or API key needed.

## Why use this actor

- One actor covers all of Hugging Face's public surface: search models/datasets/Spaces, pull full download-ready details for a specific repo, and look up user or organization profiles
- Full repo detail includes the complete file manifest (`siblings`), parsed model/dataset card metadata, config, and (for Spaces) the live demo URL
- No account, login, or API key required — this actor talks to Hugging Face's own official public REST API
- Automatic retries on temporary network hiccups, including respecting the platform's own rate-limit headers
- Robust pagination — automatically follows the platform's `Link`-header pagination up to the limit you set
- Honest about limits: a nonexistent repo returns a clear `_error` record (even though the platform itself replies with a slightly confusing HTTP 401 instead of 404 — this actor normalizes that), and user vs. organization lookups are resolved automatically

## How it works

Pick a `mode`:
1. **`models`** / **`datasets`** / **`spaces`** — search/browse with filters for query text, author, tags, task (models), library (models), sort order.
2. **`model-detail`** / **`dataset-detail`** / **`space-detail`** — fetch full detail (every file, card metadata, config) for one or more specific repo IDs.
3. **`creator`** — look up a user or organization profile (auto-detects which type).

## Input

**Search models:**
```json
{
  "mode": "models",
  "search": "llama",
  "pipelineTag": "text-generation",
  "sort": "downloads",
  "maxItems": 50
}
```

**Model detail (by ID):**
```json
{
  "mode": "model-detail",
  "modelIds": ["google-bert/bert-base-uncased", "meta-llama/Llama-3.1-8B-Instruct"]
}
```

**Datasets / Spaces:**
```json
{ "mode": "datasets", "search": "squad", "maxItems": 20 }
```
```json
{ "mode": "spaces", "author": "huggingface", "sort": "likes", "maxItems": 20 }
```

**Creator profile:**
```json
{ "mode": "creator", "username": "openai" }
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"models"` (default), `"model-detail"`, `"datasets"`, `"dataset-detail"`, `"spaces"`, `"space-detail"`, or `"creator"`. |
| `search` | string | `models`/`datasets`/`spaces` mode — free-text search term. |
| `author` | string | `models`/`datasets`/`spaces` mode — exact username/organization filter. |
| `filter` | array | `models`/`datasets`/`spaces` mode — tag filters, e.g. `["license:mit", "pytorch"]`. |
| `pipelineTag` | string | `models` mode — task filter, e.g. `"text-generation"`. |
| `library` | string | `models` mode — e.g. `"transformers"`, `"diffusers"`. |
| `sort` | string | `downloads`, `likes`, `createdAt`, `lastModified`, or `trendingScore`. |
| `direction` | string | `"-1"` (descending, default) or `"1"` (ascending — only supported for `createdAt`, see Known limits). |
| `modelId` / `modelIds` | string / array | `model-detail` mode — repo ID(s) in `namespace/name` form. |
| `datasetId` / `datasetIds` | string / array | `dataset-detail` mode. |
| `spaceId` / `spaceIds` | string / array | `space-detail` mode. |
| `username` / `usernames` | string / array | `creator` mode. |
| `accountType` | string | `creator` mode — `"auto"` (default), `"user"`, or `"organization"`. |
| `maxItems` | integer | Max results for list modes. Default 100, max 10,000. |
| `maxConcurrency` | integer | Detail/creator modes — how many IDs to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default (not required — Hugging Face's own official public API — kept for production robustness). |

## Output

**Models / model-detail mode** — one record per model (truncated for readability):
```json
{
  "_input": "google-bert/bert-base-uncased",
  "_source": "S1-api",
  "_scrapedAt": "2026-08-25T19:50:00Z",
  "id": "google-bert/bert-base-uncased",
  "author": "google-bert",
  "pipeline_tag": "fill-mask",
  "library_name": "transformers",
  "downloads": 93831528,
  "likes": 2740,
  "tags": ["transformers", "pytorch", "bert", "fill-mask", "license:apache-2.0"],
  "cardData": { "language": "en", "license": "apache-2.0" },
  "siblings": [{ "rfilename": "config.json" }, { "rfilename": "pytorch_model.bin" }]
}
```

**Datasets / Spaces mode** — analogous shape, upstream fields passed through as-is.

**Creator mode:**
```json
{
  "_input": "openai",
  "_source": "S1-api-organization",
  "_scrapedAt": "2026-08-25T19:50:00Z",
  "fullname": "OpenAI",
  "name": "openai",
  "isVerified": true,
  "numModels": 39,
  "numDatasets": 16,
  "numSpaces": 6,
  "numFollowers": 40018
}
```

A record with `_error` instead of the fields above means that item could not be processed (for example, `"_error": "model_not_found"` for a repo ID that doesn't exist).

## Known limits

- **Ascending sort only works for `createdAt`.** Requesting `direction: "1"` with any other `sort` value returns a structured `_error: "invalid_request"` record — this is a genuine Hugging Face platform restriction (confirmed live across all 5 sort fields), not a bug in this actor.
- **List-mode results don't include the full file list.** Only `model-detail`/`dataset-detail`/`space-detail` mode returns the complete `siblings` file manifest for a repo.
- **Gated/private repos** return their public metadata only (this actor never logs in, by design) — download-restricted file contents are out of scope.
