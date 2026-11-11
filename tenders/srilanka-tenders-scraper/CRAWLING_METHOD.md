# Crawling Method — Sri Lanka Government Tenders (Treasury / Ministry of Finance)

**Last verified:** 2026-08-27

## Target discovery — what "the" official Sri Lanka tender portal actually is

Sri Lanka has no single OCDS-style national e-GP aggregator that is both
genuinely official *and* freely scrapable:

- **`promise.lk`** ("Promise" e-GP, National e-GP System) is the platform most
  search results and secondary sources point to as Sri Lanka's e-procurement
  system, with a public search page at
  `?p=vendor_cont&a=all_procurements&type=e`. It could not be independently
  verified: every direct connection attempt (`curl`, `curl_cffi`, and the
  agent's own `WebFetch` tool) either timed out or hit `ECONNREFUSED` on
  `124.43.177.184:443` from this environment. This reads as either a
  geo-restriction (Sri Lanka-only routing) or the host being down/unreachable
  from this network -- not a bot block (no WAF response was ever received to
  triage). **Not used**, since it could not be verified as workable at all.
- **`nprocom.gov.lk`** (National Procurement Commission, the constitutional
  body that regulates public procurement) is genuinely official, has a
  permissive `robots.txt` (`Disallow: /wp-admin/` only), and has a
  "Procurement Notices" nav item -- but that page only holds static
  guidance/Standard Bidding Document templates, not actual live tender
  listings. Its sibling `epms.nprocom.gov.lk` ("Electronic Procurement
  Monitoring System") is a genuine live procurement database, but is a large,
  JS-driven exploration/reporting tool (procurement plans, monitoring
  records) rather than a simple tender-notice bulletin, and was not verified
  further given the strong alternative below. **Not used** for this actor.
- **`treasury.gov.lk`** (Ministry of Finance, Planning and Economic
  Development -- the ministry the brief explicitly named as a candidate) runs
  a `/procurement/procurement-notices` page that is a genuine, actively
  updated (multiple new notices per week, most recent dated the day of this
  survey) bulletin of real tender/bid notices from government departments
  under its umbrella (Department of Management Services, Department of State
  Accounts, Sri Lanka Customs, Excise Department, Department of Information
  Technology Management, and the Ministry itself), plus a paginated archive
  of 460+ historical notices back to January 2019 from an even wider set of
  entities (Ministry of Health / State Pharmaceuticals Corporation, etc.).
  **This is what the actor scrapes.** It is scoped to notices the Treasury
  itself publishes (not literally every ministry in the country -- no such
  single aggregator exists per this survey), but it is unambiguously a real,
  official, actively-maintained `.gov.lk` government tender bulletin, matching
  the brief's own fallback candidate ("Ministry of Finance procurement
  guidelines portal").

## robots.txt

`https://www.treasury.gov.lk/robots.txt` returns a real HTTP **404** — not a
disallow rule, an actual missing file. This is a Next.js app; unmapped paths
render its own styled 404 page (confirmed: title "Page Not Found - Ministry
of Finance, Sri Lanka", full site chrome, not a bare error). Since no
`robots.txt` exists at all, there is no `Disallow` rule of any kind and no
`User-agent: Claude`/`anthropic-ai` mention to find, on the `www` hostname
tested.

## WAF — Sucuri/Cloudproxy, permissive

The site sits behind **Sucuri/Cloudproxy** (`Server: Sucuri/Cloudproxy`,
`X-Sucuri-ID`, `X-Sucuri-Cache` headers on every response). No JA3/TLS
fingerprint gate, no JS challenge page, and no CAPTCHA were observed:

- Plain `curl` with a generic desktop User-Agent (no TLS impersonation at
  all) got clean `200`s with full page content on every path tested.
- One quirk: the very first request to `/procurement/procurement-notices` in
  a fresh connection sometimes answers `307 Temporary Redirect` (same URL,
  no `Location` header change, no cookie set) before a same-session retry
  returns `200`. This reads as a Sucuri load-balancer/cache-warming artifact,
  not a bot challenge -- `curl -L` (and `curl_cffi`'s default
  `allow_redirects=True`) handles it transparently, identical to how a real
  browser would.
- The actor still uses `curl_cffi` with `impersonate="chrome124"` per this
  portfolio's default stack, even though bare `curl` already worked, for
  production robustness against any future WAF tightening.

## No login required to view listings

Both the current-notices page and every archive page (`/p/procurement-notices/1`
through `/23`) return full content to a plain, unauthenticated GET. No
cookies, sessions, or account of any kind are needed to browse. (Sri Lanka's
Public Procurement Guidelines do gate actual *bid submission* behind supplier
registration on relevant department systems -- this actor only reads public
notice listings, never touches bidding.)

## Data source — Next.js `__NEXT_DATA__`, two distinct page shapes

`www.treasury.gov.lk` is a Next.js (React SSR) site. Every page ships its
data pre-rendered inline as `<script id="__NEXT_DATA__" type="application/json">`.
This actor regex-extracts and JSON-parses that blob rather than CSS-selecting
rendered HTML (more stable across cosmetic redesigns, per this portfolio's
`JSON-LD > __NEXT_DATA__ > HTML` priority order) -- no true public REST API
or RSS feed was found for either view. A lighter Next.js data-only endpoint
(`/_next/data/<buildId>/procurement/procurement-notices.json`) also exists
and returns the identical JSON, but was deliberately **not** used: `buildId`
changes on every site redeploy, which would require a cache-with-refresh
mechanism for a payload-size saving (144 KB vs 211 KB) that doesn't matter at
this actor's scale (tens of requests per run). Parsing the always-current
full HTML page avoids that fragility entirely.

### "Latest" mode — `/procurement/procurement-notices`

`pageProps == {"notices": [...], "count": N}`. Each notice is a clean,
already-structured object (id, issuing department as `title`, notice title as
`subtitle`, an HTML `description` fragment with the contract/IFB reference
number, `status`, `createdOn`/`publishedOn`/`updatedOn` timestamps, and an
`attachments` list). As of 2026-08-27: 20 notices live, `count: 144`
(cumulative total notices this system has ever held, not all still shown --
the historical ones live in the separate archive below instead).

Each attachment's `link` field is a **bare UUID**, not a path -- the
`/api/file/<uuid>` pattern was confirmed by fetching one directly
(`Content-Type: application/pdf`, real 20-page PDF, `Content-Disposition:
inline`, no auth). The actor resolves this into a `downloadUrl` convenience
field alongside the raw `link`.

### "Archive" mode — `/p/procurement-notices/<page>`

`pageProps == {"sections": [...], "count": N, "page": N}`. This is a
completely separate, older CMS content-block system (not the same backend as
"latest") holding free-form HTML notices going back to January 2019.
`count: 460` total notices across pages `1`-`23` (confirmed by binary-search
probing: page 23 returns `200`, page 24 returns a real `404` — this is the
actor's end-of-archive signal, checked fresh each run rather than hardcoded,
since the archive will grow over time as old "latest" notices presumably age
out into it). Page sizes vary (16 sections on page 1, as few as 4 on page 2)
-- this is a content-block CMS, not a fixed-page-size table, so the actor
does not assume any particular count per page.

Each section's `html` field is genuinely free-form -- department name, bid
reference number, item list, and closing date all live inside arbitrary
`<h3>`/`<h4>`/`<p>` tags with no consistent structure (some notices even
contain literal invalid-HTML artifacts like `style={color:'red'}`, exactly as
upstream authored them). This is raw-passthrough by necessity: the actor does
not attempt to parse structured fields (deadline, reference number) out of
this HTML, since no field is guaranteed present or positioned consistently
across 460+ hand-entered notices spanning 7+ years. It does provide a
`descriptionText` convenience field (tags stripped via BeautifulSoup) for
easier reading/searching, alongside the raw `descriptionHtml`.

Archive attachments live under `/documents/procurement/notices/...` and are
mostly directly downloadable with no auth -- **some older ones (2021 and
earlier, tested) now 404**, presumably cleaned up by the Ministry over time.
The actor passes through the metadata unconditionally (raw passthrough
principle: a missing file is a fact about upstream, not something to hide by
dropping the record).

## Why no "detail" mode

Neither view has a separate per-notice detail page — everything the site
itself shows for a given notice (department, title, reference text, and
attachments) is already present in the list-page JSON. A `detail` mode would
just be a network round-trip to re-fetch the exact same data (or, for
archive, fetch a document file, which is not something to shoehorn into a
JSON detail record). This matches the "only add a detail mode if individual
pages carry richer info" guidance in this portfolio's actor-building skill.

## TLS profile

`chrome124`, consistent with the portfolio-wide default. No profile-specific
blocking was observed on this host.
