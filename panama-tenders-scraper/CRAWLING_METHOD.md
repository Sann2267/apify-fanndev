# Crawling method

## Market check first

Before building anything, the seller cluster `scrapers_lat` — already confirmed to systematically own Peru (SEACE), Colombia (SECOP), Mexico (CompraNet), Argentina (Comprar), Paraguay (DNCP), and Chile (Mercado Publico) in this project's tender vertical — was checked specifically for Panama. Their Apify Store portfolio includes real-estate listing scrapers and a "Panama Emprende" business-registry scraper for Panama, but **no tenders/procurement actor for Panama** turned up in either their store listing or a direct Apify Store search for "panama tender"/"panamacompra". Confirmed clear to build.

## The obvious portal is the wrong one to scrape — but the right one is one hop away

The obvious target, `www.panamacompra.gob.pa` (PanamaCompra, the citizen-facing Angular SPA run by DGCP — Direccion General de Contrataciones Publicas), has a `robots.txt` that matters:

```
User-agent: *
Allow: /$
Allow: /Inicio/$
Allow: /Inicio/index.html
Allow: /Inicio/sitemap.xml
Allow: /Inicio/robots.txt
Disallow: /
Disallow: /Inicio/
Disallow: /Inicio/#!*
Disallow: /Inicio/#!/*
Disallow: /Inicio/?_escaped_fragment_=*
Disallow: /Inicio/?_escaped_fragment_=/*
```

Under the standard (Google-style) most-specific-rule-wins interpretation, this allows exactly the bare root shell and the sitemap, and disallows everything else for `User-agent: *` — i.e. every actual tender-listing/detail URL on this domain. No Claude/anthropic-ai mention (there's no per-bot carve-out at all, it's a blanket `*` group), but the *effect* for any bot, including this one, is a near-total crawl block on real content. **This actor does not fetch anything from `www.panamacompra.gob.pa` beyond having read this file.**

The fix wasn't to give up — DGCP runs a **second, separate host** for exactly this purpose: `panamacompraencifras.gob.pa` ("PanamaCompra in Figures"), specifically its `ocdsv2dev.panamacompraencifras.gob.pa` subdomain — a public OCDS (Open Contracting Data Standard) transparency portal. Its own page metadata says outright: *"Es un portal para poder visualizar los datos que se encuentran transformados en el estandar OCDS ... Puedes explorar y visualizar las contrataciones del gobierno de Panama"* — a portal built specifically so the public (and, implicitly, tools) can explore Panama's procurement data in OCDS form. Every API response's `publisher` field reads "Direccion General de Contrataciones Publicas (DGCP)", `license` is CC-BY 4.0, and there's a linked `publicationPolicy` PDF — this is DGCP's own deliberately-open data channel, not an unintentional leak.

Neither `ocdsv2dev.panamacompraencifras.gob.pa/robots.txt` nor its sibling `www.panamacompraencifras.gob.pa/robots.txt` exist as real resources — the Angular SPA's client-side catch-all router returns its own `index.html` (200, `Content-Type: text/html`) for the former, and IIS returns a plain "404 - File or directory not found" for the latter. Neither is a restriction, and neither mentions any bot by name — there's no file to mention anything in. This actor is built entirely against this second host.

## No login wall

Every endpoint below was fetched cold — no cookies, no prior request, no account — and returned real data on the very first try. There is no separate login-gated area for *viewing* this data at all (the whole point of the portal is public visualization).

## No WAF, no TLS-fingerprint gate

Plain `curl` with zero impersonation got clean `200`s immediately. The front server is `nginx`; no Cloudflare/Akamai/PerimeterX/DataDome headers or challenge cookies of any kind were seen. `curl_cffi` `chrome124` is used anyway, for consistency with the rest of this portfolio.

## Finding the real API — reverse-engineering the Angular bundle

The portal's `/api` route is client-side (Angular) and just re-serves `index.html` — there's no server-rendered API doc page. The actual endpoint paths were recovered by downloading the app's `main.<hash>.js` bundle and grepping it for `/api/v1/` string literals, which surfaced:

- `GET /api/v1/records` and `GET /api/v1/releases` — bulk OCDS feed listings
- `GET /api/v1/record/{ocid}` and `GET /api/v1/release/{id}` — single-record lookups
- `GET /api/v1/files` / `/api/v1/file/{source}/{type}/{year}/{month}` — bulk data-dump downloads (not used by this actor)

`/api/v1/records` was then probed directly and confirmed to return a genuine, well-formed OCDS record package.

## Two real quirks, both handled in `client.py`

1. **Incomplete TLS certificate chain, server-side.** `curl_cffi`'s bundled OpenSSL cert store fails every request with `CertificateVerifyError: unable to get local issuer certificate`, while Windows-native `curl` (schannel-backed, more permissive about fetching missing intermediates from a CA's AIA extension) succeeds silently on the identical URL. This is the same portfolio-wide pattern already seen on Nepal/Tunisia/Eswatini government sites — a server misconfiguration, not a local/proxy artifact. `verify=False` is set explicitly in `client.py`.
2. **`Accept: application/json` must be sent explicitly.** Without it, `curl_cffi`'s `chrome124` impersonation profile sends a browser-typical `Accept: text/html,...` header, and the Angular server's catch-all route returns the SPA's `index.html` shell (200 OK, ~148KB of HTML) instead of the real ~53KB JSON response. Confirmed by fetching the identical URL both ways during recon.

## The API is a flat bulk-export feed, not a search API

`GET /api/v1/records` returns 10 records per page (`?limit=`/`?pageSize=` are silently ignored — tested), paginated forward via an opaque `links.next` cursor URL (`searchAfter=<source>,<tenderId>,<epoch>,<epoch>,<id>`) — there is no page-number scheme. Every other query parameter tried during recon — `?year=`, `?source=`, `?sort=`, `?order=`, `?descending=` — was silently ignored (byte-identical response every time regardless of value). The feed's internal order groups by tender code within each buyer, not chronologically — the very first page returned tenders dated March–May 2024, and the second page's last record was dated *earlier* (February 2024) than the first page's records, confirming this is not date-sorted at all.

**Practical consequence:** there is no way to ask this API for "just this month's tenders" or "newest first." `list` mode in this actor pages forward from the beginning of the feed (or from a `startCursor` carried over from a previous run's `_nextCursor` output field) and returns whatever the feed yields, honestly reflecting the upstream data source's own limitation rather than fabricating a sort/filter that doesn't exist server-side.

`GET /api/v1/record/{ocid}` (used by `detail` mode) fetches exactly one tender by its OCDS `ocid`, in the same package shape with a one-element `records` array. An unknown `ocid` returns a clean `404` with a small JSON body (`{"detail":"No se encontraron resultados.","error":true}`) — `client.py` treats this as a definitive "not found" and does **not** retry it (retrying only applies to genuinely transient failures: network errors and unexpected non-200/non-404 statuses).

## Record content

Each `compiledRelease` is a real, rich OCDS object: `tender` (title, description, status, procurement method, procuring entity, a link back into PanamaCompra's own SPA), `awards` (value in PAB, line items with UNSPSC classification, supplier), `contracts` (value, period, and signed documents with **direct PDF download URLs** on `apisv3.panamacompra.gob.pa`), `parties` (buyer/procuringEntity/supplier, each with a PA-RUC tax-id identifier where available), and `sources` (which underlying PanamaCompra platform version — `panamacompra_v2` or `panamacompra_v3` — produced the record). This actor passes the `compiledRelease` object through close to verbatim (raw-passthrough convention), only adding the portfolio's standard `_input`/`_source`/`_scrapedAt` envelope.

## Encoding note

The response body is correctly UTF-8 — verified at the byte level (an accented buyer name's "i-acute"/"a-acute" characters round-tripped as the correct 2-byte UTF-8 sequences `0xC3 0xAD` / `0xC3 0xA1`). Any mojibake seen while debugging in a terminal during recon was purely a Windows console codepage display artifact, not a real data problem — the same false alarm already documented in this portfolio's Honduras actor. `client.py` decodes response bytes as UTF-8 explicitly (`r.content.decode("utf-8")`) rather than relying on `curl_cffi`'s charset auto-detection, since the `Content-Type: application/json` response header carries no explicit `charset=` parameter.

## The "dev" in the hostname

`ocdsv2dev.panamacompraencifras.gob.pa` has "dev" in its own hostname, which might suggest a staging/unstable environment. In practice: it is the *only* live host for this data (`ocdsv2.panamacompraencifras.gob.pa` doesn't resolve; `ocds.panamacompraencifras.gob.pa` 404s), it's the one search results and the wider PanamaCompraenCifras portal's own homepage actually link to, and it served consistent, well-formed data throughout recon with no errors. Treated as the real production endpoint DGCP currently operates under that name, not as an unstable target to avoid.
