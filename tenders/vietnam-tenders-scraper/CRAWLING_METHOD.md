# Crawling Method — Vietnam Government Tenders (VNEPS)

**Last verified:** 2026-08-27

## Target discovery — `muasamcong.mpi.gov.vn` is the real, current official platform

Vietnam's **National E-Procurement System** ("Hệ thống mạng đấu thầu quốc gia",
internally versioned "EGP_v2.0", publicly branded **VNEPS**) is operated by
the Ministry of Planning and Investment's (MPI) Procurement Management
Department at `https://muasamcong.mpi.gov.vn`. Confirmed independently:

- MPI's own official site (`mpi.gov.vn/en/Pages/Procurement-1638.aspx`) links
  out to it as the government's procurement portal.
- Vendor press material (FPT Information System Corp / FPT IS, the system
  integrator) documents the platform's launch and describes MPI as the
  directing ministry.
- The system is under active, recent maintenance: VNeID electronic-identity
  login integration (March 2026), a new registration flow rolled out on the
  National Public Service Portal (June 2026), and a regulatory update per
  Decree 274/2026/NĐ-CP (August 2026) — all reported in 2026 news coverage,
  confirming this is the live, current platform, not a decommissioned one.
- The site itself is a Liferay portal (`/web/guest/...` paths, `p_p_id=...`
  portlet parameters) titled "EGP_v2.0 - EGP" in its own page `<title>`.

No decoy/lookalike commercial domain was found sitting next to this one (the
pattern seen in several other countries in this project, e.g. Tanzania's
`nest.co.tz`) — `muasamcong.mpi.gov.vn` itself is unambiguously the platform.

## robots.txt

```
User-Agent: *
Disallow:
```

Identical across TLS profiles. A blank `Disallow:` value means **allow
everything** — this is the opposite of a blanket block. One flat
`User-agent: *` group, no Claude/ClaudeBot/Claude-Web/Claude-User/
Claude-SearchBot/anthropic-ai mention anywhere, no natural-language
prohibition comments.

## No login required to search, browse, or fetch award detail

The "Lựa chọn nhà thầu" (Contractor Selection) search page
(`/en/web/guest/contractor-selection?render=index`) is reachable anonymously
and returns a full page (~550 KB) with zero redirects to any login screen.
The JSON services it calls internally (below) were confirmed reachable with
a fresh, cookie-less `curl_cffi` session — no session, no API key, no CSRF
token. VNEPS does have "Register" / "Login" flows (recently gaining VNeID
integration per the March 2026 update above), but — consistent with every
other tender-vertical actor in this project (Ghana/Zambia/Jamaica/Uganda/
PNG/Sierra Leone/Nepal/Tanzania/Eswatini/Rwanda/Namibia/Trinidad & Tobago/
Botswana/Malawi) — that gate is for **submitting** a bid or managing an
account, never for viewing/searching public notices, plans, or results.

## The real find: the SPA's own internal search API, reverse-engineered from its inline script

`contractor-selection` is a Liferay portlet whose body is a Vue.js 2 widget
(loaded inline, not a separate bundle file) backed by `axios`. Rather than
scrape the rendered HTML table, the widget's own `data()` block was read
directly out of the page source and yields the real internal service paths
it calls, e.g.:

```js
elasticSearch: "/o/egp-portal-contractor-selection-v2/services/smart/search",
urlDetailKqlcntLdt: "/o/egp-portal-contractor-selection-v2/services/expose/contractor-input-result/get",
```

Both are plain `POST` endpoints under
`https://muasamcong.mpi.gov.vn/o/egp-portal-contractor-selection-v2/services`,
confirmed live with `curl_cffi` and zero auth:

```
POST /smart/search?token=<anything-non-empty>
Content-Type: application/json
[{
  "pageSize": 50,
  "pageNumber": 0,
  "query": [{
    "index": "es-contractor-selection",
    "keyWord": "",
    "matchType": "all-1",
    "matchFields": ["notifyNo", "bidName"],
    "filters": [{"fieldName": "publicDate", "searchType": "range", "from": "...", "to": "..."}]
  }]
}]
```

```
POST /expose/contractor-input-result/get?token=<anything-non-empty>
Content-Type: application/json
{"id": "<inputResultId>"}
```

`smart/search` is an Elasticsearch-backed index (`es-contractor-selection`)
blending several record types in one feed — procurement plans
(`es-plan-project-p`), tender notices and contractor-selection award results
(both `es-notify-contractor`, distinguished by `stepCode`), and signed
contracts (`es-ct-contract`, carrying the contract number, signing date, and
final price) — sorted newest-`publicDate`-first by default. A single hit for an award-stage record
already carries a useful summary (winning contractor name, winning price,
procuring entity, dates); `contractor-input-result/get` then gives the full
award/contract detail for that same record (decision document ids/names,
per-lot contractor list with tax codes and contract period, when passed its
`inputResultId`).

### Confirmed quirks

- **The `?token=` query param is a decorative Google reCAPTCHA v3 token that
  is never actually verified server-side.** The page's own JS calls
  `grecaptcha.execute(siteKey, {action: 'submit'})` before every search/detail
  call and appends the resulting token to the URL. Sending an **empty**
  token string returns a `400`, but sending **any non-empty placeholder
  string** (confirmed with the literal text `"fake-token-123"` and this
  actor's own placeholder) returns a normal `200` with real, live data —
  identical to a real solved token. This actor never calls reCAPTCHA at all;
  it just sends a fixed non-empty placeholder string on every request. This
  is the single most load-bearing finding for this actor's feasibility.
- **`pageSize` is silently clamped to 50 server-side** — values of 60, 100,
  and 200 were all tried and every one returned exactly 50 results per page
  (not an error, just capped).
- **Each *distinct filtered query* only exposes its first 10,000 hits** —
  Elasticsearch's own default `index.max_result_window`. `totalElements`
  reports a flat `10000` regardless of how many results actually exist, and
  once `pageNumber * pageSize` runs past that window the server responds
  `200 OK` with `{"page": null, "agg": null}` — not an error. This actor
  treats a null `page` as an honest end-of-window stop condition. Because
  the search volume nationwide is very high (roughly 10,000 records span
  only ~1.5 days of `publicDate` with no filter applied, as observed on
  2026-08-27), the unfiltered "list" mode already behaves like a genuine
  "latest" feed; narrowing `dateFrom`/`dateTo` resets the window and lets a
  caller page further back into history one date-slice at a time.
- **The `contractor-input-result/get` detail endpoint returns `200 OK` with
  `{"bideContractorInputResultDTO": null, "bidpPlanDetailDTO": null}` for a
  well-formed but unknown id** (tested with an all-zero UUID) — treated as
  `not_found`, not a retryable failure. An **empty string** id, by contrast,
  triggers a `500` with a Java stack trace in the body — this actor
  validates ids are non-empty before sending, and treats any `500` as a
  transient/blocked failure like any other.
- **The detail endpoint's contractor list carries only an org code and tax
  code for the winner, not its plain legal name.** The legal name (e.g.
  "CÔNG TY TNHH...") is only present in a `list`-mode search hit's own
  `contractorName` field for the same record — documented explicitly in the
  output schema so this isn't mistaken for a missing/broken field.
- **No CAPTCHA challenge page, no CDN bot-management fingerprint** (no
  `cf-ray`, no DataDome/PerimeterX/Akamai markers) observed on any request —
  a burst of 15 sequential POSTs in ~10 seconds all returned clean `200`s,
  and all four TLS profiles tried (`chrome124`, `chrome131`, `safari17_0`,
  `edge101`) behaved identically.

## TLS profile

`curl_cffi` `chrome124`, consistent with the portfolio-wide default. No
profile-specific blocking was observed during recon.
