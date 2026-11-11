# Tech Stack Detector — Website Technology Lookup

Give it a list of domains. Get back what each one runs — store platform, CMS, framework, analytics, marketing, chat, payments, CDN — **and the exact header, cookie or script tag that proved it**.

87 technologies across 13 categories. One request per site. No login, no API key, no proxy.

## Why the evidence matters

Most stack lookups hand you a label and ask you to trust it. This one shows its working:

```json
{
  "technology": "Shopify",
  "confidence": "confirmed",
  "evidence": ["cookie _shopify_y", "asset host cdn.shopify.com", "html contains \"Shopify.theme\""]
}
```

Every detection carries `confidence`:

- **`confirmed`** — proven by something that cannot match by coincidence: a vendor cookie, a vendor CDN hostname, a vendor-specific header.
- **`likely`** — consistent with the technology but shared with others, or self-declared.

So when a result surprises you, you can check it in ten seconds instead of re-running a second tool to see whether you believe the first one.

## The two jobs it does

**Prospecting — find the companies on a stack you sell into.**

```json
{
  "domains": ["allbirds.com", "gymshark.com", "notion.com"],
  "requireTechnology": ["Shopify"]
}
```

**Gap-finding — find the companies missing the tool you sell.** This is the higher-value one, and it is two fields:

```json
{
  "domains": ["...500 store domains..."],
  "requireTechnology": ["Shopify"],
  "excludeTechnology": ["Klaviyo", "Omnisend", "Mailchimp", "Attentive"]
}
```

That returns Shopify stores with no email platform detected — a qualified list, not a scraped one.

## What you get per site

| Field | What it tells you |
|---|---|
| `technologies` / `technologiesConfirmed` | Everything detected, and the subset that is proven |
| `stackEcommerce`, `stackCMS`, `stackFramework`, … | One column per category, so the CSV filters cleanly |
| `detections` | Per technology: confidence, signal types, exact evidence strings |
| `reachable` / `_error` | Whether the domain answered, and why not if it did not |
| `redirected` / `finalDomain` | Whether you are looking at the stack of a *different* host |
| `technologyCount` / `confirmedCount` | Quick quality score for the row |

The `RUN_SUMMARY` record ranks technologies across the whole list with a site count and share — useful on its own for a market snapshot ("what share of these 400 DTC brands run Klaviyo").

## Categories covered

Ecommerce · CMS · Framework · Hosting/CDN · Analytics · Tag Manager · Marketing · Support · Payments · Reviews · Search · Monitoring · Experimentation

Coverage is deliberately narrow. Wappalyzer tracks about 2,000 technologies and most of them never appear in a lead filter; this table covers the ones buyers actually sort on, which keeps every fingerprint maintained rather than inherited.

## Limits worth knowing

- **Homepage only.** Fingerprinting is done on the homepage plus, optionally, `/robots.txt`. A tool that only loads on a checkout or pricing page will not be seen. This is what keeps it one request per domain.
- **No JavaScript execution.** Technologies injected by a tag manager at runtime rather than referenced in the HTML are invisible. `Google Tag Manager` will be detected; what it loads afterwards may not be.
- **Absence is not proof of absence.** A site that does not show Klaviyo may still use it. Read `excludeTechnology` results as "no evidence found", which for prospecting is usually the right signal anyway.
- **Redirects change the subject.** If `example.com` redirects to `shop.example.net`, the stack reported is the destination's. `redirected` and `finalDomain` tell you when this happened.
- **`likely` is not `confirmed`.** Filters match on technology name regardless of confidence, so check `confidence` before acting on a thin result.

## Failures are data

A domain that does not resolve is a finding about that prospect, not a broken run. Errors are classified rather than retried into the ground:

`dns_failure` · `tls_failure` · `timeout` · `connection_failed` · `http_error` · `unreachable`

DNS and TLS failures return immediately — they will not fix themselves on retry. Sites that answer only over plain HTTP are retried there automatically, so older business sites stay in the dataset instead of being written off.

## Cost and proxy

One request per domain, two with `checkRobotsTxt`. **Leave the proxy off by default** — there is no single target site here, so there is nothing to be blocked by. Turn it on only when scanning thousands of domains and you want the requests spread across IPs.

`concurrency` can go high (up to 30) because every request goes to a different server.

## Output shape

Every record carries `_input`, `_source`, `_scrapedAt` and `recordType`. `recordType` is `SITE` per domain, `RUN_SUMMARY` once per run, `ERROR` for a domain that could not be fetched. Three dataset views: **Overview**, **Marketing stack** and **Infrastructure**. Optional `exportFormats` writes JSON, NDJSON, CSV or XLSX to the key-value store.

Pairs with `shopify-store-analyzer`: use this to find the Shopify stores in a list, then run that one for the catalogue.

## Development

```bash
pip install -r requirements.txt
python -m src            # needs an Apify runtime
python test_local.py     # table integrity, matching edge cases, live fixtures
```

`CRAWLING_METHOD.md` documents the signal types and why each one is weighted the way it is.
