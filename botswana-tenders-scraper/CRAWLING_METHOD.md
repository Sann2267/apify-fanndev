# Crawling Method — Botswana Ministry Tender Pages

**Last verified:** 2026-08-27

## Background: why this actor exists

A prior session (Babak 25, `ACTOR_MARKET_RESEARCHER_NEW.md`) correctly
**skipped** Botswana's central procurement portal, PPRA's "Integrated
Procurement Management System" (`ipms.ppadb.co.bw`): its "Tender Search"
link is dead (commented out in the homepage HTML, not merely CSS-hidden),
`robots.txt` explicitly disallows `/search` and `/docdetails`, and the
AJAX search endpoint (reverse-engineered) returns `200 OK` with an empty
body — a server-side session gate, not a client-side trick. That session
also flagged that Botswana decentralized procurement publication to
individual ministries around 2022, with `finance.gov.bw` spotted as a
promising lead worth checking in a follow-up session. This actor is that
follow-up.

## Independent re-verification (this session), not a blind trust of the prior lead

Everything below was re-checked directly with `curl_cffi` in this session
rather than assumed from the prior summary.

### `www.ppadb.co.bw` (separate from `ipms.ppadb.co.bw`) — also unreachable

Before trusting the decentralization lead, this session also re-probed the
main `ppadb.co.bw` marketing/legacy domain directly (distinct from the
`ipms.` subdomain that hosts the search system). Every connection attempt
(`robots.txt`, homepage, a specific referenced subpage) timed out — the
whole `ppadb.co.bw` domain family appears to be down at the network level,
not merely gated. This matters later: the Ministry of Health's own tenders
page links out to a `ppadb.co.bw` URL for "Tender Adjudication Decisions,"
which this actor deliberately does not attempt to fetch (see below).

## Ministry of Finance — `www.finance.gov.bw` (CONFIRMED WORKING, primary source)

### robots.txt

```
User-agent: *
Disallow: /administrator/
Disallow: /cache/
Disallow: /cli/
Disallow: /components/
Disallow: /images/
Disallow: /includes/
Disallow: /installation/
Disallow: /language/
Disallow: /libraries/
Disallow: /logs/
Disallow: /media/
Disallow: /modules/
Disallow: /plugins/
Disallow: /templates/
Disallow: /tmp/
```

This is the **stock, unmodified Joomla installer template** for
`robots.txt` — every disallowed path is a CMS-internals folder
(admin panel, cache, PHP includes, etc.), not content. No blanket
`Disallow: /`, no `Claude`/`ClaudeBot`/`anthropic-ai` mention in any
group, no natural-language crawl prohibition anywhere in the file.
Note: `/images/` is technically disallowed, which is where tender PDFs
live (`/images/Procurement/*.pdf`) — this actor extracts and reports the
PDF *URLs* (present in the page's own RSS feed as plain link text, not
fetched separately) but never issues a `GET` against `/images/*` itself,
so it stays inside the disallow scope.

### No anti-bot gate found

```
$ curl -sI https://www.finance.gov.bw/
server: Apache/2.4.25 (Debian)
x-powered-by: PHP/7.1.26
```

Confirmed with a **plain stdlib `urllib.request` call and zero TLS
impersonation** — `HTTP 200`, full real content, byte-identical page
length to the `curl_cffi chrome124` version. No Cloudflare/Akamai/
DataDome/WAF headers anywhere in the response. This actor still uses
`curl_cffi` (chrome124 profile) for portfolio consistency and because a
residential proxy in front of it still negotiates its own TLS fingerprint,
but it is not load-bearing here.

### No login wall for viewing

The "Procurement" nav item and every article beneath it render in plain
HTML with no auth check of any kind. Botswana's Public Procurement Act
requires open publication of procurement notices; this ministry's own site
reflects that with zero gating on the read path.

### Finding the real listing (the nav link looked stale; the category wasn't)

The homepage's "Procurement" nav link (`Itemid=246&option=com_content&view=article&id=110&catid=38`) resolves to a single **static article**
that itself hasn't been touched since 2021 — easy to mistake for "this
ministry stopped publishing tenders in 2021." The real, actively-updated
content lives one level up, at the **category** view for the same
`catid=38`:

```
GET https://www.finance.gov.bw/index.php?option=com_content&view=category&id=38&Itemid=246
```

This is a standard Joomla "category blog" layout — several full articles
followed by a "More Articles ..." link list. Confirmed via this page that
newer procurement content exists (a 2023 Permanent Secretary decision, a
2022 mobile-banking EOI, two 2022 tender addenda) beyond what the stale
nav-link article shows.

### The real source: this category's own RSS feed

Joomla auto-generates an RSS feed for every category. For catid=38:

```
GET https://www.finance.gov.bw/index.php?option=com_content&view=category&layout=blog&id=38&Itemid=246&format=feed&type=rss
```

This is a clean `<rss version="2.0">` document with one `<item>` per
notice: `title`, `link` (the article permalink), `pubDate` (RFC-822,
`+0200` = Botswana's UTC+2, no DST), `category` (always "Procurement"),
and a `description` CDATA blob containing one `<a href="...pdf">` — the
actual tender-document link. Confirmed this feed carries **all 9** items
that exist in this category (cross-checked against the category page's
own "4 shown + 4 in More Articles" = 8, plus the newest one not yet in
that cached count = 9) — nothing is being paginated away.

**Why RSS over HTML scraping here** (per this portfolio's general
"JSON-LD > structured feed > HTML scraping" priority): each article's own
detail page (`view=article&id=<n>`) was checked directly (ids 431, 505,
619, etc.) and confirmed to carry **zero additional text** beyond what the
RSS `description` already has — the Joomla "article" is nothing but a
wrapper around one PDF link. Fetching each detail page individually would
be 9 extra requests for zero extra data; the RSS feed alone is the
complete, sufficient source.

### Gotcha: `lastBuildDate` is "now," `pubDate` per item is real — don't confuse them

The feed's channel-level `<lastBuildDate>` reflects the moment the feed
was generated (i.e. whenever this actor's request hit the server) and will
always look current. The actually meaningful date is each `<item>`'s own
`<pubDate>` — this actor parses and reports that per record, not the
channel-level timestamp.

### Correction to the prior session's summary

The Babak 25 market-research note (`ACTOR_MARKET_RESEARCHER_NEW.md`)
describes this ministry as having "data Juli 2026 nyata" (real July 2026
data). Independent re-verification in this session found the RSS feed's
own `pubDate` values top out at **3 Oct 2024** — nothing newer has been
posted to the Procurement category as of this recon date (27 Aug 2026), a
roughly 22-month gap. This is reported plainly rather than silently
repeating the unverified "July 2026" claim; it does not change the
conclusion that this source is real, public, and worth building against —
it just means "currently quiet," not "currently active with 2026 postings."
The site overall is not abandoned (its homepage links unrelated 2026-dated
content in other categories, e.g. "UNCLAIMED FUNDS JULY 2026-2027" under a
different `catid`), so the quiet Procurement feed looks like upstream's own
posting cadence rather than a scraping gap.

## Ministry of Health & Wellness — `www.moh.gov.bw` (CONFIRMED WORKING, thin secondary source)

### robots.txt: none at all

```
$ curl -sI https://www.moh.gov.bw/robots.txt
HTTP/1.1 404 Not Found
Server: nginx/1.17.8
```

A plain nginx 404, not a redirect to a login page or a WAF challenge page.
Per standard robots.txt semantics, a missing file means nothing is
disallowed. No Claude/AI-crawler restriction exists because no robots.txt
exists.

### No anti-bot gate, no login wall

`nginx/1.17.8` serving static HTML, no WAF response headers. The tenders
page renders fully in plain HTML with no auth check.

### The listing: one plain HTML table, no API

```
GET https://www.moh.gov.bw/opportunitiestenders.html
```

A static page with exactly one `<table>`: a header row (`Tender` /
`Closing date`) followed by one `<tr>` per open tender. At recon time this
held **exactly one** row — a 2017 tender (`Tender Ref No:
MTC\MOHW\CLS\SER/10511/0707/2017`, closing 31 Aug 2017). This is reported
honestly as the real, current (if very stale) content of the page rather
than treated as a parsing failure. The parser (`parse_health_tenders` in
`src/extractor.py`) walks `table.find_all("tr")[1:]` generically — it does
not hardcode "exactly one row," so it will pick up additional rows the
ministry may add in the future without code changes.

### Gotcha: the tender-reference `<u>` tag vs. the row's full text

The tender cell packs the reference number, a `<br><br>`, and the PDF link
+ title into one `<td>` with no separating markup beyond whitespace. A
naive `get_text()` regex-search for "Tender Ref No:" against the *whole*
cell's text greedily swallows the title text too (both are joined by a
single space once HTML is stripped). Fixed by anchoring the regex against
just the `<u>` tag's own text (`tender_cell.find("u")`), which upstream
uses to wrap only the reference number — leaving the `<a>` tag's own text
as the clean title.

### Gotcha: `adjudication_decisions_url` points to dead infrastructure

The page also links "MOH-MTC Tender Adjudication Decisions" to
`http://www.ppadb.co.bw/health_13.html`. This actor extracts and passes
through that URL as a raw data field but **does not fetch it** —
`ppadb.co.bw` timed out on every connection attempt during this session's
recon (see the top-level note above), consistent with the central PPRA
portal being generally down, not merely gated. Attempting to fetch it
would only add multi-second timeouts per run for no data; the URL itself
is still useful as a reference for a human reader checking it later by
other means.

## Ministries investigated and excluded

| Domain | Result |
|---|---|
| `www.gov.bw/tenders` (unified central portal, Drupal) | Live, clean standard-Drupal `robots.txt`, no login wall, no WAF — but the page literally reads "There are currently no tenders available," with no underlying Views/listing markup visible to build or verify a parser against. Excluded: not a block, just nothing real to scrape right now. Revisit if it's ever populated. |
| `moa.gov.bw` / `www.moa.gov.bw` (Agriculture) | `www.moa.gov.bw` connection timed out on every attempt (host up, not responding); bare `moa.gov.bw` fails DNS resolution entirely. |
| `mti.gov.bw` / `www.mti.gov.bw` (Trade and Industry, since renamed Ministry of Trade and Entrepreneurship) | DNS resolution failure on both. |
| `moe.gov.bw` (Education) | DNS failure (bare); `www.moe.gov.bw` timed out. |
| `mlg.gov.bw` (Local Government) | DNS failure (bare); `www.mlg.gov.bw` timed out. |
| `mid.gov.bw` / `www.mid.gov.bw` (Infrastructure and Housing) | DNS resolution failure on both. |
| `mineral.gov.bw` / `www.mineral.gov.bw` (Minerals and Energy) | DNS resolution failure on both. |
| `cms1.gov.bw` (referenced in search results as the unified portal's actual CMS host) | Connection timed out on every attempt. |
| `trade.gov.bw` (Ministry of Trade & Entrepreneurship eServices) | Live (no robots.txt, plain 404), no WAF — but it's a business-licensing portal (company registration, import permits, liquor/trade licences), not a tender publication. Out of scope entirely, not a "failed" source. |
| `www.ppadb.co.bw` | Connection timed out on every attempt — same domain family as the central PPRA search system already known to be down/gated. |

The pattern across the dead domains (Agriculture, Trade/Industry,
Education, Local Government, Infrastructure, Minerals) strongly suggests
these ministries' standalone legacy websites were decommissioned in favor
of the unified `gov.bw` portal — which itself currently has zero tenders
published. Finance and Health are the two ministries confirmed to still
run (and actively use, however infrequently) their own standalone
tender-publishing infrastructure.

## Known limits

- Ministry of Finance's procurement RSS feed had not been updated since
  3 Oct 2024 as of this recon (27 Aug 2026) — expect a quiet dataset most
  runs; this reflects upstream's posting cadence, not a scraping gap.
- Ministry of Health's tenders table currently holds one 2017 entry —
  same caveat, parser is generic and will pick up new rows automatically.
- `gov.bw`'s central tenders portal is deliberately not covered (see
  table above) — worth a quick recheck in a future session in case it
  gets populated, at which point its markup can finally be inspected for
  real and a parser built against actual data.

## Diff cadence

Semiannual smoke test recommended given both sources' slow posting
cadence — a monthly check would mostly just confirm "still zero new
records," which is expected, not a signal of a broken scraper.
