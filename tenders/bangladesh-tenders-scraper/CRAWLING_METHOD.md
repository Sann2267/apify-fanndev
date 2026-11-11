# Crawling Method — Bangladesh Government Tenders (CPTU/BPPA e-GP)

**Last verified:** 2026-08-27

## Which portal, and how it was verified

Bangladesh's national e-Government Procurement (e-GP) system is at
**`www.eprocure.gov.bd`**. It was developed, is owned, and is operated by
the **Central Procurement Technical Unit (CPTU)**, IMED, Ministry of
Planning -- and the portal's own footer now credits the
**Bangladesh Public Procurement Authority (BPPA)** as the copyright holder
("Copyright (c) 2011 Bangladesh Public Procurement Authority (BPPA). All
Rights Reserved. IMED, Ministry of Planning"), indicating CPTU has been
rebranded/absorbed into BPPA at some point after the portal's 2011/2012
launch. This was cross-checked multiple ways before building anything:

- `cptu.gov.bd/e-gp.html` (CPTU's own informational site) documents e-GP
  and links to the live portal.
- Independent government agency sites unrelated to CPTU itself link to
  `www.eprocure.gov.bd` as "the National e-GP System Portal" for their own
  procurement (e.g. `bhbfc.gov.bd`, Bangladesh House Building Finance
  Corporation).
- Live data on the portal itself is current: tenders published *today*
  (2026-08-27, the day of this build) were live during recon, and the
  portal's own footer/marquee reference "PPR 2025" (Bangladesh's current
  Public Procurement Rules), confirming active maintenance.
- Web search independently confirms this is one of the earliest
  World-Bank-funded e-GP systems in South Asia (live since 2011/2012),
  consistent with CPTU's Wikipedia entry.

No third-party aggregator domain was found competing directly for
"Bangladesh government tenders" on the Apify Store -- only broad
40+-country tender aggregators list Bangladesh as one of many supported
sources, not a dedicated single-country actor -- matching this vertical's
established "big platforms saturated, individual countries wide open"
pattern.

## Robots.txt and login wall

- `www.eprocure.gov.bd/robots.txt` has **no dedicated static file** -- it
  302-redirects through a session-cookie-setting hop and ultimately lands
  on `/SessionTimedOut.jsp` (a normal JSP page, HTTP 200). This is the
  Java-app-server-swallows-every-unknown-path behavior already documented
  for this vertical's Nepal (`bolpatra.gov.np`, JBoss/Struts2) and Ghana
  (GHANEPS, Java/Struts) actors -- no `Disallow`, no AI-crawler mention of
  any kind.
- **No login wall for viewing.** Every endpoint this actor uses -- the
  live-tender search (`AllTenders.jsp` / `TenderDetailsServlet`), the
  awarded-contracts search (`SearchNOA.jsp` / `SearchNoaServlet`), and the
  full tender detail page (`ViewTender.jsp`) -- returns real data to a
  totally cold client: no cookies, no session priming, no referer needed in
  practice (a `Referer` header is sent anyway for consistency, but was not
  required in testing). A "User Login" widget appears on every page's
  sidebar (used to place bids or register as a vendor), but it never blocks
  reading tender/award/detail content -- confirmed across dozens of calls
  during recon.
- The homepage's own tender-view dialog explicitly tells users that manual
  ("offline") tenders can also be checked on a separate BPPA site,
  `www.bppa.gov.bd` -- not used by this actor (out of scope; all data here
  comes from the live e-GP system itself, which is far richer).

## No TLS/WAF gate

`curl_cffi` `chrome124`, `chrome131`, `safari17_0`, and `edge101` were all
tried back-to-back against the live-tender search endpoint with a fresh,
uncached client and every one returned an instant, clean `HTTP 200` with
real tender data -- no CAPTCHA, no challenge page, no block. Plain `curl`
with **no TLS impersonation at all** also succeeded throughout recon.
Unlike this vertical's Nepal actor (`bolpatra.gov.np`) and the unrelated
`nepal-ocr-scraper`, no incomplete-certificate-chain issue was found here
-- default TLS verification (`verify=True`) works fine against
`www.eprocure.gov.bd`.

## Gotcha: `X-Requested-With` breaks the search endpoint

A real browser's own `$.post()` call to `TenderDetailsServlet` does **not**
send an `X-Requested-With: XMLHttpRequest` header for this endpoint.
Sending it anyway (the natural instinct when replicating an AJAX call)
caused the servlet to return `HTTP 200` with a **zero-byte body** on every
attempt during recon; removing that header and otherwise sending the exact
same request produced full HTML immediately. This actor's `DEFAULT_HEADERS`
(`src/constants.py`) deliberately omits it.

## Gotcha: `TenderDetailsServlet` needs the FULL field set, even blank

Omitting several of the search form's own field names outright (rather than
sending them as empty strings) also produced an empty response body during
recon. `src/client.py`'s `fetch_list()` always sends every field the real
search page's own JS sends (`departmentId`, `office`, `procNature`,
`procType`, `procMethod`, `tenderId`, `refNo`, four date fields,
`cpvCategory`, `isFrame`, `pageNo`, `size`, `h=t`), setting each to `""`
when not in use, plus an additional `keyword` field (confirmed to combine
cleanly with the rest of this exact field set).

## Three endpoints used by this actor

1. **`POST /TenderDetailsServlet`** (`funName=AllTenders`, `viewType=Live`)
   -- live/open tenders (`mode: "list"`). Confirmed genuine filtering (not
   decorative) on:
   - `keyword` -- free text, matched against title/description. A
     deliberately nonexistent keyword returns a `<td id="noRecordFound">`
     row (zero matches), confirmed against a real keyword returning
     thousands of pages.
   - `procNature` -- `1`=Goods, `2`=Works, `3`=Service,
     `4`=Physical Services. Confirmed independently: `procNature=1` vs
     `procNature=2` alone (no keyword) return visibly different category
     rows in every row of a fresh query.

   **Confirmed server-side quirk: `procNature` is silently ignored whenever
   `keyword` is also set.** Tested extensively (several field-combination
   variants, including the exact shape the site's own keyword-search JS
   sends): a request with both `keyword="hospital"` and `procNature=2`
   (Works) returned **Goods** rows identical to a keyword-only search with
   no nature filter at all -- the site's own search code evidently applies
   `procNature` only in the pure-filter (no-keyword) code path. This actor
   does not claim to combine them: a run with both set logs a warning and
   the query proceeds keyword-only (see `run_list` in `src/main.py`).

   `size` (rows returned) was confirmed to work reliably from 5 up to 100
   (this actor's per-request cap); not tested above that.

2. **`POST /SearchNoaServlet`** -- awarded contracts / Notice of Award
   (`mode: "awarded"`). Much simpler request shape (`keyword`, `pageNo`,
   `size` only) and, unusually for a South Asian e-GP portal, the listing
   rows themselves already carry the **winning supplier's name and the
   contract value** (in BDT crore) -- no per-contract detail-page fetch
   needed for that headline data, unlike most sibling actors in this
   vertical where award value/supplier requires a detail-page hit.

3. **`GET /resources/common/ViewTender.jsp?id=<tenderId>&h=t`** -- full
   tender detail (`mode: "detail"`). The site's own UI navigates here via a
   hidden auto-submitting POST form (`viewtenderform_N`), but a plain GET
   with the same two query params was confirmed to return byte-identical
   content -- simpler for this actor to call directly. Returns rich,
   well-labeled sections: basic info, procurement method/funding, package
   description and CPV category, the full bid schedule (publication,
   pre-bid meeting, closing, security deadlines), tenderer eligibility
   criteria (often several paragraphs of real procurement requirements),
   document fee/payment info, a **per-lot breakdown table** (location,
   security amount, tentative start/completion dates), the inviting
   official's name/designation/contact, and a link to the tender's
   downloadable-documents page (not itself followed by this actor --
   out-of-scope, see README).

   **Not-found gotcha (nicer variant than most sibling actors' HTTP-200
   blank-template pattern):** an unknown/out-of-range `id` still returns
   `HTTP 200`, but with an explicit, human-readable message --
   *"This tender is not exists or You are un-authorized to access
   information for this tender"* -- confirmed on a deliberately
   out-of-range id (`999999999`). This actor detects that exact substring
   as the not-found signal.

## Parsing approach

None of the three endpoints return JSON or even a `<table>`-wrapped
fragment -- the site's own JS inserts a raw sequence of `<tr>...</tr>`
elements directly into an existing page's table via jQuery's `.after()`.
Rows are identified by their `bgColor-white`/`bgColor-Green` CSS class
(alternating-row striping, confirmed present on every real data row across
both list endpoints) and validated by exact `<td>` count (6 for live
tenders, 8 for awarded contracts) -- a shape change raises
`UnexpectedShape` rather than silently mis-mapping columns, per this
project's fail-loud convention.

The tender-detail page has no JSON field names either -- it is a series of
`<table class="formStyle_1">` label/value `<td>` pairs (label cells always
carry `class="ff"`, immediately followed by their value cell in the same
row). Per the convention established by this vertical's Nepal actor, labels
are slugified into camelCase keys generically rather than hardcoded, so
upstream label additions/renames flow through automatically (raw
passthrough) instead of being silently dropped. The lot table
(`class="tableList_1"`) is parsed separately, keying each row off its own
`<th>` header text (also slugified) since column sets can vary slightly by
procurement type.

## Data quirk: reference-number/date formatting is inconsistent

The reference number + date text embedded in each live-tender row's second
column is typed by hand per procuring entity and observed in at least three
different shapes during recon: `"REF, Dated: DD-Mon-YYYY"`,
`"REF, Date: DD-MM-YY"`, and `"REF Date DD/MM/YYYY"` (no comma at all, plain
space separator). This actor's `referenceNo`/`referenceDate` split handles
the first two (comma-delimited) forms; the third leaves the whole string in
`referenceNo` with `referenceDate: null` rather than guessing a fragile
regex for every possible hand-typed variant -- raw passthrough over
half-correct parsing, per project convention.

## Data quirk: `_totalPages` is unreliable at very small page sizes

`_totalPages` (from a hidden `<input id="totalPages">` in each response) is
internally consistent at the page sizes this actor actually uses (`size=50`
gave `totalPages=54`, `size=100` gave `totalPages=27` -- both implying
~2,700 live tenders total, consistent with each other) but goes wildly
inconsistent at very small sizes tested during recon (`size=2` returned
`totalPages=311002`, and the awarded endpoint returned `totalPages=436582`
at `size=2` vs. a much lower, internally-consistent value at larger sizes)
-- almost certainly a server-side calculation quirk specific to small page
sizes, not something this actor's request shape controls. This actor
reports the value exactly as the site returns it for the request actually
made (raw passthrough, `maxResults` defaults to 30 and the field is
documented as "as eprocure reports it" rather than a value this actor
guarantees is exhaustive), the same honesty-over-fabrication convention
used by this vertical's Nepal actor for its own flaky page-size behavior.

## Diff cadence

Quarterly smoke test recommended. This is a mature (2011/2012-launched),
heavily-used government Java application, not a modern SPA -- the endpoint
paths, field names, and `<td>` counts are reasonably likely to stay stable
across small deploys, but a fresh fetch of `AllTenders.jsp` and
`SearchNOA.jsp` (checking their own embedded JS for the request-field
names/shapes documented above) is the right first step if either servlet
starts returning unexpected shapes or empty bodies.
