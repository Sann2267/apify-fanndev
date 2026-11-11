# Crawling method

Recon date: 2026-09-20.

## Surface

```
GET https://{domain}/          # always
GET https://{domain}/robots.txt # optional, checkRobotsTxt
```

**There is no target site.** Every request goes to a different company's server, which is the structural advantage of this actor: no WAF to defeat, no DOM layout to track, no IP gate, no endpoint that can be withdrawn. Nothing any one vendor does can take the surface away.

Verified live across `allbirds.com`, `notion.com`, `basecamp.com`, `gymshark.com`, `wordpress.org`, `stripe.com`, `shopify.com`, `hubspot.com`, `squarespace.com`, `wix.com` — all 200, no gating of any kind.

The consequence is that a failure is **data about the prospect**, not a signal that something is wrong on our side. Errors are classified (`dns_failure`, `tls_failure`, `timeout`, `connection_failed`, `http_error`, `unreachable`) and returned. DNS and TLS failures short-circuit rather than burning retries — neither fixes itself on a second attempt. Sites that answer only on port 80 are retried over plain HTTP so older business sites stay analysable.

## Signal types

Five, ordered by how much they prove:

| Type | Source | Why it is weighted this way |
|---|---|---|
| `header` | response header, optionally with a value substring | Set by the server or edge. Not something a page author fakes by accident. |
| `cookie` | cookie name the site sets | Same: emitted by the platform itself. `_shopify_y` means Shopify. |
| `generator` | `<meta name="generator">` | Self-declared, therefore removable — but never wrong when present. |
| `host` | hostname in `<script src>` / `<link href>` / `<iframe src>` | The workhorse. Most SaaS is embedded from a vendor CDN. |
| `html` | substring in the markup | Weakest, so these are chosen to be strings nothing else plausibly contains (`__NEXT_DATA__`, `Shopify.theme`). |

Plus `robots` for the optional second request, always `likely` — a disallow path is suggestive, never conclusive.

### Host matching is exact or subdomain, never substring

A naive `"shop.app" in url` check matches `myshop.apple.com`. Host signals therefore match only `host == needle` or `host.endswith("." + needle)`. A fingerprint carrying a path (`cdn.jsdelivr.net/npm/algoliasearch`) falls back to a substring search over the joined asset URLs, which is safe because the path makes it specific.

Relative asset references are skipped entirely: they are same-origin by definition and say nothing about which vendors a site uses. The page's own hostname is excluded for the same reason.

## Confidence

Per **signal**, not per technology, because the same technology can be proven or merely suggested depending on what turned up:

- `confirmed` — specific to the vendor and essentially unforgeable by coincidence.
- `likely` — shared with others, self-declared, or a generic path fragment.

A technology is reported `confirmed` if **any** confirmed signal matched, otherwise `likely`. Every match carries its evidence string, so a result is auditable rather than something to trust.

## What is deliberately not done

- **No JavaScript execution.** Anything injected at runtime by a tag manager is invisible. Executing pages would multiply cost per domain by an order of magnitude and break the one-request-per-site economics that make this actor cheap.
- **No deep crawl.** Homepage only. A tool present solely on a checkout page is missed; accepting that is what keeps this at 1–2 requests per domain.
- **No 2,000-technology table.** Coverage is 87 technologies across 13 categories, chosen because they appear in lead filters. A large inherited table rots; a small one stays correct.

## Performance

`MAX_HTML_BYTES` caps analysis at 2 MB per page. Homepages routinely inline several MB of application state, and every fingerprint worth having appears in the head or the asset references near it, so the cap bounds memory per concurrent fetch without costing detections.

Evidence is indexed once per page (hosts, cookies, headers, generators, asset blob) and all 167 signals are then matched against that index, rather than re-scanning the HTML 167 times.

## Live fixtures

`test_local.py` asserts these, so a vendor changing a CDN hostname fails the suite instead of quietly emptying the dataset:

| Site | Must detect |
|---|---|
| `allbirds.com` | Shopify, Cloudflare |
| `notion.com` | Next.js, Vercel, Contentful |
| `wordpress.org` | WordPress |
| `squarespace.com` | Squarespace |
| `hubspot.com` | HubSpot, HubSpot CMS |

It also asserts the negative cases that matter: `shop.app` must **not** match `myshop.apple.com`, relative assets must not match a host signal, and a header signal with a value must not match a different value.
