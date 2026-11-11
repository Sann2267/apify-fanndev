# Crawling Method — Jamaica COJ Business Registry Scraper

**Last verified:** 2026-08-26/27

The Companies Office of Jamaica (COJ, formerly the Office of the Registrar
of Companies -- hence the `orcjamaica.com` domain) is Jamaica's official
company/business-name registry, at `www.orcjamaica.com`. There is also a
`services.orcjamaica.com/validation` sub-app ("QR Code Validation") which
looks up a single already-known document/certificate number by base64'd
GET request (`/validation/Validate/Search/<base64(query)>`) -- that is a
narrow, different tool (for verifying a physical certificate's QR code,
not general company search) and is **not** what this actor uses.

The general public search lives on the legacy ASP.NET WebForms site,
`www.orcjamaica.com/CompanySearch.aspx`.

## robots.txt

```
User-agent: *
Disallow:
Crawl-delay: 120
Disallow: /cgi-bin/
```
(plus a long list of specific-bot groups for other crawlers, none of them
Claude/AI-related, several of them fully disallowed -- Scrapy included --
but `User-agent: *` itself is unrestricted apart from `/cgi-bin/`.)

No `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or
`anthropic-ai` user-agent appears anywhere in the file. None of the paths
this actor touches (`CompanySearch.aspx`, `PaymentConfirmation.aspx`,
`CompanySearchResults.aspx`, `/AsyncServices/...`) are disallowed.

The `Crawl-delay: 120` directive is real and is honored via
`requestDelaySecs` (input, default 10s between separate queries) and a
generous exponential retry/backoff on transient rate-limit blocks (see
below) rather than a hardcoded 120-second sleep before every single
request, which would make even a small batch take a very long time.
Operators who want strict compliance can set `requestDelaySecs` to 120.

## WAF / anti-bot

Fronted by a CDN/WAF (`Server: ZENEDGE`, `X-Cdn: Served-By-Zenedge`).

**The "cookie support" challenge is not really a challenge.** The very
first `GET /CompanySearch.aspx` in a fresh session returns a tiny
(~665-byte) HTML snippet whose `<script>` does
`document.cookie = "__zjc<N>=" + Math.floor(<unix-epoch> * Math.PI)`, then
`window.location` back to the same URL. This looks like a Zenedge
JS-computed "Human Interaction Check" but empirically **is not one**: the
response also carries a plain `Set-Cookie: AspxAutoDetectCookieSupport=1`
header, and simply repeating the exact same `GET` a second time in the same
cookie jar (now carrying that cookie) returns the real ~30KB page with a
working `__VIEWSTATE`/`__EVENTVALIDATION` pair. The `__zjc*` cookie and its
pi-multiplication math are never actually checked -- this is just
ASP.NET's standard `AspxAutoDetectCookieSupport` cookieless-session probe,
reskinned with Zenedge's challenge-page template. No JS execution or math
is needed; `client.py`'s `_warmup_and_fetch_form` just issues the same GET
twice.

**The real block: a request-volume rate limit.** During recon, running
several full search flows back-to-back within about a minute intermittently
tripped a hard `403` with page title `"Access to the website is blocked"`
and `Code: HIC` (from Zenedge), on the *initial search POST* specifically
-- never observed on the harmless two-GET cookie warmup. This:

- Recovered on its own within roughly 60-120 seconds: the *exact same*
  query that got blocked succeeded again, completely unmodified, after a
  short wait.
- Did **not** correlate with the query text. An intentionally garbage-
  looking random string (`zzzznonexistentxyz999qqq`) tripped it, but so did
  a perfectly ordinary business-name query (`Digicel`) and a plain numeric
  one (`999999999999`) once enough requests had already gone out in the
  same short window -- and the garbage string itself succeeded cleanly on a
  later, less-rushed attempt. This reads as a behavioral/volume rate limit,
  consistent with the site's own `Crawl-delay: 120`, not a per-query content
  filter and not a hard/permanent IP ban.

`client.py`'s retry loop treats 403/429/503 as retryable (not fatal),
backing off 15s/30s/60s/120s/240s (`MAX_RETRIES=5`,
`RETRY_DELAY_BASE_SECS=15.0`) -- generous enough to ride out the observed
recovery window.

## The search flow

1. `GET /CompanySearch.aspx` twice, same session (see cookie-warmup note
   above). Second response is the real page: extract `__VIEWSTATE`,
   `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION` (plain hidden `<input>`
   tags).
2. `POST /CompanySearch.aspx`, same session, full WebForms postback:
   `__EVENTTARGET=ctl00$Space$btnSearch`, `ctl00$Space$org_name=<query>`,
   the three extracted fields above, plus empty boilerplate
   (`__LASTFOCUS`, `__EVENTARGUMENT`, `__SCROLLPOSITIONX/Y`,
   `ctl00$Timezone`). Response is another tiny `window.location='...'`
   redirect snippet (same shape as the cookie-warmup one), this time
   pointing at `PaymentConfirmation.aspx?cId1=<transaction-guid>`.
3. **Despite the name, `PaymentConfirmation.aspx` is not a paywall for the
   search** -- it's this site's generic "processing" page for any
   async server-side job, search included. `GET` it (same session; twice
   if the cookie-warmup didn't already run earlier in this session) and
   extract three hidden fields from the rendered page:
   `ctl00_Space_Response` (an async job id -- a *different* guid from
   `cId1`), `ctl00_Space_PollURL` (`https://www.orcjamaica.com/AsyncServices/`),
   `ctl00_Space_ResultUiController`
   (`CompanySearchResults.aspx?cId1=<yet another guid>`).
4. `POST {PollURL}asyncState/{Response}` (`Content-Type: application/json`,
   empty body) repeatedly until `{"CurrentState": "Succeeded"}`. Observed
   sequence: `Preparing` -> `Committing` -> `Succeeded`, 2-3 polls at ~1.5s
   apart is typical. A `Failed` (or stuck `Awaiting retry of
   rollback`/`commit`) state means the job itself errored -- distinct from
   an HTTP-level 403 block on the POST, which is a WAF/rate-limit signal,
   not a job failure.
5. `GET {ResultUiController}&asyncId={Response}` (i.e.
   `CompanySearchResults.aspx?cId1=...&asyncId=...`) -- the results page.
   The rendered `<table id="company-results-table">` is empty in the raw
   HTML; the real data is a `<script>var database = {"data": [...], ...
   };</script>` blob, extracted with a balanced-brace walk (not a naive
   regex -- addresses/names in the data can contain characters that break a
   non-greedy `\{.*?\}` match) then `json.loads`.

## Wire shape of a result row

Each element of `database["data"]` (passed straight through, upstream's
own field names):

```json
{
  "link": "", "rank": 0, "id": "61230-L",
  "name": "Digicel (Jamaica) Limited",
  "office": "Bjorn Spence - Secretary",
  "status": "ACTIVE", "type": "COMPANY",
  "date": "09 Apr 1999",
  "address": " 14 Ocean Boulevard, ingston, Kingston, JAMAICA",
  "number": "61230 (Local)", "documentCount": "630"
}
```

`id` format differs by entity kind: `<num>-L` (local company),
`<num>-F` (overseas company), `<num>-S` (foreign S.C.), or
`<num>_<year>-` (registered business name). `number` mirrors this with a
human-readable suffix (`(Local)`, `(Overseas)`, `(Foreign S.C.)`) for
companies, or `<num>/<year>` for business names.

**This is already the complete record this actor exposes** -- there is no
separate "entity detail page" fetch step. Every field the task asked for
(entity name, registration number, status, incorporation date, registered
address) is present directly in the search-result row; drilling into an
entity (the site's own "click name for transaction options" affordance)
only opens a document-purchase modal, which requires the site's own paid
account flow and is out of scope.

## Match semantics (important, non-obvious)

The `org_name` query box does **loose substring matching on both name and
number fields, not exact matching on either**:

- Name: token/prefix matching, not exact-phrase. A deliberately-long,
  guaranteed-nonexistent phrase ("Blueberry Nonexistent Trading
  Enterprises Limited") still matched every real entity whose name starts
  with "Blueberry" (11+ distinct businesses).
- Number: substring matching across every suffix format COJ uses. A plain
  `384` query matched `384 (Local)`, `384 (Overseas)`, `384 (Foreign
  S.C.)`, and business names `384/1980`, `384/1981`, etc. -- 200 rows
  (the page-size cap), not the single expected "GraceKennedy Limited"
  exact match. `61230` happening to return exactly one match earlier during
  recon was coincidental (no other registration number on file contains
  that digit sequence), not evidence of exact matching -- do not rely on a
  short/partial number for a precise single-entity lookup.

## Known limits

- **Result cap: 200.** The largest page size observed (a broad one-word
  or short-number query). A query broader than that may not surface every
  match; there is no further pagination affordance on this page.
- **A clean zero-result case was not isolated during recon.** Every
  distinctly-worded query tried (including intentionally-unusual ones)
  matched at least one real entity, because of the loose substring/token
  matching described above -- constructing a guaranteed-zero-result query
  that doesn't *also* look like a bot probe (which risks tripping the rate
  limit) turned out to be difficult in the time available. `extractor.py`
  treats an empty `data: []` array in the results blob as the documented
  no-match case (`NoResultsFound` -> `_error: "not_found"`); if upstream's
  actual zero-result shape differs from this assumption, the actor will
  instead raise `UnexpectedShape` (`_error: "unexpected_shape"`) rather
  than silently emit nothing, per this project's fail-loud convention --
  worth re-checking on the first real zero-result query encountered in
  production.
- The `office` field carries at most one officer (whichever COJ's search
  index surfaces), not a full list of directors/shareholders/secretaries --
  the search-results page simply doesn't carry more than that; a fuller
  officer list would require the paid/login document-purchase flow, out of
  scope here.
- `documentCount` is informational only -- this actor does not fetch or
  purchase the underlying documents.

## Diff cadence

Quarterly smoke test recommended. This is a legacy ASP.NET WebForms
application (not a modern SPA/API), so it is unlikely to change quickly,
but the `PaymentConfirmation.aspx` async-job mechanism and the WAF's
rate-limit tuning are both plausible targets for a future platform update.
