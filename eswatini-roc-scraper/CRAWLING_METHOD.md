# Crawling Method — Eswatini Company Registry

**Last verified:** 2026-08-26/27

## Finding the real portal (this took most of the recon time)

Every third-party KYC/company-search blog (creditreform.co.uk, businessdataguide.com, and others surfaced by web search) cites `cipa.org.sz` as "Eswatini's Companies Registry portal, run by the Company and Intellectual Property Authority (CIPA)". **That domain does not resolve at all** — NXDOMAIN on every lookup tried, both bare and with `www.`. CIPA appears to have no live web presence at all as of this recon.

The REAL, live, official system was found by following the link trail from the *government's own* page instead of third-party blogs: `https://www.gov.sz/index.php/departments-sp-1596706154?id=522` ("REGISTRAR OF COMPANIES") names the online portal and its exact URL in its body text, and links to:

```
https://www.online.gov.sz/
```

— "Government Online Services", a general citizen e-services portal run by **Government Computer Services** (per the footer) under the Ministry of ICT, not a CIPA-branded system anywhere in its markup. Its "Business" menu has four items; only the first is public:

| Menu item | Path | Login required? |
|---|---|---|
| Company Name Search | `e-companysearch.aspx` | **No** — used by this actor |
| Company Name Reservation | `e-reservationSignOn.aspx` | Yes (`...SignOn...`) |
| Company Registration | `e-registrationLOGIN.aspx` | Yes (`...LOGIN...`) |
| Trading and Liquor License Application | `TradingLicenseSignOn.aspx` | Yes (`...SignOn...`) |

Named this actor `eswatini-roc-scraper` (Registrar of Companies) rather than `eswatini-cipa-scraper`, since CIPA has no reachable domain and nothing on the working portal identifies as CIPA — "Registrar of Companies" is both the legal/historical name and what the linking government page itself calls it.

### TLS cert gotcha: use `online.gov.sz`, not `www.online.gov.sz`

The site's cert is `CN=*.gov.sz`, SAN `DNS:*.gov.sz, DNS:gov.sz`. A wildcard covers exactly one label — it matches `online.gov.sz` but **not** `www.online.gov.sz` (two labels deep). Any client that verifies certs (a bare TLS handshake, `curl_cffi` without disabling verification) throws a hostname-mismatch error against the `www.` host, even though `www.online.gov.sz` itself resolves and serves the identical site over HTTP and over HTTPS-with-verification-disabled. Confirmed the fix: hit `https://online.gov.sz/...` (no `www.`) and the cert validates cleanly with no special handling needed.

## Robots.txt

```
HTTP 404 (no robots.txt file exists at all)
```

No restrictions, no Claude/AI-crawler mention — there's nothing to mention anything in. Checked both `online.gov.sz/robots.txt` and `www.online.gov.sz/robots.txt`.

## WAF / anti-bot

**None observed.** Plain `nginx` (per `Server` header) in front of an ASP.NET 4.0 app (`X-AspNet-Version: 4.0.30319`, `X-Powered-By: ASP.NET`). All four `curl_cffi` profiles tried (`chrome124`, `chrome131`, `safari17_0`, `edge101`) got identical HTTP 200 responses — no fingerprint gate, no CAPTCHA, no Cloudflare/`cf-ray` markers.

## The search flow — classic ASP.NET WebForms postback, no JSON API

View-source of `e-companysearch.aspx` shows a plain `<form method="post">` with a text input (`ctl00$MainContent$txtreserve`) and a submit button (`ctl00$MainContent$Button1`) — no JS, no fetch/XHR anywhere. This is NOT a REST API; it's a server-rendered postback form, the same family of pattern as `botswana-cipa-scraper`'s Verne app but far simpler (no transaction ids, no node-graph, no delta-mode flags).

1. `GET https://online.gov.sz/e-companysearch.aspx` — the server sets an `ASP.NET_SessionId` cookie and returns the form page embedding three hidden fields: `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`.
2. `POST` the same URL, form-encoded, with those three tokens plus `ctl00$MainContent$txtreserve=<query>` and `ctl00$MainContent$Button1=search`, **on the same cookie-bearing session** — ASP.NET's server-side event-validation check is tied to the session that issued the `GET`; a stateless client (fresh cookies per request) gets rejected.
3. The response is a full HTML page (not a partial/AJAX fragment) containing either:
   - `id="MainContent_GridView1"` — an HTML `<table>` with one `<tr>` per match, columns "Company Name" / "Company Status" / "Date Registered", or
   - `id="MainContent_Label2"` containing the text "No match was found for the specified company name" — the reliable zero-result signal (`extractor.NoResultsFound`).

No detail/profile page exists reachable from here — the `<td>` cells are plain text, not hyperlinks. There is nothing to click through to without logging into the Company Registration module.

## No pagination — the whole result set renders in one response

Confirmed with three different query breadths in the same recon session:

| Query | Rows returned | Response time | Response size |
|---|---|---|---|
| `"trading"` | 3,864 | ~7s | 1.46 MB |
| `"tra"` | 15,366 | 23.5s | 6.0 MB |
| `"trad"` | 5,556 | 10.0s | 2.1 MB |
| `"eswa"` | 6,564 | 15.9s | 2.5 MB |
| `"moza"` | 138 | 1.8s | 60 KB |
| `"mtn"` | 42 | 1.2s | 22 KB |
| `"ab"` | 13,758 | ~22s | — |

No `__doPostBack('GridView1','Page$N')` pattern anywhere in the markup (the standard ASP.NET GridView pager postback) — every match is rendered server-side in one page load, regardless of how many thousands there are. This actor slices to `maxResultsPerQuery` client-side after parsing the full response.

## Very short/generic queries can hang the server itself

A 1-character query (`"a"`) and a 2-character query (`"in"`) were both observed to make the server hang — no bytes received at all after 60 seconds (confirmed as server-side, not a client timeout artifact: the TCP connection stays open with zero response). Presumably the server tries to synchronously render an enormous result set. Notably this is NOT purely a character-count threshold — a different 2-character query (`"ab"`) completed fine in ~22s with 13,758 rows — it depends on how many rows the specific substring actually matches, which isn't knowable in advance.

Mitigations shipped in this actor:
- `MIN_QUERY_LENGTH = 3` (`src/constants.py`) rejects anything shorter client-side with a `query_too_short` error record, before spending a request.
- `REQUEST_TIMEOUT = 75` seconds gives a legitimately broad-but-completing query (like `"tra"` at 23.5s) plenty of headroom.
- This does not eliminate the risk entirely — a rare 3+ character prefix could still be broad enough to hang the server. If that happens, the retry loop's `except Exception` catches the timeout and retries (up to `MAX_RETRIES = 3`), which in the worst case means ~3×75s before surfacing a `blocked_or_transient` error record for that one query. Users are advised via the input schema description to keep `maxConcurrency` low and expect broad queries to take longer.

## Duplicate rows are upstream's own data, not a parsing bug

Searching `"MTN"` returns the literal string `"MTN FINTECH SERVICES (PROPRIETARY) LIMITED" | RESERVED | 03/04/2020` **five times in a row**, byte-for-byte identical. Verified this is present in the raw HTML table itself (not introduced by the regex parser) — the register's own database has duplicate entries for this name. Per this project's raw-passthrough convention, these are NOT deduplicated — the actor emits exactly what the register shows.

## Sample entities tested

- **`"MTN"`** — 42 matches, including 5 duplicate rows for the same reserved name.
- **`"Eswatini Bank"`** — matches include `ANGLO ESWATINI BANK (PROPRIETARY) LIMITED` (`COMPANY REGISTERED`, 2019) and `ESWATINI BANK LIMITED` (`RESERVED`, 2018).
- **`"Debswana"`** (Botswana's largest company, used as a cross-check) — correctly returns `not_found`, confirming the zero-result path doesn't false-positive on a plausible-looking but wrong-country name.
- **`"zzzznonexistentxyz999"`** — confirms `NoResultsFound` on an unambiguous garbage query.
- **`"trading"` / `"tra"` / `"trad"` / `"eswa"` / `"moza"` / `"ab"`** — breadth/timing table above.

## Known limits

- **No detail/profile page** — this is a name-search-only actor. Registration number, directors, addresses, and annual-return history all live behind the login-gated Company Registration module on the same portal, out of scope per this project's no-login policy.
- **No true pagination cap** — `maxResultsPerQuery` truncates client-side after the full (potentially huge) response has already been downloaded and parsed; it does not reduce server-side work or response time for a broad query.
- Dates are passed through exactly as displayed (`MM/DD/YYYY` strings), not normalized to ISO 8601.
- A rare, sufficiently-broad 3+ character query could still time out server-side (see above) — surfaces as a `blocked_or_transient` error record for that query rather than crashing the whole run.

## Diff cadence

Quarterly smoke test recommended (a small government ASP.NET portal like this can be redeployed/redesigned with little notice, and unlike a commercial vendor platform there's no changelog to watch).
