# Crawling Method — Nicaragua Government Tenders (SISCAE)

**Last verified:** 2026-08-27

## Two different domains — only one of them is the real application

Nicaragua's public procurement is governed by SISCAE (Sistema de
Contrataciones Administrativas Electronicas), administered by the Direccion
General de Contrataciones del Estado (DGCE), part of the Ministerio de
Hacienda y Credito Publico. Two `nicaraguacompra.gob.ni` hosts exist and
behave very differently:

1. **`www.nicaraguacompra.gob.ni`** — a Plone-based marketing/information
   site (news, manuals, "about" pages). Not used by this actor.
2. **`www.gestion.nicaraguacompra.gob.ni/siscae/portal`** — the actual
   SISCAE application: a JBoss Portal (Apache Pluto portlet container)
   built on Apache MyFaces (JSF) portlets, `JBoss Web/2.1.3.SNAPSHOT`. This
   is where every search/listing this actor uses actually lives.

## Reachability — a false alarm, resolved by testing on Apify Cloud itself

Both this development session's own network and Anthropic's own web-fetch
infrastructure got immediate TCP-level connection resets/timeouts on every
`nicaraguacompra.gob.ni` host tried directly, on every `curl_cffi` TLS
profile. On its face this looked identical to the pattern this portfolio's
Ecuador actor already documented (regional network/peering limits that a
country-pinned Residential proxy fixes) — and Babak 28's own research notes
flagged this exact risk for Nicaragua going in.

**It turned out not to be that.** Rather than assume the Ecuador pattern by
analogy, this was tested directly: a throwaway recon actor was pushed to
Apify and run for real, comparing no-proxy (plain Apify datacenter IP),
generic Residential, and Nicaragua-pinned (`country: "NI"`) Residential —
all three reached `www.gestion.nicaraguacompra.gob.ni/siscae/portal` and got
identical clean `200` responses. Only `www.nicaraguacompra.gob.ni/robots.txt`
(the unrelated Plone marketing site, not used by this actor) stayed
unreachable across all three. **This actor's default proxy configuration is
therefore plain Residential with no country pin** — Apify's own plain
datacenter egress already works fine against the real target; Residential is
kept as a conservative default rather than because it was proven necessary.

## robots.txt

- `www.nicaraguacompra.gob.ni/robots.txt` (the Plone marketing site) SSL-resets
  or times out on every proxy/no-proxy combination tried — an infra quirk on
  a host this actor doesn't use, not a policy block (the same class of
  finding as Ecuador's unrelated NetScaler robots.txt signature block).
- `www.gestion.nicaraguacompra.gob.ni/siscae/robots.txt` (the actual host
  this actor talks to) returns a clean JBoss Web 404 "the requested resource
  (/siscae/robots.txt) is not available" — there is no robots.txt file at
  all on this host, so there is no restriction to violate, and no
  Claude/ClaudeBot/anthropic-ai mention anywhere (there is nothing to
  mention anything in).

## Login — viewing is fully public

The search form, results grid, and every field on it are served with zero
authentication — confirmed by fetching the search form and running searches
cold, with no prior session. `/siscae/portal`'s `LoginSmallPortlet` is for
registered government users/suppliers to manage their own accounts (publish
notices, submit bids) — a bidding/publishing gate, not a viewing gate,
exactly the "fine if only BIDDING requires login" carve-out from this
project's standing instructions.

## No WAF / TLS-fingerprint gate observed

`curl_cffi` `chrome124` got clean `200`s immediately on every path tried, no
challenge page of any kind.

## Two ways to list procedures, both plain HTML, no ViewState, no JSON API

### 1. Quick browse by status (not used by this actor's final input, but confirmed working)

`GET .../adquisiciones-gestion/busquedaProcedimientosVigentes?proc_estado=<ESTADO>`
is a stateless GET (VIGENTE/EJECUCION/CANCELADO/CERRADO/DESIERTO/ADJUDICADO/
SUSPENDIDO). Fast (~5-10s), returns whatever currently matches that single
status — observed exactly 10 rows per status across all 7 values during
recon, consistent with a small country's real currently-active tender
volume rather than an artificial cutoff (query-string attempts at a larger
page size or a "page 2" had no effect on this endpoint specifically — it
belongs to a different, simpler portlet than the full search form below).

### 2. Full search form (what this actor actually uses)

`GET .../adquisiciones-gestion/busqueda?accion=todos` returns the
`inicioBusqForm` search form. This actor extracts its **complete current
field set generically** (`extractor.extract_form_fields`, mirroring this
portfolio's Honduras ASP.NET actor) rather than hand-listing field names —
but it's genuinely simpler than Honduras: there is **no
`__VIEWSTATE`/`javax.faces.ViewState` token anywhere in this form** (the
only hidden fields are `<form>_SUBMIT`, `autoScroll`, and `_link_hidden_`).
The extracted field set is overlaid with the desired keyword / procedure
number / status(es) / institution / department / page-size, then POSTed
back to the form's own session-scoped `action` URL (which embeds this
session's JBoss Portal window id and `jsessionid`) on the **same session**
(`curl_cffi` persists the `JSESSIONID` cookie automatically).

Confirmed live and used by this actor:
- **Up to 100 results in a single request** (`resultadosItems=CIEN`) — a
  POST for VIGENTE+EJECUCION+ADJUDICADO with `resultadosItems=CIEN` returned
  exactly 100 real rows in 763KB of HTML.
- **Multiple status values in one search** — `estadoAdqPuId` is a repeatable
  checkbox field; this actor sends one pair per selected status.
- **Institution and department filters** resolved by case-insensitive
  substring match against the form's own dropdown option text (268
  institutions, 18 departments/regions, scraped live from the same form
  fetch) — the same pattern as Honduras' `entidad` filter.
- No pagination beyond a single request (100 rows) was confirmed working in
  the time available — `maxResults` is capped at 100 accordingly. A future
  session could investigate whether a second page is reachable.

Both list mechanisms render the **exact same** nested-table JSF grid
component (`listadoProcedimientos`), confirmed by comparing the `tbody` id
pattern and row markup byte-for-byte between the two sources — so one shared
parser (`extractor.parse_procedure_rows`) handles either.

## Row parsing — deeply auto-ID'd JSF markup, parsed structurally not by ID

Each procedure renders as one `<tr>` with three `<td>`s:

1. **~10% column**: procedure type + number as two stacked "leaf" `<span>`s
   (a JSF grid wraps each value span in an outer label span with the same
   text — `extractor._leaf_spans` finds spans with no nested `<span>` child
   to avoid double-counting).
2. **~75% column**: a nested `<table class="grid">` of label:value pairs
   (Estado, Codigo SIGAF, Publicacion, Cierre — label text varies slightly
   by status, e.g. a status-specific `cierre*` variant — Ultima
   Actualizacion), followed immediately by a sibling `<table class="empty">`
   with three unlabeled rows: institucion, classification(s) (multiple
   classifications render as sibling spans separated by a literal `", "`
   span — filtered out as punctuation-only fragments, not real data), and
   objeto (title).
3. **~15% column**: a "Mas Datos" action link — see below.

Parsing is entirely structural (nth-sibling-table, leaf-span order), not by
hardcoded auto-generated component IDs (which are stable *within* one page
render but not worth hardcoding when the structure itself is a reliable
anchor) — the same philosophy as this portfolio's Honduras/DR Congo actors.

## "Mas Datos" detail expansion — investigated, not implemented

Each row's "Mas Datos" link is a client-side JS `onclick` that sets a hidden
`_link_hidden_` field to that row's specific JSF component id and
re-submits the same results form in place (a portlet partial-postback,
not a navigable URL) — there is no stable "detail page URL" this actor
could accept as an input the way Honduras' `ProcesoHistorico.aspx?Id0=...`
links work. One attempt to simulate this postback (same session, full
field set, target row's `_link_hidden_` id set) returned a clean HTTP 200
but rendered the plain search form again rather than an expanded detail
view — some piece of server-side portlet-window state wasn't reproduced
correctly in the time available. Given the list view already surfaces rich
per-procedure fields (institution, type, number, classification, title,
publish/close/last-updated dates, status), this actor ships **list/search
mode only** and does not claim a "detail mode" that wasn't gotten working
reliably. Worth revisiting in a future session.

## The server is occasionally slow, not blocking

One POST search attempt during recon hit a clean 40s timeout with 0 bytes
received; retried immediately afterward at a 90s timeout and got a normal
200 in under 30s. No 403/429/challenge marker was ever observed — read as
an occasionally slow/loaded JBoss box (consistent with this app's era), not
a block. `REQUEST_TIMEOUT=90` and `MAX_RETRIES=4` with exponential backoff
cover this.

## Encoding

Response bodies declare and use valid UTF-8 — accented characters (á, é, í,
ó, ú, ñ, Ú) round-trip correctly at the codepoint level (verified: `Ú` in
"PÚBLICA" decodes to `U+00DA`, the mojibake seen in a Windows terminal while
debugging was purely a console-codepage display artifact, not a real data
problem — matching this portfolio's Honduras finding).

## Market check

Searched the Apify Store for "Nicaragua", "Nicaragua tender", "SISCAE", and
"Nicaragua compra" before building — no actor targeting Nicaragua's
procurement system was found. Per this project's standing "Babak 28"
research notes, the `scrapers_lat` seller cluster that has systematically
built scrapers for Peru (SEACE), Colombia (SECOP), Mexico (CompraNet),
Argentina (Comprar), Paraguay (DNCP), and Chile (Mercado Publico) was
already checked and does **not** include Nicaragua — independently
re-confirmed here (their only Nicaragua-related listing found is an
unrelated Encuentra24 used-car-listings scraper).
