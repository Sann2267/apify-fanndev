# AEO Bing Rank Tracker

Track whether your brand/domain appears in Bing search results — Answer-Engine Optimization rank tracking, no account or API key needed.

## Why use this actor

- No account, login, or API key required
- Honest results: a genuine bot-detection block is reported as a clear `_error`, never disguised as "brand not found"
- Built-in guidance to avoid a real, confirmed Bing quirk that silently ruins results for naively-phrased queries (see Known limits — this alone can be the difference between a correct report and a false "you're not ranking" scare)
- Every result's real destination URL is used for domain-matching, not Bing's tracking-redirect wrapper (Bing wraps every link in a `bing.com/ck/a?...` redirect; this actor decodes it)

## ⚠️ Important: phrase queries as natural questions, not "best X" keywords

This was found and confirmed during development, not a stylistic suggestion: Bing returns a completely irrelevant **decoy** result set for queries starting with a bare superlative.

| Query | Result |
|---|---|
| `"best crm software for small business"` | ❌ Irrelevant — pages about the standalone word "best" (a dictionary, BestBuy, an electronics retailer) |
| `"which crm software is best for small business"` | ✅ Correct — real CRM pages, Salesforce found ranking on page 1 |
| `"crm software for small business"` | ✅ Also correct |

Always phrase `query`/`queries` the way you'd actually ask a person or an AI assistant.

## Input

```json
{
  "queries": ["which crm software is best for small business", "what's a good alternative to salesforce"],
  "targetDomain": "hubspot.com"
}
```

| Field | Type | Description |
|---|---|---|
| `query` / `queries` | string / array | Natural-question phrasing (see above). |
| `targetDomain` | string | Your domain to check for. |
| `maxConcurrency` | integer | How many queries to run in parallel. Default 3. |
| `proxyConfiguration` | object | Apify Proxy settings. Not required — confirmed working without a proxy. |

## Output

One record per query:
```json
{
  "_input": "which crm software is best for small business",
  "_source": "S1-html",
  "query": "which crm software is best for small business",
  "targetDomain": "salesforce.com",
  "targetFound": true,
  "targetRank": 8,
  "resultCount": 10,
  "results": [
    { "rank": 1, "title": "...", "url": "https://qontak.com/...", "domain": "qontak.com", "isTarget": false },
    { "rank": 8, "title": "What Is a CRM? | Salesforce IN", "url": "https://www.salesforce.com/in/crm/what-is-crm/", "domain": "salesforce.com", "isTarget": true }
  ]
}
```

A record with `_error` instead means that lookup couldn't complete (e.g. `"_error": "blocked_or_transient"` for a network-level issue).

## Known limits

- **Results are capped at the top 10.** Confirmed during development that neither the `count` parameter nor real next-page links return additional/different results through this access path — for AEO purposes this is a reasonable scope anyway, since answer engines draw citations overwhelmingly from top-ranking pages.
- **Leading "best"/"top" queries get decoy results** — see the warning above. This is the single most important thing to get right when using this actor.
- **This actor tracks Bing's traditional organic results, not an AI-generated answer box.** Two "generative engine" surfaces (Google AI Overview, DuckDuckGo AI Chat) were thoroughly investigated during development and both turned out to require executing real JavaScript to access — Google's results are now entirely client-side-rendered (confirmed via Google's own `<noscript>` "enable JavaScript" fallback, present even on a clean, non-blocked response), and DuckDuckGo's anonymous chat API now gates access behind a proof-of-work-style JS challenge with an undocumented, very recently changed protocol. Both are genuine architectural walls, not solvable with better headers or proxies — see `CRAWLING_METHOD.md` for the full evidence trail from both investigations. This actor ships the one surface that's honestly, reliably deliverable via HTTP-only access.
