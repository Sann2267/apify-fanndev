# Crawling Method — Tunisia Government Tenders (TUNEPS)

**Last verified:** 2026-08-27

## Target discovery — TUNEPS is the official platform

Tunisia's national e-procurement system, **TUNEPS** ("Tunisia National
e-Procurement System"), is run by the **Haute Instance de la Commande
Publique (HAICOP)** under the Presidency of Government. It has been
mandatory for ministries, public establishments (EPNAs) and public
enterprises to conduct procurement through it since a September 2018
decree. The official platform is `https://www.tuneps.tn` ("TUNEPS-3", the
current Angular rebuild). A separate HAICOP site,
`https://www.marchespublics.gov.tn`, publishes procurement regulations,
statistics and news but is not the live tender-listing system itself.

## robots.txt

`www.tuneps.tn/robots.txt` does not exist as a real robots.txt file — the
server is a pure Angular SPA with a catch-all route, so **every** path,
including `/robots.txt`, returns `200` with the same `index.html` app shell.
There is no `Disallow` directive anywhere and no
Claude/ClaudeBot/anthropic-ai mention (there is nothing to mention — the
"file" is just the SPA shell). `www.marchespublics.gov.tn/robots.txt` is a
real, clean file: `User-agent: *` / `Disallow:` (empty — allow all).

## No login required to view tender listings or detail

TUNEPS's Angular app is split into an authenticated buyer/supplier
back-office (`/acheteur/...`, `/fournisseur/...`, gated by `AcheteurGuard`/
`FournisseurGuard`) and a public portal (`/portail/...`, gated only by a
`NonAuthGuard` that just keeps already-logged-in users out of the anonymous
views — anonymous visitors pass through freely). The tender listing and
detail JSON endpoints this actor uses live under the public portal's own
service class and were confirmed reachable with a completely fresh,
cookie-less, token-less `curl_cffi` client — no `Authorization` header, no
session cookie, no CAPTCHA. TUNEPS does have separate registration/login
flows for buyers (to publish tenders) and suppliers (to submit bids), but —
consistent with every other tender-vertical actor in this project — that
wall sits only in front of *acting*, never in front of *viewing*.

**One dead end worth documenting:** the *authenticated* buyer-side
`ConsultationService`/`AppeloffreAcheteurService` classes in the same JS
bundle expose look-alike endpoints
(`/api2/acheteur/bid/publicData`, `/api2/acheteur/vSpShopMaster/publicData`)
whose name suggests "public" but which return a bare `401` with an empty
body for every TLS profile tested, even from a cookie-less client — despite
the app's own `AppHttpInterceptor` only attaching a `Bearer` token when one
already exists in `sessionStorage` (i.e. these are NOT gated by a
client-side auth check that a guest client could ever satisfy; the `401` is
enforced purely server-side regardless of the `publicData` URL suffix). This
actor does not use those paths — the real, working public endpoints live
under the separate `AppeloffreService` class (base path `portail`, not
`acheteur`), described below.

## The real find: a genuinely public JSON API behind the Angular SPA

`www.tuneps.tn` renders nothing server-side — reading its `main.js` bundle
directly (16 MB, un-minified enough to grep class/method names) surfaces the
Angular services backing the public portal's "Appel d'offres" (tender)
pages. The relevant service, `AppeloffreService`, hard-codes:

```js
static get base() {
    return urlJoin(environment.server.hostSource, 'portail');
    // environment.server.hostSource == 'https://www.tuneps.tn/api2'
}
search(searchObject) {
    return this.http.post(urlJoin(AppeloffreService.base, 'bid/master', 'data'), searchObject);
}
findById(id) {
    return this.http.get(urlJoin(AppeloffreService.base, 'bid/master', id));
}
```

Confirmed live and public with zero auth, across `chrome124`/`chrome131`/
`safari17_0`/`edge101` TLS profiles identically:

```
POST https://www.tuneps.tn/api2/portail/bid/master/data
GET  https://www.tuneps.tn/api2/portail/bid/master/{epBidMasterId}
```

The `POST` body shape (from the same bundle's `SearchObject`/`Pagination`/
`Sort`/`CriteriaSearch` domain classes):

```json
{
  "pagination": {"limit": 100, "offSet": 0},
  "sort": {"nameCol": "publicDt", "direction": "desc nulls last"},
  "dataSearch": [{"key": "publicYn", "value": "Y", "specificSearch": "="}],
  "listSort": [],
  "listCol": []
}
```

`publicYn == "Y"` is the exact filter TUNEPS's own public "Liste A.O."
component (`ListAppelOfferComponent`/`OffersComponent`) applies — it is what
distinguishes a tender actually published to the public portal from one
still sitting in a buyer's internal draft/review workflow. This actor always
includes it.

A list response:

```json
{
  "code": "200",
  "payload": {
    "total": 59331,
    "data": [
      {
        "epBidMasterId": 134251,
        "bidNo": "20260805154",
        "bidModSeq": "00",
        "bidInstNm": "Hôpital d'Enfants",
        "bidNmFr": "«LA MISE A LA DISPOSITION D'UN AUTOMATE D'IMMUNOANALYSE...»",
        "bidNmAr": "...",
        "bidNmEn": "...",
        "publicDt": "2026-08-26 18:42:56.364903",
        "publicYn": "Y",
        "bdRecvEndDt": "2026-09-25 09:30:00.0"
      }
    ]
  }
}
```

A detail response for the same `epBidMasterId` returns a much richer ~90-key
object: full submission window (`bdRecvStartDt`/`bdRecvEndDt`/`bdOpenDt`),
procedure/price/financing/guarantee type (each with `StrFr`/`StrAr`/`StrEn`
label variants), buyer registration info, contact staff name, framework/
consortium/international-bid flags, and more — see `output_schema.json`.

### Confirmed quirks

- **Data is genuinely live, not stale.** At recon time (2026-08-27), the
  newest published tender's `publicDt` was the same day, and open tenders'
  `bdRecvEndDt` values run months into the future (Sept/Oct 2026) —
  consistent with an actively-used production system, not an abandoned or
  demo instance.
- **TLS cert chain is missing an intermediate** (`unable to get local issuer
  certificate`) — the same failure mode already seen on Nepal's and
  Eswatini's government hosts in this project. `verify=False` is required
  on every request (see `client.py`); no TLS-profile fallback was needed
  otherwise (chrome124/chrome131/safari17_0/edge101 all behaved identically).
- **Text encoding is correct UTF-8 — an earlier `curl_cffi` inspection that
  looked like mojibake was a Windows-console display artifact, not a real
  data problem.** Verified against raw response bytes: accented French
  (`Hôpital`, `pièces`, `à`) and Arabic script both decode correctly; no
  transliteration or encoding fix-up is applied by this actor.
- **`bidNmEn` is not a real English translation** — TUNEPS stores whatever
  text the buyer entered in that field, which in practice is often identical
  to the French or Arabic title (buyers rarely fill in a distinct English
  version). Passed through as-is rather than dropped, since it is
  occasionally genuinely different.
- **An unknown-but-numeric `epBidMasterId` returns a `200`, not a `404`** —
  the envelope carries `{"code": "420", "payload": {}}` instead. A
  non-numeric id instead hits a generic Spring "Whitelabel Error Page" (HTML,
  `400`). Both are treated as `not_found` by `client.py`'s
  `fetch_bid_detail`, not as a transient failure worth retrying.
- **`bdRecvEndDt`/`publicDt`/etc. are plain SQL-style timestamps**
  (`YYYY-MM-DD HH:MM:SS[.ffffff]`), not ISO 8601 — the `openOnly` filter's
  `_now_sql()` helper in `main.py` formats the comparison value to match.
- **Pagination is genuinely stable via `limit`/`offSet`** — unlike some peer
  targets in this project (e.g. Tanzania's ignored `cursor`), `limit=100`
  and incrementing `offSet` were confirmed to return distinct, non-repeating
  pages. The one caveat: because the default `publicDt desc` ordering is a
  live, constantly-changing feed (new tenders are published throughout the
  day), a long-running `maxResults` pull can occasionally see a page shift
  under it; `main.py` de-duplicates by `epBidMasterId` and stops early
  (rather than looping) if an entire page turns out to be already-seen.
- **Keyword search (`bidNmFr` + `upper_like`) is accent- and
  case-insensitive server-side** — searching `"hopital"` matches records
  titled `"Hôpital ..."`. Confirmed via TUNEPS's own filter-panel
  `CriteriaSearch` usage in the JS bundle.
- **No WAF/bot-challenge fingerprint observed** — no CAPTCHA, no `cf-ray`/
  DataDome/PerimeterX markers, no rate-limit 403s during recon (unlike
  Tanzania's NeST). A generic `cookiesession1` cookie is set but never
  required on subsequent requests.

## TLS profile

`curl_cffi` `chrome124`, consistent with the portfolio-wide default, with
`verify=False` for the missing-intermediate cert chain (see above). No
profile-specific blocking was observed.
