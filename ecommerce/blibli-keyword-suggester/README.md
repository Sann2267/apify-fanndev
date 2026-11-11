# Blibli Search Keyword Autocomplete & Suggester

Harvest the keyword suggestions [Blibli](https://www.blibli.com)'s search box
shows shoppers — expanded far beyond the handful you can see — each with a
**measured count of competing products** so you know which terms you can
actually rank for.

For merchants optimising product titles and marketplace SEO.

No login, no API key. HTTP-only — no browser.

## ⚠️ About "search volume"

**Blibli does not publish search volume, and this actor does not invent one.**

Measured: across 65 autocomplete suggestions from 10 prefixes, every
volume-shaped field (`productCount`, `count`) was null and `dsScore` was
`0.0` on every row. No endpoint in the search family exposes a volume,
impression count or frequency.

What you get instead — both real, both measured:

- **`competingProducts`** — how many products Blibli actually returns for the
  keyword. This is the number that decides whether you can rank: `laptop`
  returns 58,744 competing products, `laptop gaming` 6,639, `laptop advan`
  644.
- **`suggestPosition`** — rank inside Blibli's own autocomplete ordering,
  which comes from their relevance model. An ordinal popularity signal, not
  a volume.

If you need true search volume, no public Blibli surface provides it.

## What it does that the search box doesn't

Typing a seed into Blibli shows you ~6 suggestions. This actor appends every
letter a–z to the seed and collects each different slice of the suggestion
index:

| Query | Keywords found |
| --- | --- |
| `laptop` typed into the search box | **6** |
| this actor, `expansionMode: alphabet` | **147** |

31 of those 147 don't even start with "laptop" — `asus laptop`,
`backpack laptop`, `tote bag laptop`, `tas laptop jinjing`. Those are the
terms you'd never have thought to check.

## Output

```json
{
  "keyword": "laptop hp official store",
  "seedKeyword": "laptop",
  "source": "autocomplete",
  "sourcePrefix": null,
  "suggestPosition": 5,
  "competingProducts": 335,
  "competitionLevel": "LOW",
  "wordCount": 4,
  "isLongTail": true,
  "containsSeed": true,
  "searchUrl": "https://www.blibli.com/cari/laptop%20hp%20official%20store"
}
```

Sort the dataset by `competingProducts` ascending and the top rows are your
SEO opportunities — real demand (Blibli suggests them) with little
competition:

```
Anti Aging Diskon hingga 60%        3 products   LOW    (curated)
sepatu pria kanky                  42 products   LOW    (related)
isolasi listrik nitto              85 products   LOW    (trending)
laptop hp official store          335 products   LOW    (autocomplete)
```

## Input

```json
{
  "seedKeywords": ["laptop", "sepatu pria"],
  "expansionMode": "alphabet",
  "includeCompetition": true,
  "includeTrending": true
}
```

| Field | Description |
| --- | --- |
| `seedKeywords` | Terms to expand |
| `expansionMode` | `none` (1 req/seed), **`alphabet`** (27), `alphanumeric` (37), `related` (2), `full` (38) |
| `includeCompetition` | Measure competing products per keyword — 1 extra request each |
| `includeTrending` | Add marketplace-wide trending searches (works with no seeds) |
| `includeCurated` | Add Blibli's curated promo keywords, with their promo URLs |
| `minWordCount` | Set to `3` to harvest long-tail terms only |
| `maxKeywordsPerSeed`, `maxConcurrency` | Volume and politeness |
| `proxyConfiguration` | Residential + country `ID` recommended |

## Four keyword sources in one run

| `source` | What it is |
| --- | --- |
| `autocomplete` | Suggestions for the bare seed |
| `autocomplete-expansion` | Suggestions for seed + a suffix (`sourcePrefix` records which) |
| `related-search` | Blibli's "refine your search" terms |
| `trending` | Marketplace-wide trending searches |
| `curated` | Editorially promoted keywords, with `promoUrl` |

Everything is deduplicated across sources and seeds in a single run.

## Known limits

- **No search volume** — see above.
- `competitionLevel` bands are a convenience from this actor, not a Blibli
  metric; `competingProducts` is the real number.
- Autocomplete reflects what an anonymous Indonesian visitor sees — the right
  baseline for marketplace SEO, but a logged-in shopper's box may differ.
- Suggestions are in Indonesian, as shoppers type them.
- With `alphabet` + competition on, a single seed is ~27 + N requests; use a
  residential proxy for large seed lists.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the endpoint map, the
`searchTermPrefix` parameter trap, the endpoints that return 500, and the
measured expansion figures.
