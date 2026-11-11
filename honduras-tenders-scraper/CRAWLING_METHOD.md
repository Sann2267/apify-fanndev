# Crawling method

## The obvious domain is dead — a real finding, not a dead end

Every third-party source ("HonduCompras licitaciones en línea", official-looking search results) points at `honducompras.gob.hn` (and the regulator's own site, `oncae.gob.hn`). Both are **currently unreachable** from every network path tested in this project (a `curl_cffi` profile ladder — chrome124/safari17_0/edge101 — and an independent fetch tool both got connection timeouts/refusals on both domains, on both `http://` and `https://`).

Checking the Wayback Machine (`web.archive.org`) confirms this is not a transient block: the domain's most recent snapshot (May 2026) is generic **WordPress boilerplate content** — "¡Hola, mundo!", a "career" page, a blog post titled "Custom vs. Template Websites: The Case for Tailored Development" — i.e. the domain/hosting lapsed and got overtaken by unrelated web-agency filler content sometime between January and May 2026. It has not been re-crawled since (no snapshot between May and August 2026 — consistent with it still being down/dead now). Separately, `web.oncae.gob.hn` — which the Open Contracting Partnership's data registry cites as the source of ONCAE's daily-updated OCDS open-data export — no longer resolves in DNS at all (`NXDOMAIN` on Google's own resolver, 8.8.8.8).

**Do not build against these domains.** They are not blocking bots; they are simply gone.

## The fallback: HonduCompras 1.0, still alive on a different subdomain

ONCAE's citizen-facing homepage for the legacy system, `h1.honducompras.gob.hn`, IS still live and correctly identifies itself (`<meta name="author" content="Oficina Normativa de Contratacion y Adquisicion del Estado, ONCAE">`, copyright 2005-2017). It links directly to the real, working search tool on yet another subdomain:

```
http://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx
```

This is the same recurring pattern seen elsewhere in this project's tender vertical (Sierra Leone's NPPA, Malawi's PPDA, Botswana's ministry sites): when a country's modern e-GP front door fails, an older corporate/legacy system from the same regulator is often still quietly serving the same underlying data. This actor is built entirely against `sicc.honducompras.gob.hn`.

Two adjacent legacy pages under the same `/HC` application — `Oportunidades_negocio/Default.aspx` ("business opportunities") and `Contratos/Default.aspx` ("contracts") — return a generic ASP.NET 500 runtime error on every attempt. These are genuinely broken/decommissioned sub-features of the old app, not an auth wall or a block — `busquedahistorico.aspx` alone already covers both current and historical processes via its "Etapa" (stage) filter, so they are not needed.

## Access checks

- **`robots.txt`**: `sicc.honducompras.gob.hn/robots.txt` → plain HTTP 404 (classic IIS "the page cannot be found" — there is no file at all, so no restriction to violate). The sibling `h1.honducompras.gob.hn/robots.txt` is even more explicit: `User-agent: * / Allow: /`. No mention of Claude/anthropic-ai/AI crawlers anywhere (there's nothing to mention anything in).
- **Login for viewing**: none. The homepage links to a *separate* login page, `sicc.honducompras.gob.hn/DCC/webapp/login.aspx`, explicitly labelled "Usuarios de Sistema (Difusión de procesos)" — that's for government procurement officers to **publish** notices, not for the public to browse them. The search form, results grid, and every individual tender's detail page (contact info, line items, documents, bidders, award) are served with zero authentication — confirmed by fetching a detail page cold, on a client that had made no prior request.
- **WAF / TLS fingerprint gate**: none observed. Plain IIS fronting an old (2005-2017-era) ASP.NET WebForms app with Infragistics UI controls. `curl_cffi` `chrome124` got a clean `200` on the very first request, no challenge page of any kind.
- **HTTPS**: not available on this subdomain — `https://sicc.honducompras.gob.hn` times out on every profile tried; only `http://` responds. The actor uses `http://` throughout.

## The search flow — ASP.NET WebForms postback, not a JSON API

This is a classic "carry the hidden fields forward" WebForms flow, complicated by one wrinkle discovered during recon:

1. `GET busquedahistorico.aspx` returns the search-form HTML, embedding `__VIEWSTATE` / `__VIEWSTATEGENERATOR` / `__EVENTVALIDATION` plus a dozen other hidden fields belonging to Infragistics date-chooser widgets (calendar-state IDs, etc.).
2. **A hand-typed subset of these fields is not safe.** The first recon attempt built the POST body from only the three usual postback tokens plus the visible form controls (dropdowns, text inputs) — this got an immediate ASP.NET 500 runtime error. The fix: extract **every** hidden input and every select's selected option generically (`extractor.extract_form_fields`, via BeautifulSoup) and only overlay the specific fields being changed. The Infragistics calendar controls apparently need their extra hidden state echoed back unchanged, or the server-side control tree validation throws.
3. `POST` the full field set (with `ddlEntidades`/`ddlEtapas`/`ddlModalidad`/`ddlTipoAdquisicion`/`txtExpediente`/date-range fields overlaid as desired, and `...btnBuscar=Buscar` set) on the **same session** — `curl_cffi`'s cookie jar persists this automatically, and it's required: `__EVENTVALIDATION` is tied to the session that issued the `GET`.
4. Pagination is a further `POST` with `__EVENTTARGET=ctl00$cphCuerpo$gvResultados` and `__EVENTARGUMENT=Page$<n>`, again carrying forward the **entire** field set — including the just-refreshed `__VIEWSTATE` — from the immediately preceding response. Confirmed working through page 2 in recon. Because each page's postback depends on the prior response's fresh `__VIEWSTATE`, list-mode pagination is inherently **sequential** per search, not parallelizable.

An unfiltered search returned **21 pages × 30 rows ≈ 630 records** during recon — a mix of currently-open and historical tenders. There is no separate "current-only" endpoint; use the `etapa` (stage) filter to narrow to live processes.

## Detail pages are simple, stateless `GET`s

Unlike the search flow, `ProcesoHistorico.aspx?Id0=...&Id1=...&Id2=...` detail pages need **no session state at all** — confirmed by fetching one on a freshly-created client with no prior request. The three `Id0`/`Id1`/`Id2` query parameters are opaque, server-generated tokens with no discoverable pattern; there is no way to construct a detail URL by hand, it must come from a `Ver Detalle` link on a search-results row. This makes `detail` mode fully parallelizable (bounded by `maxConcurrency`), unlike `list` mode's pagination.

The detail page's data table (`id="...dvProceso"`) is a clean, generic label→value HTML table — no Infragistics complexity there, just `<tr><td>Label</td><td>Value</td></tr>` rows, parsed without hardcoding the label set (so a future added row is picked up automatically rather than silently dropped).

Below that, an Infragistics tabbed widget renders up to **four** separate data grids: "Productos y/o Servicios Solicitados" (line items — UNSPSC code, description, full free-text specification, quantity), "Documentos", "Participantes", and "Adjudicado a". These use the deeply-nested, auto-ID'd Infragistics `WebDataGrid` markup (`id="...WebTab1_tmpl<N>_wdg<Name>"`), parsed generically by widget-ID pattern rather than by hardcoded IDs (which change per page load). **A tab with no data yet renders a genuinely empty/self-closed row container** — this is correctly parsed as an empty array, not an extraction failure. Recon confirmed this is common even for tenders already in "Adjudicado" (awarded) stage — award data does not appear to populate this widget for every modality (e.g. small "Compra Menor" purchases), which appears to be a genuine gap in how ONCAE's own legacy system records awards, not a scraping bug.

## The server is slow and flaky, not blocking

Multiple recon requests timed out at 20-40 seconds with a *mostly-complete* response already received (once, 202KB of a ~211KB page) — a classic overloaded/aging legacy IIS box, not a WAF or rate limit: no `403`/`429`, no challenge marker of any kind, and a plain retry of the identical request reliably succeeds. `REQUEST_TIMEOUT` is set to 90 seconds and `MAX_RETRIES`/exponential backoff cover this in `client.py`.

## Encoding note

The response `Content-Type` correctly declares `charset=utf-8` and the bytes are valid UTF-8 (verified at the codepoint level: `ó` decodes to `U+00F3` correctly). Any mojibake seen while debugging in a terminal was purely a Windows console codepage display artifact, not a real data problem — no special encoding handling was needed in the extractor itself.
