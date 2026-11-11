# Uruguay Government Tenders Scraper

Extracts public procurement records from Uruguay's official state
purchasing agency, ARCE (Agencia Reguladora de Compras Estatales) — the
body that regulates and publishes every public tender, direct purchase, and
award made by Uruguay's government institutions.

## Why use this actor

- No account, login, or API key required — every record here is public
  open data, published under Uruguay's own Open Data License.
- Browse the newest tender and award activity across the whole platform,
  or narrow to a specific month.
- Fetch full detail for any purchase you already know: buyer, tender terms,
  award, winning supplier, and value — merged into one clean record.
- Stable, structured JSON output ready for spreadsheets, databases, or
  reporting pipelines.
- Runs on a schedule and exports straight to JSON, CSV, or Excel from Apify.

## How it works

1. Choose **List** mode to browse the most recent tender/award activity
   published across all of Uruguay's state institutions, or restrict it to
   one calendar month — or **Detail** mode to fetch one or more specific
   purchases you already know the ID for.
2. The actor reads Uruguay's own official open-contracting data feed — the
   same public data ARCE itself publishes for transparency.
3. Every stage of a purchase's life that has been published (call for
   tenders, amendments, and award) is merged into one record, alongside a
   handful of summary fields for quick reading.
4. Automatic retries handle temporary hiccups on the source's end, so you
   don't have to babysit failed requests.

## Input

**List mode** — browse the newest activity, or one calendar month:

```json
{
  "mode": "list",
  "year": 2026,
  "month": 8,
  "maxResults": 50,
  "fetchDetail": false,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"list"` or `"detail"`. |
| `year` / `month` | integer | Optional. Restrict the list to one calendar month — both must be given together, or both left blank to get the newest 500 records platform-wide instead. |
| `maxResults` | integer | Caps how many records this run returns. |
| `fetchDetail` | boolean | When `true`, enriches each list row with the full merged tender/buyer/award detail — one or more extra requests per row (slower). |
| `proxyConfiguration` | object | Apify Proxy settings (Residential recommended). |

**Detail mode** — fetch specific purchases by ID:

```json
{
  "mode": "detail",
  "idCompra": "1314718",
  "idCompras": [],
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `idCompra` | string | A single purchase's ID (find one from a "list" mode run's `idCompra` field). |
| `idCompras` | array | Multiple purchase IDs to fetch in one run. |
| `maxConcurrency` | integer | How many purchases to fetch in parallel. |

## Output

One dataset item per record. Real sample from a **list** run (newest
records, no detail):

```json
{
  "_input": "list:idCompra=1342093",
  "_source": "S1-ocds-rss",
  "_scrapedAt": "2026-08-27T16:28:11Z",
  "idCompra": 1342093,
  "releaseId": "adjudicacion-1342093",
  "eventType": "award",
  "pubDate": "Thu, 27 Aug 2026 13:25:16",
  "releaseUrl": "http://www.comprasestatales.gub.uy/ocds/release/adjudicacion-1342093",
  "guid": "adjudicacion-1342093"
}
```

Real sample from a **detail** run (`idCompra: 1314718`, a public tender
call — truncated; the full record also includes item lines, submission
method, and the buyer's contact details):

```json
{
  "_input": "1314718",
  "_source": "S1-record-plus-followed-releases",
  "_scrapedAt": "2026-08-27T16:29:27Z",
  "idCompra": 1314718,
  "ocid": "ocds-yfs5dr-1314718",
  "buyerId": "66-1",
  "buyerName": "Administración de las Obras Sanitarias del Estado",
  "tenderId": "1314718",
  "tenderTitle": "Concurso de Precios 6870/2026",
  "tenderStatus": "active",
  "procurementMethod": "open",
  "procurementMethodDetails": "Concurso de Precios",
  "tenderStartDate": "2026-01-31T10:05:06Z",
  "tenderEndDate": "2026-02-12T12:00:00Z",
  "tags": ["tender"],
  "awardsCount": 0,
  "totalAwardAmount": null,
  "awardCurrency": null,
  "suppliers": [],
  "latestReleaseDate": "2026-01-31T10:05:06Z",
  "releaseLinks": [ { "url": "http://www.comprasestatales.gub.uy/ocds/release/llamado-1314718", "date": "2026-01-31T10:05:06Z", "tag": ["tender"] } ],
  "releases": [ /* full release: buyer contact, tender terms, item lines, submission method */ ]
}
```

And a purchase that has reached award (`idCompra: 1367020`):

```json
{
  "idCompra": 1367020,
  "ocid": "ocds-yfs5dr-1367020",
  "buyerName": "Jefatura de Policía de Río Negro",
  "tags": ["award"],
  "awardsCount": 1,
  "totalAwardAmount": 172.13,
  "awardCurrency": "UYU",
  "suppliers": ["LIBRERIAS DEL LITORAL S A"],
  "releases": [ /* full award: winning supplier, item lines with unit price and quantity */ ]
}
```

| Field | Type | Description |
|---|---|---|
| `idCompra` | integer | Stable ID for this purchase, unchanged from its first tender call through award. |
| `ocid` | string | The purchase's Open Contracting ID. Only present once full detail has actually been fetched — never guessed on a bare list row. |
| `buyerName` | string | The government institution running this purchase. |
| `tenderTitle` | string | The tender's title or reference code, e.g. `Concurso de Precios 6870/2026`. |
| `procurementMethodDetails` | string | Spanish-language procurement modality (e.g. `Concurso de Precios`, `Compra Directa`, `Licitacion Publica`). |
| `tenderStatus` / `procurementMethod` | string | e.g. `active`, `complete`; `open`, `limited`, `direct`. |
| `tenderStartDate` / `tenderEndDate` | string | The bidding window, when a tender call exists. |
| `awardsCount` | integer | How many award entries exist for this purchase. |
| `totalAwardAmount` / `awardCurrency` | number / string | Combined award value (unit price × quantity across every awarded item) and its currency (UYU — Uruguayan peso). |
| `suppliers` | array | Names of all winning suppliers. |
| `tags` | array | Union of stage tags seen (`tender`, `tenderUpdate`, `award`, etc.). |
| `releases` | array | Every stage published for this purchase, verbatim — full tender terms, item lines, buyer contact details, and award/supplier information. |
| `eventType` / `pubDate` / `releaseUrl` | string | On list rows: which kind of update this specific row is, and when it was published. |
| `_error` | string | Present only when a record couldn't be retrieved (`not_found` for an unknown purchase ID). |

A list row fetched with `fetchDetail: true` has the same additional fields
as a detail record, merged onto it.

## Notes

- List mode without a year/month returns the newest 500 records
  platform-wide. Restricting to one month returns everything published that
  month — commonly several thousand records — capped at `maxResults`.
- `buyerId`/`buyerName` are only present once at least one stage has been
  published under that name — passed through as-is.
- Some purchases only ever get a direct award published, with no separate
  tender call (small/direct purchases) — `tenderTitle` and related fields
  stay empty in that case, which is expected, not a bug.
- `totalAwardAmount`/`tenderTitle`/etc. are this actor's own summary fold
  across the purchase's published stages (the source has no ready-made
  merged view) — the full unmodified stage-by-stage detail is always
  included too, so nothing is lost.

## Other actors in this collection

Related government tender/procurement scrapers built the same way: Ecuador
(SERCOP), Honduras (HonduCompras), Nigeria (NOCOPO), Ghana (GHANEPS),
Zambia (ZPPA), Jamaica (GOJEP), Uganda (EGP), Papua New Guinea (NPC),
Sierra Leone (NPPA), Nepal (Bolpatra), Eswatini (ESPPRA), Rwanda (Umucyo),
Namibia (CPBN), Trinidad & Tobago (ProcureTT), Botswana (ministry sites),
Malawi (MANEPS/PPDA), Tanzania (NeST), Bangladesh (CPTU), Pakistan
(PPRA-EPMS), Vietnam (VNEPS), Sri Lanka (Treasury), Zimbabwe (PRAZ),
Liberia (PPCC), Madagascar (ARMP), Cameroon (ARMP), Indonesia (SPSE),
Ethiopia (eGP), DR Congo (SIGMAP), Algeria (defense ministry), and Tunisia
(TUNEPS).
