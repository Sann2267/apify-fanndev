# Skool/Whop Community Analyzer

Extract member count, subscription price, and an estimated monthly revenue signal from any public Skool or Whop community — built for finding creators worth pitching for sponsorship or collaboration.

## Why use this actor

- **No account or login required** — works on fully public community pages.
- **One combined tool for both platforms** — point it at a Skool community or a Whop community with the same actor, just switch the mode.
- **Built-in revenue estimate** — combines member count and disclosed subscription price into an `estimatedMonthlyRevenue` figure, so you don't have to do the math yourself across a list of leads.
- **Stable JSON output** ready to drop into a spreadsheet, CRM, or outreach pipeline.
- **Automatic retries** on temporary network hiccups — no babysitting long lists of URLs.
- **Bulk-friendly** — feed it a list of community URLs and get one row back per community.

## How it works

1. You give it one or more Skool or Whop community URLs (or bare slugs) and pick the platform.
2. It visits each community's public page and reads the member count, name, description, and (when the creator has made it public) the subscription price.
3. For Whop communities, it also checks the community's pricing page to find the plan price.
4. It multiplies member count by the monthly price to produce an estimated monthly revenue figure, and tells you exactly how that number was derived.
5. Every community comes back as one clean row of data — no manual copy-pasting from community pages.

## Input

**Skool mode**

```json
{
  "mode": "skool",
  "urls": [
    "https://www.skool.com/freegroup",
    "https://www.skool.com/skool-100"
  ],
  "maxConcurrency": 4,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

**Whop mode**

```json
{
  "mode": "whop",
  "url": "https://whop.com/kaizen",
  "maxConcurrency": 4,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"skool"` or `"whop"` — which platform the URL(s) belong to. |
| `url` | string | A single community URL or bare slug. |
| `urls` | array | Multiple community URLs/slugs to process in one run (same platform). |
| `maxConcurrency` | integer | How many communities to fetch in parallel. Default `4`. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default and recommended, especially for Whop mode. |

## Output

**Skool example** (`freegroup`, real output, truncated):

```json
{
  "_input": "https://www.skool.com/freegroup",
  "_source": "S1-nextdata",
  "_scrapedAt": "2026-08-28T19:37:19Z",
  "platform": "skool",
  "communityName": "AI Automation (A-Z)",
  "url": "https://www.skool.com/freegroup",
  "memberCount": 164801,
  "isPaid": true,
  "subscriptionPrice": {
    "amountUsd": 7.0,
    "currency": "usd",
    "interval": "month",
    "monthlyEquivalentUsd": 7.0
  },
  "estimatedMonthlyRevenue": 1153607.0,
  "estimatedMonthlyRevenueBasis": "memberCount (164801) x monthly price ($7.00) -- upper-bound estimate; memberCount includes free/trial members on both platforms, so treat this as a triage signal, not verified revenue.",
  "raw": { "... full community details (description, admin count, post count, etc.)": "..." }
}
```

**Whop example** (`kaizen`, real output, truncated):

```json
{
  "_input": "kaizen",
  "_source": "S1-html-rsc-scan",
  "_scrapedAt": "2026-08-28T19:41:08Z",
  "platform": "whop",
  "communityName": "Kaizen",
  "url": "https://whop.com/kaizen",
  "memberCount": 4541,
  "isPaid": true,
  "subscriptionPrice": {
    "monthlyEquivalentUsd": 183.33,
    "currency": "usd"
  },
  "estimatedMonthlyRevenue": 832501.53,
  "estimatedMonthlyRevenueBasis": "memberCount (4541) x monthly price ($183.33) -- upper-bound estimate; memberCount includes free/trial members on both platforms, so treat this as a triage signal, not verified revenue.",
  "raw": { "... plans, access passes, review count, etc.": "..." }
}
```

| Field | Type | Description |
|---|---|---|
| `platform` | string | `"skool"` or `"whop"`. |
| `communityName` | string | The community's display name. |
| `url` | string | The community's canonical URL. |
| `memberCount` | integer | Total members shown on the community's page. This includes free/trial members, not just paying subscribers. |
| `isPaid` | boolean | Whether the community charges for access. |
| `subscriptionPrice` | object | The disclosed monthly-equivalent price, when the creator has made it publicly visible. Some paid communities don't show their price without logging in — in that case this is `null`. |
| `estimatedMonthlyRevenue` | number | `memberCount × monthly price` — a triage estimate, not verified revenue. `null` when price isn't disclosed. |
| `estimatedMonthlyRevenueBasis` | string | Plain-language explanation of how the estimate was calculated, or why it's unavailable. |
| `raw` | object | The full set of community details captured (description, admin/post counts, review ratings, plan options, etc). |

## Notes

- Neither platform publishes actual creator revenue — `estimatedMonthlyRevenue` is a member-count-times-price estimate meant for quickly ranking and shortlisting leads, not an exact figure.
- Some paid Skool communities don't disclose their price to logged-out visitors. When that happens, member count is still returned, but the price and revenue estimate come back as `null`.
- For best reliability, keep Residential proxy enabled (on by default) — especially in Whop mode.
