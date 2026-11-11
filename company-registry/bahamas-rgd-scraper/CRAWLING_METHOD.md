# Crawling Method — Bahamas RGD

**Last verified:** 2026-08-27

The Bahamas' official company/business registry is run by the **Registrar
General's Department (RGD)**, part of the Ministry of Finance. Three hosts
are involved:

- `www.rgd.gov.bs` — the RGD's marketing/info site (also mirrored via
  `bahamas.gov.bs/agencies/registrar-generals-department` and
  `bahamas.gov.bs/service/company-search`, both of which link/redirect here).
- `pub.rgd.gov.bs` — "BDR Online Public Services", an Angular SPA that hosts
  the actual Company Search / Name Reservation / Document filing tools.
- `cars.rgd.gov.bs` — the JSON REST API backing the SPA ("CARS" = Corporate
  Administrative Registry Services).

## Robots.txt

`www.rgd.gov.bs/robots.txt` (200, 454 bytes):

```
User-agent: *
Disallow: 
Disallow: /cgi-bin/

User-Agent: Googlebot
Allow: /
... (similar explicit-Allow groups for Adsbot-Google, Googlebot-Image,
     Googlebot-Mobile, YahooSeeker/M1A1-R2D2, MSNBOT-MOBILE, Twitterbot)
```

Checked every `User-agent:` line individually (not just the last one before
a `Disallow:`, per this project's standing policy after the Babak 14
multi-group-parsing bug) — no group anywhere names Claude, ClaudeBot,
Claude-Web, Claude-User, Claude-SearchBot, or anthropic-ai, and the `*`
group has no blanket `Disallow: /`. `pub.rgd.gov.bs/robots.txt` and
`cars.rgd.gov.bs/robots.txt` both return HTTP 200 but serve the SPA's
`index.html` shell (client-side-routed app, no server-side match for that
path) — i.e. neither host actually has a `robots.txt` file, so no
restriction applies there either. No natural-language AI/data-mining
prohibition anywhere in the actual robots.txt text.

## No login/CAPTCHA gate on the free search

The Company Search page's Angular component (`CompanySearchModule`) calls
the free search directly from the name input box with no auth step.
reCAPTCHA (`recaptcha_sitekey` present in the SPA's build-time
`environment` config) only gates the credit-card **payment** step later in
the flow ("PROCEED TO PAYMENTS PAGE" → `initiatePayment(...)`), for the paid
$100 BSD "Company Search Report". This was confirmed by reading the
Angular component source (see below), not assumed from marketing copy.

## Finding the API: read the shipped Angular bundle

`pub.rgd.gov.bs` is an Angular (not React/Vue, unlike prior registry
targets) SPA. Its `index.html` references three top-level chunks
(`runtime.<hash>.js`, `polyfills.<hash>.js`, `main.<hash>.js`); `main.js`
declares the lazy-loaded route `services/company_search` →
`CompanySearchModule`, resolved via `runtime.js`'s webpack chunk-ID→hash map
to `66.<hash>.js` (the search-page component) and `868.<hash>.js` (the
shared Angular service class with the actual HTTP calls). Same "download the
build and grep for API base URLs / route tables" technique used for
URSB/CIPA/PACRA in prior actors, adapted to Angular's webpack chunk-loader
format instead of Vite/Next.

`main.js`'s production `environment` object:

```js
{ apiBase: "https://cars.rgd.gov.bs/api", loginUrl: "https://cars.rgd.gov.bs",
  recaptcha_sitekey: "6LdT0W4e...", disableServices: false }
```

`868.<hash>.js`'s service class:

```js
searchCompany(name, includeHistory=false, pageNo=1, pageSize=3) {
  const path = `/public/entities${includeHistory ? "/history" : ""}`
             + `?name=${encodeURIComponent(name)}&pageNo=${pageNo}&pageSize=${pageSize}`;
  return this.api.get(path);   // GET {apiBase}{path}
}
```

i.e.:

```
GET https://cars.rgd.gov.bs/api/public/entities?name=<query>&pageNo=<n>&pageSize=<n>
GET https://cars.rgd.gov.bs/api/public/entities/history?name=<query>&pageNo=<n>&pageSize=<n>
```

Both confirmed reachable with a **completely plain, unauthenticated
`curl`** — no TLS impersonation, no cookies, no special headers (`Origin`/
`Referer` were tried and made no difference once the actual empty-body
behavior below was understood; a same-path 404 for a bogus URL returns a
normal JSON error body, and a sibling public endpoint
`/public/bdr/features` returns `{"PUBLIC_COMPANY_SEARCH":true}` confirming
the feature flag is on). `curl_cffi` is still used in this actor's client
for consistency with the rest of the portfolio, not because any gate
requires it.

## Gotcha 1: `pageNo`/`pageSize` are accepted but silently ignored — free tier hard-caps at 3 results

Every combination tested — `pageSize` of 3, 50, or 100; `pageNo` of 1 or 2 —
returned **the same 3 results, in the same order**, for every query that had
matches (confirmed on `Colina`, `Atlantis`, `Nassau`, `Graham`,
`International`, byte-for-byte identical response bodies regardless of the
requested page/size). This is not a request-construction bug on this
actor's side: the free `/public/entities` endpoint is a "top-3 best name
matches" preview, full stop. This matches the government's own
monetization design — free preview to help you *identify* the entity you
want, paid $100 BSD "Company Search Report" (credit card, CARS account) to
actually see or pull anything beyond the top-3 name list. This actor does
not implement pagination logic because there is genuinely nothing to
paginate into.

## Gotcha 2: broad/common queries return HTTP 200 with a truly empty (0-byte) body

A query matching nothing real returns `200` with a proper empty JSON array,
`[]` (2 bytes) — e.g. `name=xyzxyzxyznonexistent12345` or
`name=AML Foundation`. But short/very common terms —
`Bank`, `Banks`, `Ba`, `Ban`, `RBC`, `LTD` — reliably return `200` with a
**completely empty body: 0 bytes, no `Content-Type` header at all**
(`Transfer-Encoding: chunked` with an immediate terminator). Reproduced
identically across:

- `curl_cffi` (`chrome124`, `chrome131`, `safari17_0`, `edge101` — all the
  same)
- plain `httpx` (`http2=True` requested, server negotiated `HTTP/1.1`
  anyway — same empty result)
- real system `curl` (`curl -sD headers.txt -o body.json ...` — body file
  is 0 bytes)
- every header combination tried: no headers, `Accept: application/json`,
  full browser `Sec-Fetch-*`/`sec-ch-ua` set, `Origin`+`Referer` matching
  the real SPA, even `User-Agent: Googlebot` — all identical

...which rules out TLS-fingerprint gating, a CORS/Origin check, and a
User-Agent-based block. Response time for these was fast and consistent
(~1.3s, not a slow-timeout pattern), and deterministic across repeated
calls — not flaky/random. Likely cause: the backend's relevance-ranking
computation over an unusually large candidate set (a common short
word/prefix matches thousands of Bahamas IBCs by design, since this is a
major offshore company-formation jurisdiction) hits an internal resource
limit or a short reverse-proxy timeout, and the gateway returns a
truncated/empty `200` instead of a proper error. Interestingly, `"Banker"`
(also containing the substring `"bank"`) returned real results fine — so
this is driven by total-match-count/breadth, not a keyword-substring
content filter.

This actor's `client.py` distinguishes the two empty cases explicitly:
a real `[]` body → `not_found`; a 0-byte body → `TooBroadError` →
`result_set_too_broad` in the output, rather than collapsing both into a
false "not found" (same spirit as `fiji-roc-scraper`'s own
`result_set_too_broad` handling for its overly-fuzzy search). **Practical
takeaway:** search with a real, reasonably specific company name or a
distinctive fragment, not a single common word.

## Gotcha 3: almost every field beyond name/ID is `null` on the free tier

Each matched entity carries `entityId` (RGD's internal numeric ID) and
`entityName` (exactly as registered) as the only reliably populated fields,
plus `legacyMigrationStatus` (`"NONE"` on every live sample: banks, hotels,
insurers, law firms, foundations, across a dozen+ distinct real queries).
Every other field — `entityType`, `entityNumber`, `entityStatus`,
`registrationDate`, `directors`, `shareholders`, `capitals`, `documents`,
etc. — was `null`/`[]` on every single real entity sampled. This is a
genuine data-completeness limit of the free preview, not a scraping gap:
that's exactly the content of the $100 BSD paid Company Search Report,
which requires the credit-card payment flow this project does not automate.
Raw-passthrough is used throughout, so if RGD ever populates more fields on
the free tier they will show up automatically without a code change.

## Name-history variant

`GET {apiBase}/public/entities/history?name=<query>...` searches
name-CHANGE history instead of current names. Each hit:
`{"nameHistoryId": <id>, "name": "<former name>", "entity": {...same shape
as the plain search...}, "links": []}`. Confirmed working, e.g.
`name=Bahamas Hot` → `Bahamas Hotel And Restaurnats Employers'Association`
(note the upstream typo, preserved verbatim per raw-passthrough) and
`Bahamas Hotel And Tourism Association`. Same 3-result cap and same
0-byte-on-too-broad behavior as the plain search. Exposed as this actor's
`includeHistory` input flag.

## Sample queries tested

- **Sandals** — 3 real hotel-group entities (Sandals Intertrade Ltd.,
  Sandals Resorts International 2000 Inc., Sandals Resort Limited).
- **Baha Mar** — 3 real entities (Baha Mar Equity L.P., The Baha Mar
  Foundation, Baha Mar Holdings Ltd.).
- **Atlantis**, **Colina**, **Scotiabank**, **Kerzner** — all real, plausible
  Bahamas corporate entities, 3 results each.
- **AML Foundation** — real empty result, `[]` (proves the true-empty-array
  path is reachable and distinct from Gotcha 2).
- **xyzxyzxyznonexistent12345** — real empty result, `[]`.
- **Bank**, **Banks**, **Ba**, **Ban**, **RBC**, **LTD** — all reproduced the
  0-byte "too broad" response (Gotcha 2).
- **Bahamas Hot** (with `includeHistory=true`) — 2 real former-name records.

## Known limits

- Free tier hard-caps at 3 results per query with no working pagination
  (Gotcha 1) — this is the upstream tool's actual design, not a scraping
  limitation.
- Almost all fields beyond name/ID are `null` on the free tier (Gotcha 3) —
  matches exactly what the RGD's own free tool shows; the paid report is
  where the rest of the data lives.
- Broad/common single-word queries can return `result_set_too_broad`
  instead of results (Gotcha 2) — use specific company names.
- This actor covers the free public name-search only. The $100 BSD paid
  Company Search Report (registration number, status, entity type,
  directors, share capital, filed documents) requires a CARS account and
  credit-card payment on `rgd.gov.bs` — out of scope (no payment/login
  automation in this project).

## Diff cadence

Quarterly smoke test recommended. Angular chunk hashes will change on any
RGD redeploy, but the underlying `/api/public/entities` REST shape is a
stable backend contract independent of frontend build hashes.
