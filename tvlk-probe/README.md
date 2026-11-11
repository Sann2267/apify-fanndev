# Traveloka Surface Probe

Diagnostic probe for Traveloka's internal APIs. It mints an AWS WAF token, boots a session through `/api/v2/user/context/web`, then hits a fixed set of hotel, experience, flight and ground-transport endpoints to record whether each one is reachable, WAF-challenged, or captcha-gated when called from an Apify residential proxy.

## What it does

For each round it runs:

1. Resolves an exit IP through the selected proxy mode.
2. Mints an `aws-waf-token` via a headless challenge solver.
3. Boots a session and probes the `/en-id/hotel` page for a captcha-delivery response.
4. Calls each of these endpoints and records status, `x-amzn-waf-action`, response size and a snippet:
   - `hotel-searchList`, `hotel-staticSearch`
   - `xperience-searchV2`, `xperience-detail`
   - `hotel-autocomplete`
   - `pps-multileg`
   - `ugc-getReviews`
   - `flight-price-table`

## Input

| Field | Type | Description |
|---|---|---|
| `proxyMode` | string | `residential-id`, `residential-sg`, or `none`. |
| `rounds` | integer | Number of independent proxy sessions to probe with (1-5). |

## Output

One dataset record per round with the WAF/session diagnostics and a `checks` object keyed by endpoint name. See the Output tab for the full field reference.

## Use case

Intended for internal recon: deciding whether Traveloka's hotel-search and Xperience-search surfaces are reachable well enough to justify building a dedicated scraper actor against them.
