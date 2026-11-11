# Crawling Method — Ecuador Government Tenders (SERCOP OCDS)

**Last verified:** 2026-08-27

## Target discovery — two separate SERCOP systems, only one of which is public

Ecuador's public procurement is regulated by **SERCOP** (Servicio Nacional de
Contratacion Publica). SERCOP actually runs **two distinct web systems** on
related `compraspublicas.gob.ec` domains, and they behave completely
differently:

1. **SOCE — Sistema Oficial de Contratacion Publica**
   (`www.compraspublicas.gob.ec/ProcesoContratacion/compras/`) — the
   *bidding* system where suppliers register, submit offers, and
   institutions run procurement processes. Confirmed by direct fetch: this
   page is a **hard login wall** (RUC + username + password, "Acuerdo No.
   012-2019" data-policy acceptance) with no public browsing at all.
2. **"Contrataciones Abiertas Ecuador" — the OCDS open-data platform**
   (`datosabiertos.compraspublicas.gob.ec`) — a **separate, explicitly
   public** platform built by SERCOP together with the **Open Contracting
   Partnership (OCP)** and **CAF** (Banco de Desarrollo de America Latina),
   specifically so third parties can search and bulk-download procurement
   data under the Open Contracting Data Standard (OCDS) without an account.
   Confirmed independently, not from a tender-alert blog:
   - The Open Contracting Partnership's own Data Registry lists SERCOP as a
     publisher (`data.open-contracting.org/en/publication/110`), naming
     `datosabiertos.compraspublicas.gob.ec` as the source, confirming OCID
     prefix `ocds-5wno2w`, a CC BY 3.0 EC license, and daily-updated bulk
     JSON/CSV/XLSX exports last retrieved by OCP's own crawler on
     2026-08-05.
   - The platform's own `/PLATAFORMA/acerca` ("About") and
     `/PLATAFORMA/datos-abiertos/api` ("API") pages (read via a 2026-06-10
     Wayback Machine snapshot, see below) describe it as a joint
     SERCOP/OCP/CAF initiative and document the query API in full.

**This actor only uses system #2.** The login wall on system #1 is a
BIDDING system's account gate (submitting offers), not a block on viewing
procurement data — exactly the "fine if only BIDDING requires login"
carve-out. All of SERCOP's actual tender/award/contract *data* lives on the
open-data platform and needs no account.

## robots.txt — an infra quirk, not a policy block

Every attempt to fetch `robots.txt` on any `compraspublicas.gob.ec` /
`sercop.gob.ec` host (both live, and in a 2022 Wayback Machine snapshot)
returns the same **Citrix NetScaler Application Firewall block page**:

```
Violation Category: APPFW_SIGNATURE_MATCH / APPFW_STARTURL
Violation Details: ... Signature violation rule ID 1852: web-misc robots.txt
access <blocked> ... msg=Disallow Illegal URL ...
```

This is a NetScaler AppFW signature that flags the *literal string*
`robots.txt` as a suspicious request pattern and blocks it outright — it has
done so since at least April 2022 per Wayback Machine history, on every host
tested. **No robots.txt content is retrievable at all**, from any client,
with or without a token — this is a long-standing WAF misconfiguration, not
a deliberately published `Disallow` policy. There is consequently no
robots.txt naming Claude/ClaudeBot/anthropic-ai or any other bot, because
there is no retrievable robots.txt at all. This is documented here in full
rather than treated as a silent pass.

## No WAF/TLS gate observed on the actual open-data API paths

The NetScaler AppFW signature above appears keyed specifically to the
`robots.txt` path pattern. The open-data platform's real paths —
`/PLATAFORMA/*`, `/PLATAFORMA/api/search_ocds`, `/PLATAFORMA/api/record` —
were not observed hitting that or any other WAF signature in any recon
performed (Wayback snapshots of the platform's own docs pages return clean
200s with ordinary content, and OCP's own crawler status confirms ongoing
successful automated access to the bulk-download side of the same
platform).

## Reachability: several outside networks could not reach this host at all

**Important, and reported transparently rather than glossed over:** during
recon, `datosabiertos.compraspublicas.gob.ec` and `portal.compraspublicas.gob.ec`
(both resolving to `190.152.44.111` / `157.100.62.6`) were **unreachable —
bare TCP connect timeouts on port 443 — from every network tested**: this
session's own residential ISP connection (multiple attempts, `curl`,
`curl_cffi`, and a raw Python `socket.create_connection` all timed out after
15-20s), and separately Anthropic's own web-fetch infrastructure (also
timed out with no response). By contrast, **other hosts on the same
`gob.ec` domain resolved and answered normally** from the same networks:
`sercop.gob.ec` (redirects to `www.sercop.gob.ec`), `www.compraspublicas.gob.ec`
(reachable, serves the SOCE login page above), and `compraspublicas.gob.ec`
(reachable, redirects to the SOCE login page too) — all on a *different* IP
subnet (`157.100.62.100` / `190.152.44.100` / `.126` / `.4`) than the
unreachable open-data cluster.

This pattern — one specific IP pair unreachable while sibling hosts on the
same domain answer fine — is more consistent with **regional network
routing/peering limits to that particular server** (a known characteristic
of some Latin American government hosting) than with a deliberate anti-bot
block: there is no WAF challenge page, no TLS-level rejection, and no
HTTP-level 403 — just an unanswered SYN. OCP's own crawler independently
confirms the same platform *is* reachable and actively harvested from
somewhere (last retrieval logged 2026-08-05), which rules out the platform
being simply offline.

**Consequence for this actor:** `proxyConfiguration` defaults to
`RESIDENTIAL` proxies geolocated to Ecuador (`apifyProxyCountry: "EC"`)
rather than this portfolio's more common no-proxy/datacenter default, on the
theory that a real Ecuadorian residential exit IP is far more likely to have
a working network path to this specific server than an arbitrary
international one. This could not be verified end-to-end from local
development (this Apify account's "Proxy external access" feature, needed
to use Apify Proxy from *outside* the platform, is not enabled) — **the real
test was the Apify Cloud `apify call` smoke test after deployment, which
confirmed it**: with `apifyProxyCountry: "EC"`, both `search_ocds` and
`record` returned real 200 JSON responses on the first deployed run, no
retries needed. The theory holds up in practice.

## The API — read directly from the platform's own documentation page

`/PLATAFORMA/datos-abiertos/api` (fetched via a 2026-06-10 Wayback Machine
snapshot, since the live host could not be reached directly — see above)
documents two GET endpoints in full, including worked examples with real
data:

### 1. `search_ocds` — keyword + year search

```
GET https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/api/search_ocds
    ?year=2020&search=agua&page=1&buyer=LOS%20RIOS&supplier=TINAJERO
```

| Param | Required | Notes |
|---|---|---|
| `year` | **Yes** | Integer, 2015 - current year. |
| `search` | **Yes** | At least 3 characters. **There is no "browse everything" call** — every search needs a keyword, which is why this actor's `mode=list` requires `searchQuery`. |
| `page` | No | Result page, 1-based. |
| `buyer` | No | Narrows to a buyer institution keyword. |
| `supplier` | No | Narrows to a supplier/contractor keyword. |

Response shape (from the docs page's own worked example):

```json
{
  "total": 1, "page": "1", "pages": 1,
  "data": [{
    "id": 7390, "ocid": "ocds-5wno2w-001-LICO-GPLR-2020-2805",
    "date": "2020-06-15", "buyerId": "EC_RUC-1260000140001-2805",
    "buyerName": "GOBIERNO PROVINCIAL DE LOS RIOS",
    "title": "001-LICO-GPLR-2020-2805", "description": "...",
    "year": 2020, "internal_type": "Licitacion",
    "single_provider": "TINAJERO GARCIA HECTOR RAMIRO"
  }]
}
```

This actor paginates by incrementing `page` until either `page >= pages`
(from the response itself) or `maxResults` is reached — it trusts the
upstream `pages` count rather than guessing from an empty-page heuristic,
since the docs show `pages` is always present.

### 2. `record` — full OCDS release history for one ocid

```
GET https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/api/record?ocid=<ocid>
```

**The docs page shows one response shape; the live endpoint returns a
different one — confirmed by an actual cloud smoke-test call, not assumed.**
The docs' worked example nests the payload under a top-level `records`
array (an OCDS "record package" shape): `{"uri": ..., "license": ...,
"records": [{"ocid": ..., "releases": [...]}]}`. The real live response
(fetched through the deployed actor over an Ecuador-geolocated Apify
Residential proxy, ocid `ocds-5wno2w-SIE-003-SLUCAS-2022-129262`) is
instead a **flat OCDS release package** with no `records` wrapper at all:

```json
{
  "uri": "https://portal.compraspublicas.gob.ec/sercop/datos_abiertos/",
  "license": "https://creativecommons.org/licenses/by/3.0/ec/",
  "version": "1.1",
  "releases": [ { "tag": ["planning","tender","award"], "buyer": {...},
                  "tender": {...}, "awards": [...], "parties": [...],
                  "auctions": [...], "planning": {...} } ],
  "publisher": {"uid": "ocds-5wno2w", "name": "Servicio Nacional de Contratacion Publica (SERCOP)", "scheme": "OCDS"},
  "extensions": [ "...ocds_enquiry_extension...", "...ocds_lots_extension...",
                  "...ocds_techniques_extension...", "...ocds_auctions_extension...", "..." ],
  "publishedDate": "2023-02-10T05:49:35-05:00",
  "publicationPolicy": "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/documentos/politica-publicacion-SERCOP-OCDS.pdf"
}
```

This actor's `client.py`/`extractor.py` follow the confirmed **live** shape
(`data.get("releases")` directly, no `records` unwrapping) rather than the
docs page's example. The `releases` entries are rich, genuine OCDS 1.1 data
with several official extensions enabled (enquiries, lots, techniques,
auctions, value breakdown, competitive, bid) — the real example above
includes a full electronic reverse-auction history (bid-by-bid, with
tenderer identity and value per round), buyer/supplier `parties` with
address and RUC-based identifiers, and enquiry Q&A threads between bidders
and the buyer. The merge logic in `extractor.py` follows the same OCDS
field names used by this portfolio's other confirmed-live OCDS integrations
(Nigeria NOCOPO, Tanzania NeST): `tender.id/title-or-description/status/
procurementMethod`, `planning.budget.amount.{amount,currency}` (frequently
absent — many records' `planning.budget` only carries an internal budget
line `id`, no amount), `awards[].value`, `awards[].suppliers[].name`.

**An unknown/malformed `ocid` returns 200 with an empty response** (no
`releases` key) rather than a 404 — handled as `RecordNotFound` -> a clean
`_error: "not_found"` record. Confirmed live: SERCOP's own docs-page example
ocid (`ocds-5wno2w-001-LICO-GPLR-2020-2805`, dated 2020) and one ocid
freshly pulled from a live `search_ocds` "Catalogo electronico - Compra
directa" (small electronic-catalog purchase order) result both came back
`not_found` on `record` — direct-catalog purchase orders below the formal
threshold appear not to get a full OCDS release compiled, unlike formal
tender modalities (Licitacion, Subasta Inversa Electronica, Menor Cuantia,
Contratacion Directa above threshold), which do. This is reported as an
observed, real upstream data-coverage gap, not a bug in this actor.

## Currency

Ecuador's official currency is the US Dollar (fully dollarized since 2000),
so `budgetCurrency`/`awardCurrency` are expected to read `USD` rather than a
local currency code.

## TLS profile

`curl_cffi` `chrome124`, consistent with the portfolio-wide default. No
WAF/fingerprint gate was observed on the actual API paths (only the
unrelated `robots.txt` NetScaler signature, and the raw-TCP unreachability
issue, both described above) — no profile-specific blocking was identified
during recon, but this is worth re-checking once the cloud smoke test
confirms live reachability.

## Market check

Searched the Apify Store for "ecuador", "ecuador tender", "SERCOP", and
"compras publicas" before building. No actor targeting Ecuador's tender
system specifically was found. Adjacent LATAM aggregators exist
(`iadb-tenders` by `foxlabs`, covering IADB-funded projects across 26 LATAM
countries; `licitaciones-latam` by `karmic_mastodon`, covering Colombia/
Brazil/Peru/Chile/Mexico/Argentina) but neither ingests SERCOP directly nor
lists Ecuador among their sources. The seller `scrapers_lat`, who has built
several other Ecuador-specific scrapers (SRI RUC registry, Plusvalia real
estate), has no tender/procurement actor in their portfolio either.
