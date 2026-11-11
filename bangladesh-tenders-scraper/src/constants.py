"""Endpoints, headers, enum maps, and recon summary -- all in one place.

Recon summary (2026-08-27): Bangladesh's national e-Government Procurement
(e-GP) portal is operated by the Central Procurement Technical Unit (CPTU),
IMED, Ministry of Planning -- now rebranded/absorbed as the **Bangladesh
Public Procurement Authority (BPPA)**, per the portal's own footer
("Copyright (c) 2011 Bangladesh Public Procurement Authority (BPPA). All
Rights Reserved. IMED, Ministry of Planning"). Live at
**www.eprocure.gov.bd** -- independently cross-checked against multiple
government agency sites (e.g. `bhbfc.gov.bd`) linking to it as "the national
e-GP system portal", and against `cptu.gov.bd/e-gp.html`, CPTU's own
informational page describing it. One of the earliest World-Bank-funded
e-GP systems in South Asia (live since 2011/2012) -- long-lived and heavily
used (a single day's "Live" tender count during recon was in the low
thousands).

No dedicated `robots.txt` file exists on this host: `/robots.txt` returns a
302 redirect chain ending at `/SessionTimedOut.jsp` (HTTP 200, a generic
JSP page) -- the exact same "Java app server swallows every unknown path"
behavior already documented for this vertical's Nepal (`bolpatra.gov.np`,
JBoss/Struts2) and Ghana (GHANEPS, Java/Struts) actors. No Disallow, no
AI-bot mention of any kind.

**No login wall for viewing.** Every endpoint used by this actor -- the
live-tender search, the awarded-contracts (Notice of Award) search, and the
full tender detail page -- returns real data to a completely cold client
with zero cookies, zero session priming, and zero TLS impersonation (plain
libcurl with no fingerprint spoofing got clean 200s with real data
throughout recon). A "User Login" box appears in the page sidebar on every
page (for placing/managing bids), but it is a decorative widget, not a
gate -- confirmed by successfully reading dozens of live tenders, awarded
contracts, and tender-detail pages with no cookies at all.

**No WAF / TLS fingerprint gate observed.** `curl_cffi` `chrome124`,
`chrome131`, `safari17_0`, and `edge101` were all tried back-to-back against
the live search endpoint and every one returned an instant clean 200 with
real data (no CAPTCHA, no challenge page, no rate-limit block).

**Gotcha: the `X-Requested-With: XMLHttpRequest` header breaks the search
endpoint.** A real browser's jQuery `$.post()` call does NOT send this
header for this particular endpoint's own AJAX call (checked by replaying
the exact JS-observed request shape) -- sending it anyway caused
`TenderDetailsServlet` to return `HTTP 200` with a **zero-byte body** for
every attempt during recon, while the identical request MINUS that header
returned full HTML immediately. This actor's client deliberately omits
that header (see `DEFAULT_HEADERS` below).

**Three server-rendered HTML-fragment endpoints, all POST (except the
detail page, which also accepts GET):**

- `POST /TenderDetailsServlet` (`funName=AllTenders`) -- live/open tenders.
  Requires the FULL set of form field names the search page's own JS sends
  (`departmentId`, `office`, `procNature`, `procType`, `procMethod`,
  `tenderId`, `refNo`, `pubDtFrm`, `pubDtTo`, `closeDtFrm`, `closeDtTo`,
  `cpvCategory`, `isFrame`, `pageNo`, `size`, `h=t`) present in the POST
  body even when blank -- omitting several of them outright made the
  servlet return an empty body during recon, rather than an error. An
  optional `keyword` field (free text) and `procNature` (`1`=Goods,
  `2`=Works, `3`=Service, `4`=Physical Services) both genuinely filter the
  result set -- confirmed independently (different keywords/natures
  produced different row counts and different `totalPages`), not decorative
  parameters. `size` (rows per page) was confirmed to work reliably from 5
  to 100 (used 100 as this actor's per-request cap; not tested further
  above that). Zero matches renders a `<td id="noRecordFound">` row instead
  of data rows -- detected explicitly rather than treated as an error.
- `POST /SearchNoaServlet` -- awarded contracts (Notice of Award), with
  genuine transparency-register value: winning supplier name and contract
  value (in BDT crore) are both included directly in the list rows, no
  detail-page fetch needed. Much simpler request shape: just `keyword`,
  `pageNo`, `size`. Same `noRecordFound` zero-match convention (own id
  attribute placement differs slightly but is still detected by id).
- `GET /resources/common/ViewTender.jsp?id=<tenderId>&h=t` -- full tender
  detail (this actor's `detail` mode). No auth needed; confirmed working
  via plain GET even though the site's own UI navigates to it via a hidden
  POST form (`viewtenderform_N`) -- both were tested and return identical
  content. An unknown/nonexistent id returns **HTTP 200** with an explicit,
  human-readable message ("This tender is not exists or You are
  un-authorized to access information for this tender") instead of a 404
  or a blank template -- a nicer variant of the same "HTTP-200 empty
  result" gotcha already seen on this vertical's Nepal and Ghana actors.

No cert-chain issue was found here (unlike `bolpatra.gov.np` and
`camis.ocr.gov.np`, both of which need `verify=False`) -- default TLS
verification works fine against `www.eprocure.gov.bd`.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.eprocure.gov.bd"
LIST_SEARCH_URL = f"{BASE_URL}/TenderDetailsServlet"
AWARDED_SEARCH_URL = f"{BASE_URL}/SearchNoaServlet"
DETAIL_URL = f"{BASE_URL}/resources/common/ViewTender.jsp"
AWARDED_DETAIL_URL = f"{BASE_URL}/resources/common/ViewAwardedContracts.jsp"

# Deliberately NO "X-Requested-With" header -- see module docstring, sending
# it causes TenderDetailsServlet to return an empty body.
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/resources/common/AllTenders.jsp?h=t",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
REQUEST_TIMEOUT = 45

# TenderDetailsServlet's own "procNature" <select> option values.
PROCUREMENT_NATURE_MAP = {
    "all": "",
    "goods": "1",
    "works": "2",
    "service": "3",
    "physicalServices": "4",
}
