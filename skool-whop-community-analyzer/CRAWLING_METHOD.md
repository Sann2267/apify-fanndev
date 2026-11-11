# Crawling Method — Skool/Whop Community Analyzer

Internal engineering doc. See `README.md` for the user-facing Store listing.

## Skool (`www.skool.com`)

**WAF: none found.** CloudFront fronts the domain but no challenge was
ever triggered -- every `/<slug>/about` request in recon and in the
shipped client used a plain unauthenticated `curl_cffi` request
(`chrome124` impersonation, no warmup, no cookie jar) and got a clean
200. `robots.txt` only disallows `/*/--/*`.

**Data source:** `<script id="__NEXT_DATA__" type="application/json">`
on the `/<slug>/about` page. The community object lives at
`props.pageProps.currentGroup`, and the fields this actor uses
(`totalMembers`, `displayName`, `membership`, `displayPrice`, etc.) are
all under `currentGroup.metadata`, NOT top-level on `currentGroup` --
confirmed by dumping the real key set (`src/skool.py:parse_display_price`
depends on this).

**Not-found detection:** Skool does not 404 an unknown/removed/private
slug -- it 307/308-redirects `/<slug>/about` to `/signup`. Detected via
`r.url` after redirects are followed (curl_cffi follows redirects by
default; confirmed empirically, see git history for the throwaway probe
script). A truly nonexistent slug (never registered) does return a
clean 404 directly.

**Price disclosure is inconsistent across paid communities** -- this
was the single biggest recon surprise and is worth re-reading before
"fixing" the code to always expect a price:
- `skool.com/freegroup` (AI Automation A-Z, membership=1/paid, 164,801
  members): `metadata.displayPrice` = `'{"currency":"usd","amount":700,
  "recurring_interval":"month"}'` -- a JSON-encoded *string*, not a
  nested object. $7/month.
- `skool.com/thetradingcafe` (membership=1/paid, 104,568 members): zero
  `displayPrice` field in the unauthenticated payload at all -- also no
  `membershipModel` key, no visible `$` amount anywhere in the rendered
  HTML. This community simply does not disclose price to guests.
- Conclusion: `parse_display_price` returns `None` when the field is
  absent, and that is treated as "not disclosed" (Category 1, not an
  error) -- NOT a parse failure. Do not assume every paid community
  will have a price in the output.
- A competing Store actor (`crustapi/skool-community-scraper`)
  advertises "monthly/annual price" as a standard extracted field. Recon
  here suggests that's true only for some communities, not all -- their
  listing may be optimistic, or they may have a fallback (e.g. an
  authenticated fetch, which is out of scope here per the no-login
  constraint) this actor doesn't have.

**Not built:** a "discover/trending feed" list mode. `skool.com/discovery`
does return 200 with ~30 communities' worth of embedded data per page
(confirmed live, 1000 communities across ~34 pages per a third-party
site's methodology) -- this would be a strong candidate for a future
`mode: "discover"` addition (bulk lead-sourcing without needing a
pre-existing list of URLs), but was out of scope for this build; only
per-URL lookup was requested.

## Whop (`whop.com`)

**WAF: Cloudflare, Bot Management active** (`__cf_bm` cookie set on every
response; `Content-Security-Policy-Report-Only` names a
`cf-csp-endpoint`). This is a materially higher block-risk surface than
Skool's plain CloudFront. In recon and in the shipped client, every
storefront/plan page tested still returned a clean 200 to a plain
unauthenticated `chrome124`-impersonated request with no JS challenge
triggered -- but this is the platform to watch first if the actor starts
seeing `blocked_or_transient` errors at higher run volumes. Residential
proxy is the default in `input_schema.json` for this reason.
`robots.txt` only disallows `/api/` and `/discover/search/*`, neither of
which this actor touches.

**Data source: NOT a clean JSON blob.** Whop's Next.js app-router
frontend streams `self.__next_f.push([1, "..."])` React Server
Components (RSC) chunks using unquoted-key object-literal syntax (e.g.
`memberCount:4541`, not `"memberCount":4541`) -- this is not valid JSON
and can't be `json.loads`'d. `src/whop.py` extracts known fields with
targeted regexes against the raw response text instead. This is
materially more fragile than Skool's `__NEXT_DATA__` parse: a Whop
frontend refactor that reorders these object-literal keys will silently
degrade extraction (fields come back `None`/empty rather than raising),
since "field not found" is the expected/common case for a paid
community that simply doesn't have a matching access pass, not
necessarily a break. If Whop ever exposes a documented JSON API, prefer
it over this approach.

**Two-hop crawl required for price.** The storefront page
(`whop.com/<slug>/`) has `memberCount`, `reviewsAverage`,
`publishedReviewsCount`, and a `publicCompany` object with an
`accessPasses` list (each with its own `route`) -- but NO price. Price
lives on each access pass's own plan/checkout page, at
**`whop.com/<companySlug>/<accessPassRoute>/`** (nested under the
company's own route -- a bare `whop.com/<accessPassRoute>/` looked like
it worked in one ad hoc recon probe but does NOT reliably return plan
data; always nest). Confirmed fields there: `billingPeriod` (days, or
`null`), `rawInitialPrice`, `rawRenewalPrice`, `planType`
(`"renewal"` | `"one_time"`). Monthly-equivalent price =
`rawRenewalPrice / (billingPeriod / 30)` for `renewal`-type plans only;
`one_time` plans don't feed the MRR estimate.

**Known cross-listing artifact (important, do not "fix" without new
recon):** a single access-pass's plan page has been observed to also
render a *sibling* access pass's plan/price inside what looks like an
upsell/comparison widget -- confirmed live on `kaizen`: fetching
`whop.com/kaizen/kaizen-free/` returned the SAME `$550/90-day` plan that
actually belongs to `whop.com/kaizen/kaizen-pro/`. Because of this,
`WhopClient.get_community` only uses the **first-listed access pass**
(`company["primaryAccessPassRoute"]`) to compute the single representative
`subscriptionPrice`/`estimatedMonthlyRevenue` in `run_whop()` -- the full
(deduped) plan list across all fetched access passes is still returned
under `raw.plans` for transparency, but is NOT reliable for reconstructing
a per-tier price breakdown without further work. A single page's RSC
payload was also observed to repeat the same plan object more than once
(pricing card + checkout summary widgets) -- deduped in
`WhopClient.get_community` on `(route, billingPeriodDays, rawInitialPrice,
rawRenewalPrice, planType)`.

**Real revenue (GMV) not found.** A competing Store actor
(`fatihtahta/whop-scraper`) advertises "USD GMV" as an extracted field.
Recon here (regex search for `gmv`/`totalRevenue`/`salesVolume`/
`revenueGenerated` across the full storefront RSC payload) found nothing
-- it's likely served from an internal marketplace-ranking API this
actor doesn't call, not the public storefront page. Not implemented;
`estimatedMonthlyRevenue` here is a `memberCount x price` estimate only,
same caveat as Skool.

**Not-found detection:** clean 404 for a nonexistent slug (confirmed
live), unlike Skool's redirect-to-signup pattern.

## Competitive landscape (as of 2026-08-29 recon)

Both platforms already have Apify Store scrapers: Skool has at least
`crustapi/skool-community-scraper`, `dz_omar/skool-scraper-pro`,
`leadstack/skool-community-finder`, `sourabhbgp/skool-scraper`; Whop has
at least `fatihtahta/whop-scraper`. None found combine both platforms in
one tool with an explicit MRR-estimate calculation framed for
sponsorship/lead-gen -- that combination, not raw data access, is this
actor's differentiator. See memory file
`skool_whop_community_analyzer_recon.md` for the full recon writeup this
doc was built from.

## Store category & monetization (configured 2026-08-29)

**Category:** `LEAD_GENERATION` (primary) + `SOCIAL_MEDIA` (secondary) --
matches how nearly every genuinely comparable competitor (Skool and
Whop alike) categorizes itself; the actor's own framing (finding
creators worth a sponsorship/collaboration pitch) is squarely lead-gen.

**Competitive pricing research** (`api-search-actors.py --query "skool"`
/ `"whop"`, live Algolia data, 2026-08-29):

Skool comparables (per-record PPE, `pricingPerEvent`/dataset-item unit):
`crustapi/skool-community-scraper` $0.003-0.0037 tiered (closest scope
match -- pricing/members/course stats), `sourabhbgp/skool-scraper`
$0.003 flat, `futurizerush/skool-group-scraper` $0.005 flat, and the
closest **feature** match, `goat255/skool-scraper-goat`
("...estimated MRR and ARR, member and post counts... Built-in MRR and
price filters" -- i.e. the same core idea as this actor's Skool mode,
already shipped) at $0.007 (FREE tier) down to $0.004 (DIAMOND) per
community, plus a small actor-start fee.

Whop comparables: `fatihtahta/whop-scraper` $0.001 flat (cheapest,
broad scope incl. pricing/company/metrics), `crawlerbros/whop-scraper`
$0.001-0.002 tiered (near-identical field set to this actor's Whop mode:
id/title/route/member count/reviews/creator pitch/owner), and the
closest **feature** match, `ahmed_jasarevic/whop-community-scraper`
("member counts, ratings, prices, and monetization details... creator
economy research and outreach") at $0.005 flat.

**Conclusion:** `goat255/skool-scraper-goat` already ships this actor's
core "MRR estimate" idea for Skool alone, and `ahmed_jasarevic/whop-community-scraper`
ships the equivalent concept for Whop alone -- so the real differentiator
here is combining both platforms in one tool with one consistent output
shape, not the MRR-estimate idea itself. Priced near the upper end of
the observed per-record range (matching the MRR/monetization-focused
comparables rather than the cheap raw-scrape crowd) to reflect that
Whop mode's 2-hop crawl (storefront + up to 5 plan pages) costs more to
run than the single-page competitors.

**Configured via `apify api PUT actors/{id}`** (categories in one call;
`pricingInfos` as a flat first entry then an appended tiered second
entry, per the platform's append-only-history + first-entry-must-be-flat
quirks): single event `apify-default-dataset-item`, tiered
FREE $0.006 / BRONZE $0.0055 / SILVER $0.005 / GOLD $0.0045 /
PLATINUM $0.004 / DIAMOND $0.0035 per community record. No separate
`apify-actor-start` fee -- kept to one event for cost clarity, matching
`crustapi/skool-community-scraper`'s simpler pattern over the
multi-event ones. Not yet published to the Store (`isPublic` still
`false`) -- publishing is a separate mutation, subject to a 5
actor-publications/account/day platform limit, left for a separate
explicit request.

## Envelope / `_source` tags

- `S1-nextdata` -- Skool, `__NEXT_DATA__` JSON parse.
- `S1-html-rsc-scan` -- Whop, regex extraction from the RSC payload.
- `none` -- failure records (see `_error` for the reason:
  `not_found_or_private` / `not_found` / `unexpected_shape` /
  `blocked_or_transient` / `empty_input`).
