# Crawling Method — Madagascar Government Tenders (ARMP e-GP)

**Last verified:** 2026-08-27

## Target discovery — ARMP is genuinely the official regulator

Madagascar's public procurement is regulated by the **Autorite de Regulation
des Marches Publics (ARMP)**, a public administrative institution under the
supervision of the Ministry of Economy and Finance. Independent web search
(both English and French queries, per the brief) corroborates this from
multiple angles:

- UNODC's own country profile on Madagascar's procurement framework names
  ARMP as the regulator.
- A UNDP Madagascar press release describes the handover of an "e-GP" online
  platform to ARMP, built with UNDP support, covering `e-planning` (annual
  procurement plans), `e-file` (tender-document creation), `e-payment`, and
  `e-submission`.
- The live site itself (`www.armp.mg`) titles its homepage *"Le portail des
  marches publics malagasy"* and its footer credits *"Equipe de la DSI
  ARMP"* (ARMP's own in-house IT/DSI team) — this is the regulator's own
  first-party site, not a vendor-hosted platform or a third-party aggregator.

Several **third-party aggregator sites** turned up in search results
(`madagascartenders.com`, `globaltenders.com`, `wuripay.com`, a French one
called `appel-offres-madagascar.mg`, and others) — none of these were used
as a source; they're commercial tender-alert services layered on top of (or
independently compiling) the same public notices ARMP itself already
publishes for free. One secondary-source summary (a US trade.gov guide)
claimed the official portal requires "a subscription fee" for access — this
claim does **not** hold up against the live site: every listing endpoint
described below was independently confirmed reachable with a plain
unauthenticated request, no account, and no payment of any kind.

## robots.txt / WAF

`GET http://www.armp.mg/robots.txt` and `GET http://marches.armp.mg/robots.txt`
both return a plain **404 Not Found** — no file exists, so there is no
`Disallow` rule of any kind and no `User-agent`/`Claude`/`anthropic-ai`
mention to find on either hostname.

No WAF/CDN fingerprint was observed anywhere: `Server: nginx/1.18.0 (Ubuntu)`
or `nginx/1.14.1`, `X-Powered-By: PHP/7.4.33`, no `cf-ray`, no bot-challenge
HTML, no `_abck`/`bm_sz`/`__cf_bm` cookies. A plain unauthenticated request
with no TLS impersonation cleared every endpoint tested on the first try.
`curl_cffi` `chrome124` is used anyway for portfolio consistency and
residential-proxy compatibility, not because it's load-bearing here.

**HTTPS quirk:** both `www.armp.mg` and `marches.armp.mg` serve a TLS
certificate that does not match the requested hostname (a plain client gets
`SEC_E_WRONG_PRINCIPAL` / hostname-mismatch on the TLS handshake). Plain
HTTP on port 80 serves byte-identical content from the same nginx instance,
so this actor uses `http://` throughout instead of disabling certificate
verification.

## No login required to view any listing

This was the key stop/go condition, checked directly against three real
endpoints rather than assumed:

- `GET /marches_publics/index.php` (today's live "avis d'appel d'offres",
  grouped by all 22 regions) → `200`, real current-dated data, zero
  cookies/auth needed.
- `POST /marches_publics/dossier_sub_list_modal.php` (the multi-year
  dossier-archive search — the same request the page's own "Rechercher"
  button issues) → `200`, real data back to 2015, zero auth needed.
- `POST /marches_publics/contrat_action.php` (awarded-contracts search) →
  `200`, real JSON data including supplier/amount/beneficial-owner fields,
  zero auth needed.

A **login wall does exist**, but only for something this actor deliberately
does not touch: the dossier-archive page's "Search and Export to Excel"
button, which is wired to a `connexion.php` login redirect in the page's
own JavaScript. That button is not even reachable from the rendered
page — it's inside an HTML comment (`<!--...-->`) in the page source, so a
real user browsing the site never sees it either. The button that actually
renders and works ("Rechercher") requires no account at all. A separate
"beneficial owner lookup" page linked from the homepage
(`beneficiaire effectif.php`) *does* require an active session
("No user information found." with no query params) — this actor does not
use that page; the same beneficial-owner data is already exposed per-record
on the public `contrats` JSON endpoint (`BENEFICIAIRE_EFFECTIF` field), so
nothing is lost by skipping it.

## Data sources — three genuinely different shapes

No OCDS (Open Contracting Data Standard) endpoint or RSS feed was found —
recon went straight to the site's own three views, described below in the
priority order they were found (server-rendered HTML by region → an
HTML search-result table with an embedded detail modal per row → a real
JSON endpoint).

### `avis` — live calls for tender (`GET /marches_publics/index.php`)

A single large page listing every currently-open call for tender, split
into one `<table>` per one of Madagascar's 22 administrative regions (a
`REGION : <name> (<N> avis)` banner precedes each table). At recon time
this held **423 rows** across 21 regions actually carrying data. Each row
has: procuring entity, the entity's own reference number, a short
procurement-mode code (e.g. `ACO`, `CPX`), ARMP's internal dossier number,
the tender's title/object, an open date and a submission deadline, and a
link to the official notice PDF (hosted on a separate raw-IP-addressed
document server, `154.126.93.219`, passed through as-is — not fetched or
parsed by this actor). No pagination exists or is needed: it's one request,
one response, every live tender.

### `dossiers` — the multi-year archive (`POST /marches_publics/dossier_sub_list_modal.php`)

The same request the page's own "Rechercher" (Search) button issues, with
a year (`annee_dos`, 2015-present) as the only filter this actor exposes
(category/entity/procurement-type/procurement-mode filters exist upstream
in the same form but are left wildcarded to keep the actor's input simple —
a plain year query already returns every category/type/mode for that
year). At recon time, the current year (2026, 8 months in) held **565**
dossiers; the prior full year (2025) held **8,084**.

Each row's summary table gives institution, procurement-mode label, nature
of contract, reference, dossier number, and object. Each row also has its
own **Bootstrap detail modal embedded in the same response** (triggered by
a "Details" button in the real UI) carrying three extra fields not in the
summary table: the dossier's own registration date, its financing source,
and the name of the PRMP (Personne Responsable des Marches Publics —
procurement officer) handling it. Since this modal data is already present
in the page this actor already downloaded, it's merged in for free rather
than issued as a second request — but on a best-effort basis: if the modal
markup doesn't match for a given row, that row still ships with its
already-complete summary fields rather than failing the whole run.

**Quirk — no server-side pagination, and a noisy response body.** A single
query for one year returns the *entire* matching result set in one HTML
response; there is no page-by-page fetch to throttle. Because each row
duplicates a fair amount of markup in its modal (including several
commented-out PHP-debug-notice blocks from an unrelated code path on the
same page — cosmetic upstream noise, harmless and ignored), an unfiltered
full year can be very large: 2025 alone was **~97 MB** and took over a
minute to download in recon. This actor always fetches the full page for
whichever year is requested (there's no way to ask the server for less),
then trims to `maxResults` only for what gets kept in the output — pick a
specific, ideally recent, year rather than iterating many years in one run
if the archive matters for your use case. The table-parsing step itself
avoids the worst of this by cutting the HTML at the first embedded modal
(`html.split('<div class="modal fade"', 1)[0]`) before handing it to the
HTML parser, since the summary table always appears first in the document
— this keeps the primary parse fast even on a huge page; only the
best-effort modal-merge step (a single regex pass, not a full HTML parse)
touches the rest of the document.

### `contrats` — awarded contracts (`POST /marches_publics/contrat_action.php`)

A genuine JSON endpoint (`Content-Type: application/json`) behind the
"Contrats" page's own search form, filtered by year (`ANNEE`, 2015-present
or `%` for all years — this actor always passes a single year). At recon
time, 2026 alone held **3,430** awarded contracts. Each record already
comes back as a clean flat JSON object and is passed through with
upstream's own field names, including several fields rarely seen on a
public tender feed: the winning supplier's Malagasy tax ID (`TITULAIRE_NIF`),
its **declared beneficial owner(s)** (`BENEFICIAIRE_EFFECTIF`, a genuine
transparency field, semicolon-separated when there's more than one), the
contract amount and currency (`MTT_TTC` / `UNITE_MONNAIE`, almost always
`MGA`), and the overseeing PRMP officer's name.

Response bytes are correctly UTF-8 (verified at the byte level: `é` is the
standard 2-byte UTF-8 sequence `0xC3 0xA9`) — any mojibake seen during
manual recon in a Windows terminal was a local display/encoding artifact of
the recon tooling itself, not a real data-quality issue; `curl_cffi`'s own
response decoding handles it correctly.

## TLS profile

`chrome124`, consistent with the portfolio-wide default. No profile-specific
blocking was ever observed on this target.
