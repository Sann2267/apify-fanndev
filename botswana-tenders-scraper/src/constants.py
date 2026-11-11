"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27, independently re-verified in this session -- not
copied blind from the prior session's Babak 25 market-research note):

Botswana's central procurement portal, PPRA's "Integrated Procurement
Management System" (`ipms.ppadb.co.bw`), was correctly skipped by a prior
session: its "Tender Search" link is dead (commented out in the homepage
HTML), `robots.txt` explicitly disallows `/search` and `/docdetails`, and
its AJAX search endpoint returns `200 OK` with an empty body (server-side
session gate). `www.ppadb.co.bw` (PPADB's separate marketing/legacy site)
was also probed directly in this session and found completely unreachable
(connection timeout on every attempt) -- the whole `ppadb.co.bw` domain
family appears to be down, not merely search-gated.

Since Botswana decentralized public procurement to individual ministries
around 2022, several ministries publish tenders directly on their own
websites. This actor covers the two that were independently confirmed
public, unblocked, and carrying real (if sparse) tender data:

## Ministry of Finance -- `www.finance.gov.bw` (CONFIRMED WORKING, primary)

Legacy Joomla site. `robots.txt` is the stock unmodified Joomla template
(`Disallow: /administrator/`, `/cache/`, `/components/`, etc. -- standard
CMS-internals-only paths). No blanket `Disallow: /`, no Claude/ClaudeBot/
anthropic-ai mention anywhere, no natural-language crawl prohibition.
Server is plain `Apache/2.4.25 (Debian)` + `PHP/7.1.26` -- no Cloudflare/
Akamai/DataDome/WAF headers of any kind. Confirmed working with a **plain
stdlib `urllib` request and no TLS impersonation at all** (`curl_cffi`
chrome124 is used anyway for portfolio consistency and residential-proxy
compatibility, not because it's load-bearing here). No login wall: the
"Procurement" nav item (category id 38) and every article under it render
in plain HTML with no auth check.

The nav path is Home -> Procurement -> category id=38, which has a clean
RSS feed:

    GET https://www.finance.gov.bw/index.php?option=com_content&view=category&layout=blog&id=38&Itemid=246&format=feed&type=rss

This is the actor's primary source. As of recon, it carries **9 items
total** spanning 19 Jan 2021 to 3 Oct 2024 -- tender notices, addenda, an
expression-of-interest, and adjudication-decision announcements. Each
`<item>` has a clean `title`, `link` (the article's own page -- which,
confirmed by fetching several, carries NO additional text beyond what's
already in the RSS `description`; the "article" is just a wrapper around
one PDF link), `pubDate` (RFC-822), `category`, and a `description` whose
CDATA HTML embeds the actual tender-document PDF URL in an `<a href>`.

**Correction to the prior session's summary**: the Babak 25 market-research
note describes this source as having "real July 2026 tender/addendum
postings." Independent re-verification in this session found the RSS
feed's own `pubDate` values top out at **3 Oct 2024** -- nothing from 2025
or 2026 has been posted to this category as of this recon date (27 Aug
2026), a ~22-month gap. The site itself is NOT abandoned (its homepage
carries unrelated 2026-dated content in other categories, e.g. an
"UNCLAIMED FUNDS JULY 2026-2027" notice), so this looks like a genuinely
slow-moving but still-live procurement page, not a dead one -- reported
here plainly rather than repeating the unverified "July 2026" claim.

## Ministry of Health & Wellness -- `www.moh.gov.bw` (CONFIRMED WORKING, thin/secondary)

Static HTML site (no CMS admin paths visible, no `robots.txt` at all --
`GET /robots.txt` returns a plain nginx 404, which this actor treats as
"nothing disallowed" per standard robots.txt semantics). No login wall.
Server is `nginx/1.17.8`, no WAF markers.

    GET https://www.moh.gov.bw/opportunitiestenders.html

carries one plain HTML `<table>` under "Tenders": a header row
(Tender / Closing date) plus one data row per open tender. At recon time
this held exactly **one** tender, dated 2017 (closing 31 Aug 2017) --
included here honestly as the real, if very stale, content of this page;
the parser is written generically against the table's row structure so it
will pick up additional rows automatically if the ministry ever adds new
ones, rather than being hardcoded to today's single row.

The page also links to "MOH-MTC Tender Adjudication Decisions" at
`http://www.ppadb.co.bw/health_13.html` -- passed through as a raw
reference URL on each record, but NOT fetched by this actor: `ppadb.co.bw`
(the same domain family as the skipped central PPRA portal) timed out on
every direct connection attempt during this session's recon, consistent
with the PPRA skip finding that this domain family is down, not merely
gated.

## Other ministries investigated and excluded

- `www.gov.bw/tenders` (the unified central government portal, Drupal-
  based) -- confirmed live, clean `robots.txt` (standard Drupal boilerplate,
  no blanket disallow), no login wall, no WAF. But its tenders page
  literally reads "There are currently no tenders available." with no
  underlying Views/listing markup to verify a parser against. Excluded --
  not a block, just nothing real to scrape or test a parser against right
  now (see CRAWLING_METHOD.md).
- `moa.gov.bw` / `www.moa.gov.bw` (Agriculture), `mti.gov.bw` /
  `www.mti.gov.bw` (Trade and Industry, since renamed Ministry of Trade and
  Entrepreneurship), `moe.gov.bw` (Education), `mlg.gov.bw` (Local
  Government), `mid.gov.bw` (Infrastructure and Housing), `mineral.gov.bw`
  (Minerals and Energy), `cms1.gov.bw` -- all either failed DNS resolution
  or timed out on every connection attempt. These ministries appear to have
  been consolidated onto the unified `gov.bw` portal (which itself has no
  tenders published, see above) with their standalone legacy domains
  decommissioned.
- `trade.gov.bw` -- alive (no robots.txt, 404), but is the Ministry of
  Trade & Entrepreneurship's business-licensing eServices portal (company
  registration, import permits, liquor/trade licences), not a tenders
  publication -- out of scope, not a tender source at all.
"""

FINANCE_BASE_URL = "https://www.finance.gov.bw"
FINANCE_RSS_URL = (
    f"{FINANCE_BASE_URL}/index.php?option=com_content&view=category"
    "&layout=blog&id=38&Itemid=246&format=feed&type=rss"
)

HEALTH_BASE_URL = "https://www.moh.gov.bw"
HEALTH_TENDERS_URL = f"{HEALTH_BASE_URL}/opportunitiestenders.html"

TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.0
