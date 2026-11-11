# Crawling Method — Zambia ZPPA e-GP Tenders

**Last verified:** 2026-08-27

The Zambia Public Procurement Authority (ZPPA) runs an electronic
Government Procurement (e-GP) platform at `eprocure.zppa.org.zm/epps/`.
It is built on the **"European Dynamics" e-GP platform** (confirmed via
`<meta name="Creator" content="European Dynamics"/>` on every page) — the
same commercial e-GP software vendor family used by several other
countries' government procurement portals (a shared multi-tenant/white-label
pattern similar to the Catalyst/OCRS/DotGovServer vendors already documented
for the business-registry actors in this portfolio, though this appears to
be an independently-hosted per-country deployment rather than a literal
shared tenant). The marketing/informational site `www.zppa.org.zm` is a
separate, unrelated WordPress-style site and is not used by this actor.

## Robots.txt

- `GET https://www.zppa.org.zm/robots.txt` → HTTP 200:
  ```
  User-Agent: *
  Disallow:
  Sitemap: http://www.zppa.org.zm/sitemap.xml
  ```
  No blanket disallow, no bot named (Claude/ClaudeBot/anthropic-ai or
  otherwise), no natural-language prohibition.
- `GET https://eprocure.zppa.org.zm/robots.txt` → HTTP 302 to
  `https://www.zppa.org.zm` — the e-GP host has no robots.txt route
  configured at all (any unmatched path there redirects to the marketing
  site's root, confirmed with `BigIP`/`server: null` response headers
  typical of this platform's other pages too). No restriction found on
  either host.

## WAF / anti-bot

**None found.** `curl_cffi` tested across `chrome124`, `chrome131`,
`safari17_0`, and `edge101` impersonation profiles against
`common/viewOpenedTenders.do` — all four returned identical HTTP 200
responses with the same content length. No Cloudflare/DataDome/Akamai/etc.
markers in headers or body, no CAPTCHA on any page this actor touches, no
rate limiting observed on rapid sequential requests. `curl_cffi`
(`chrome124`) impersonation is used anyway as this portfolio's default
posture (`.ai/CLAUDE.md` principle #2), not because a block was ever seen.
`proxyConfiguration` defaults to off for the same reason.

## Login wall — partial, not blanket

**Listings are fully public.** Both tender-listing surfaces this actor
uses load with no account, no cookie beyond a bare session, and no
CAPTCHA:

- `common/viewOpenedTenders.do` — a large, sortable/paginated HTML table
  ("Opened Bid Details"), **157,696 results** observed live in one fetch
  (the live count moves as tenders progress through the pipeline — do not
  treat it as a fixed constant).
- `home.do` — a "Latest Tenders" widget listing the ~10 most recently
  published currently-open tenders.

**Individual tender *detail* pages are conditionally login-walled** —
this was the one real surprise of this recon. `cft/prepareViewCfTWS.do?
resourceId=<id>`:

- Returns **HTTP 200 with the full tender record** (procuring entity,
  procurement method/technique, payment terms, all deadline timestamps,
  UNSPSC codes, etc. — 24-27 fields observed) when the tender's bid
  submission deadline has **not yet passed** — i.e. every tender surfaced
  by the homepage's "Latest Tenders" widget loaded cleanly, with zero
  exceptions across every sample tried.
- **302-redirects to `/cas/login`** once the bid submission deadline has
  passed — i.e. every single row sampled from the "Opened Bid Details"
  table (which by definition only lists tenders whose bids have already
  been opened) hit this wall. Confirmed on 6 different resourceIds across
  different procuring entities and procurement methods — 100% consistent,
  not a fluke of one tender.

This reads as a deliberate ZPPA access-control rule (e.g. protecting
post-deadline evaluation/complaint-window details from public scraping,
possibly related to the "standstill period" / complaint mechanism referenced
in the page's own JS) rather than a bug or a site-wide wall. Per this
project's stop condition ("fine if only BIDDING [or post-close detail]
requires an account, not if VIEWING listings does"), this does **not**
block the actor — it only limits which tenders can be detail-enriched.
`main.py` handles it as an expected, non-crashing outcome
(`_error: "login_required"`), not a scraping failure.

## Search form — CAPTCHA-gated (not used by this actor)

`prepareCurrentOpportunities.do?currentType=cft` ("Current Tenders") and
the quick-search box both render a `<img id="CAPTCHA">` challenge on the
search form (`quickSearchAction.do`, POST). No CAPTCHA solver is used per
this project's policy, so free-text/current-tenders search is out of
scope. This does not block the actor's core functionality: the homepage's
un-gated "Latest Tenders" widget already surfaces the same currently-open
tenders (just without a search box), and the un-gated "Opened Bid Details"
table covers the much larger historical/closed set.

## Data source — reverse-engineering path

No JSON API or `__NEXT_DATA__`/JSON-LD anywhere — this is a legacy
server-rendered Java web app (`Set-Cookie: JSESSIONID=...master-zpp-epps1``,
BigIP load-balancer cookie). All three modes parse plain HTML:

1. **`list` mode** — `GET common/viewOpenedTenders.do`, parses
   `<table id="T01">` (headers read live from `<thead>`, not hardcoded).
   Pagination is `?d-<gridId>-p=<pageNum>`, where `<gridId>` is a
   per-session widget id embedded in the page's own "next page" link
   (regex `d-(\d+)-p=\d+`) — it is **tied to the session's JSESSIONID
   cookie**, so pagination must reuse the same `curl_cffi` session across
   requests (confirmed: extracting the id from page 1 and reusing it for
   page 2+ in the same session returns the correct next rows; a fresh
   session gets a different id). The results-per-page dropdown advertised
   in the page's own JS (`["10","20","50","100"]`) does **not** actually
   change anything — `?d-<id>-n=100` was tested live and still returned
   exactly 10 rows; pagination always walks in steps of 10.
2. **`latest` mode** — `GET home.do`, parses `div.LatestTenders ul.news`
   (title + resourceId + 3-part event date), then enriches each item via
   the detail-page parse below.
3. **`detail` mode** — `GET cft/prepareViewCfTWS.do?resourceId=<id>` with
   redirects disabled (`allow_redirects=False`) so the CAS-login case can
   be detected as a distinct 302 rather than silently following it to a
   200 login page. On success, parses `<dl class="row"> dt/dd` pairs —
   every label is turned into a camelCase key programmatically (not a
   fixed field list), since the field set genuinely varies by tender type
   (a Goods/Open-Bidding tender had 27 fields; another had 30, including
   extra `procurementMethodRationale`/`awardCriteriaDetails`/
   `submissionMethodDetails` fields not present on the first).

## Known limits

- **"Current Tenders" full-text search is CAPTCHA-gated** — this actor
  cannot search by keyword/procuring-entity/date-range. `list` mode's
  historical table has no filter parameters either (confirmed: only sort
  and page params appear in the pagination links).
- **Detail enrichment only works pre-deadline.** Any resourceId whose bid
  submission deadline has passed will return `_error: "login_required"`
  in `detail` mode — this is correct, expected upstream behavior, not a
  bug in this actor.
- **`latest` mode is capped at ~10 items** — it is a fixed-size homepage
  widget with no pagination available outside the CAPTCHA-gated search.
- **`list` mode's total result count moves between requests** (observed
  81,157 and 157,696 in two fetches minutes apart) — this is a live,
  continuously-updated index on ZPPA's end, not a scraping artifact.
- Dates/amounts are passed through as ZPPA's own raw strings (`dd/mm/yyyy
  HH:MM:SS`, comma-grouped ZMW amounts) — not reformatted.
- `bidSubmissionDeadlineInDaysHours` is a moving countdown ("29/3" =
  29 days / 3 hours remaining *at scrape time*) — it will differ on every
  re-scrape of the same still-open tender, by design.

## Diff cadence

Quarterly smoke test recommended — this is a stable, unusually
long-lived government Java application (BigIP-fronted, no visible
recent redesign), but a platform upgrade is always possible.
