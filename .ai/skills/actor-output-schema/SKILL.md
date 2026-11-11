---
name: actor-output-schema
description: "Define and wire an Apify Actor dataset output schema (.actor/output_schema.json + storages.dataset in actor.json) so the Output tab renders a readable table instead of raw JSON. Use when scaffolding a new actor (bake it in from the start) or auditing/backfilling an actor that was pushed without one."
---

# Skill: Actor Output Schema

Every actor in this portfolio pushes heterogeneous, raw-passthrough records (see
[`conventions/dataset-envelope.md`](../../conventions/dataset-envelope.md)). Apify's Console
"Output" tab shows raw JSON unless the actor ships a **dataset schema** describing which fields
exist and which columns to show. This is what this project calls the actor's "output schema."

## The two Apify features — do not confuse them

Apify has two unrelated things you can put under `.actor/`. Both are used in this portfolio, wired
to **two differently-named files** so they never collide:

| Feature | Purpose | File (this project's convention) | Referenced via |
| --- | --- | --- | --- |
| **Dataset schema** | Documents dataset item fields + defines the Output-tab **table view** (the actual data columns) | `.actor/output_schema.json` | `"storages": {"dataset": "./output_schema.json"}` in `actor.json` |
| **Actor output schema** (`actorOutputSchemaVersion`) | Renders a quick-link button ("Open results") on the Console Publication tab, pointing at a URL template | `.actor/actor_output_links.json` | top-level `"output": "./actor_output_links.json"` in `actor.json` |

Every actor gets **both** — the Console's Publication checklist ("Dataset schema" / "Output schema"
rows) expects both green. The Dataset schema is what actually renders the data table; the Output
schema is just a convenience link to `{{links.apiDefaultDatasetUrl}}/items` and has zero effect on
how data is presented.

**Historical pitfall (now resolved):** an earlier attempt wired the *dataset*-shaped
`output_schema.json` file through the top-level `"output"` key (mismatched shape — no
`actorOutputSchemaVersion`, no `type` on properties) and that broke the Output tab, showing an empty
KV store. The fix is not to avoid the feature — it's to give each schema its **own correctly-shaped
file** as shown below. See [`skills/deploying-actors/SKILL.md`](../deploying-actors/SKILL.md#common-deployment-issues).

## File: `.actor/output_schema.json`

**⚠️ Apify enforces this schema server-side on every `push_data()` call, batch-wide.** This is not
documentation-only. If one item in a batch fails validation — a listed field has the wrong `type`,
or the item carries a field not listed in `properties` while `additionalProperties` isn't `true` —
**the API rejects the entire batch with HTTP 400 and the actor crashes** (`InvalidRequestError:
Schema validation failed`), not just that one record. Confirmed live: `berlingske-scraper` crashed
in production because `headline` was declared `"type": "string"` but that CMS's `__NEXT_DATA__`
actually emits it as an array of `TextNode` blocks, *and* the record carried several fields
(`externalIds`, `articleType`, `modificationDate`, …) never listed in `properties` at all.

Because every actor in this portfolio does **raw passthrough of upstream JSON** (see
[`conventions/dataset-envelope.md`](../../conventions/dataset-envelope.md)) — the exact field set
and shape depends on the site's CMS and can include nested objects/arrays that vary by article — the
schema must stay permissive:

- **`"additionalProperties": true`** on the `fields` object schema, always. Without it, any field
  you didn't think to list crashes the run the day it shows up.
- **No `"type"` on any non-envelope property.** Only `_input`, `_source`, `_scrapedAt` (always
  code-generated strings, never null) and `_error`/`_errorDetail` (always strings when present) are
  safe to type-constrain. Every content field (`headline`, `author`, `image`, `articleBody`, dates,
  booleans, arrays…) can legitimately be `None`/missing on some articles, or a different shape than
  expected on a CMS quirk you haven't seen yet — declaring `"type": "string"` on a field that is
  sometimes `null` crashes the run exactly like the wrong-shape case above. Keep `title` +
  `description` only; that's still enough for the Output-tab column labels and docs.

```json
{
    "actorSpecification": 1,
    "fields": {
        "type": "object",
        "schemaVersion": 1,
        "title": "Article / latest-headline record",
        "description": "One sentence: what the two record shapes are (article-mode vs latest-mode) and that upstream JSON-LD/ANS is passed through close to verbatim, so extra fields may appear beyond those listed.",
        "properties": {
            "_input":     {"type": "string",  "title": "Input",        "description": "The exact input value (URL, or 'latest'/'latest:<section>') that produced this record."},
            "_source":    {"type": "string",  "title": "Source strategy", "description": "Which extraction strategy emitted this record (e.g. S1-jsonld, S2-rss)."},
            "_scrapedAt": {"type": "string",  "format": "date-time", "title": "Scraped at", "description": "UTC ISO 8601 timestamp when this record was scraped."},
            "_error":       {"type": "string", "title": "Error",        "description": "Present only on failed extractions -- the error kind."},
            "_errorDetail": {"type": "string", "title": "Error detail", "description": "Free-form diagnostic detail, present only alongside _error."},

            "headline":     {"title": "Headline",     "description": "Article headline."},
            "articleBody":  {"title": "Article body", "description": "Full article text."},
            "datePublished":{"title": "Date published", "description": "ISO 8601 publish date."},
            "author":       {"title": "Author",       "description": "Byline name(s) -- shape varies by site (plain string, or a raw-passthrough object/array on JSON-LD spread actors)."}
        },
        "additionalProperties": true
    },
    "views": {
        "overview": {
            "title": "Overview",
            "description": "Key columns across both article and latest-headline records.",
            "transformation": {
                "fields": ["_input", "_source", "_scrapedAt", "headline", "title", "link", "datePublished", "pubDate", "author", "_error"]
            },
            "display": {"component": "table"}
        }
    }
}
```

**Every field this actor's `extractor.py` can put on a record should have a documentation entry
(title + description, no type)** — walk `extract_article`, `extract_error`, and
`extract_rss_items`/`extract_sitemap_items`, and list every key each one returns, so the Output tab
has useful column labels. Listing them is for documentation/column-labeling only now, not
validation — `additionalProperties: true` means anything unlisted still comes through.

`views.overview.transformation.fields` is just an ordered column list — mixing article-mode column
names (`headline`, `datePublished`) and latest-mode column names (`title`, `pubDate`) in one view is
fine; rows missing a column just render blank.

**Before trusting a schema, run the actor for real** (`apify call` against a live URL, or at least
`apify run` locally against `extractor.py`'s actual return values) and eyeball the record shape —
don't assume typical schema.org typing holds for a CMS you haven't actually seen output from.

## File: `.actor/actor_output_links.json`

```json
{
    "actorOutputSchemaVersion": 1,
    "title": "YourPlatform Scraper Results",
    "properties": {
        "results": {
            "type": "string",
            "title": "Dataset results",
            "template": "{{links.apiDefaultDatasetUrl}}/items",
            "description": "All scraped article / latest-headline records produced by this run."
        }
    }
}
```

`"type": "string"` on every property is **required** — omitting it fails `apify validate-schema`
with `must have required property 'type' at /properties/<name>`. This file is identical in shape
across actors; only `title` needs to match the actor's own title.

## Wiring: `.actor/actor.json`

Add (don't replace) `storages` and `output`:

```json
{
    "actorSpecification": 1,
    "name": "yourplatform-scraper",
    "version": "0.1",
    "buildTag": "latest",
    "title": "YourPlatform Scraper",
    "description": "...",
    "dockerfile": "./Dockerfile",
    "input": "./input_schema.json",
    "storages": {
        "dataset": "./output_schema.json"
    },
    "output": "./actor_output_links.json"
}
```

## Validate before pushing

```bash
cd actors/<name>
apify validate-schema
```

Expect all three: `Success: Input schema is valid.`, `Success: Dataset schema is valid.`, and
`Success: Output schema is valid.` A schema change only takes effect on Apify's Console after a
fresh `apify push -f` — editing the local file alone does nothing for an already-deployed actor.

**`apify validate-schema` only checks that the schema *file itself* is well-formed JSON Schema — it
does NOT check your schema against real scraped data.** A schema that validates fine can still crash
every run once real items are pushed (that's exactly what happened with `berlingske-scraper`). After
`apify push -f`, run at least one real call before calling it done:

```bash
apify call --input '{"mode":"article","url":"<a real article URL>"}'
```

Watch for `Run: SUCCEEDED` (not just `Apify push result: SUCCEEDED`, which only means the Docker
build worked) — `push` succeeding tells you nothing about whether real records pass the schema.

## When to use

- **New actor (bake it in):** do both files as part of [`skills/adding-new-actor/SKILL.md`](../adding-new-actor/SKILL.md)
  step 4, *before* the first `apify push` — the Dataset schema using the real field names your
  `extractor.py` returns (not a copy-pasted generic template), the Output-links file from the
  boilerplate above with just the title swapped.
- **Existing pushed actor missing either file:** for the Dataset schema, read `src/extractor.py` in
  full and enumerate every field every `extract_*` function returns; for the Output-links file, copy
  the boilerplate. Wire both into `actor.json`, validate, then `apify push -f` to make it live.

## See also

- [`conventions/dataset-envelope.md`](../../conventions/dataset-envelope.md) — the `_input`/`_source`/`_scrapedAt` envelope every record follows
- [`playbooks/new-scraper-bootstrap.md`](../../playbooks/new-scraper-bootstrap.md) — Step 11
- [`playbooks/apify-deploy.md`](../../playbooks/apify-deploy.md) — `actor.json` essentials
- [`skills/deploying-actors/SKILL.md`](../deploying-actors/SKILL.md) — push workflow + the `output` vs `storages.dataset` pitfall
