---
name: deploying-actors
description: "Deploy actors to Apify with the apify CLI (apify push -f), including bulk-pushing many actors from PowerShell. Use when publishing or updating one or many actors on the Apify platform."
---

# Skill: Deploying Actors to Apify

## Push a single actor

```bash
cd actors/<name>
apify validate-schema   # confirms input_schema.json, output_schema.json, AND actor_output_links.json are all valid
apify push -f
```

The `-f` flag force-pushes without confirmation prompts. The Apify CLI version is 1.2.1 - older syntax.

## Push all 15 article actors (PowerShell)

```powershell
$actors = @("aljazeera-scraper","apnews-scraper","bbc-scraper","cnbc-scraper",
            "forbes-scraper","fortune-scraper","ft-scraper","guardian-scraper",
            "head-news-scraper","msn-scraper","nytimes-scraper","reuters-scraper",
            "scmp-scraper","techcrunch-scraper","upi-scraper","yahoo-finance-scraper")

foreach ($a in $actors) {
    Write-Host "Pushing $a..."
    Push-Location "actors\$a"
    apify push -f
    Pop-Location
}
```

## Test an actor on Apify

```bash
# Article mode
apify call bbc-scraper -i '{"url": "https://www.bbc.com/news/articles/example"}'

# Latest headlines mode
apify call reuters-scraper -i '{"mode": "latest", "limit": 5}'
```

## Stress test workflow

1. Call each actor in `latest` mode to get fresh URLs
2. Feed each URL back to the same actor in `article` mode
3. Check success rate (no `error` field in output)

```powershell
# Step 1: Get fresh URLs
apify call bbc-scraper -i '{"mode": "latest", "limit": 10}' > bbc_latest.json

# Step 2: Extract articles from fresh URLs (use apify call with urls array)
# Parse bbc_latest.json to get URLs, then:
apify call bbc-scraper -i '{"urls": ["url1", "url2", ...]}'
```

## Build versioning

Each push creates a new build. Check builds at:
`https://console.apify.com/actors/<actor-id>/builds`

Current version: update the `version` field in `.actor/actor.json` before pushing.

## Common deployment issues

- **"output" field error in actor.json / empty KV Store shown instead of Dataset** → This happens
  when the top-level `"output": "..."` key points at a file shaped for the *dataset* schema instead
  of the `actorOutputSchemaVersion` shape (missing `"type"` on each property, no
  `actorOutputSchemaVersion` key). The fix is not to remove `"output"` — it's to give it its own
  correctly-shaped file. Every actor wires **two** separate schema files:
  `"storages": {"dataset": "./output_schema.json"}` (the real table view) and
  `"output": "./actor_output_links.json"` (the Console's quick-link button, template
  `{{links.apiDefaultDatasetUrl}}/items`). See
  [`skills/actor-output-schema/SKILL.md`](../actor-output-schema/SKILL.md) for both templates; run
  `apify validate-schema` before pushing to confirm all three schemas are valid.
- **Build fails** → Check `requirements.txt` for invalid package names or version conflicts
- **Actor runs but no output** → Check dataset (not KV store); use `Actor.push_data()` not KV set
- **primp not found** → Ensure `primp>=1.2.0` is in `requirements.txt` for reuters/forbes
