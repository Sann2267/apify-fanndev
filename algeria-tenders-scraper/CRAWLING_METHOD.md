# Crawling Method — Algeria Government Tenders (MDN)

**Last verified:** 2026-08-27

## Target discovery — BOMOP is genuinely down, not evasion-worthy

The task brief pointed at BOMOP (Bulletin Officiel des Marchés de l'Opérateur
Public), Algeria's central procurement bulletin published by ANEP (Agence
Nationale d'Édition et de Publicité). Independent web search (English and
French) confirmed BOMOP as the real central bulletin and turned up a modern,
Google-indexed WordPress portal at `bomop.anep.dz` with real per-sector
listing pages (`/secteur/industrie/page/173/` and similar — Google's own
cached snippets show real tender titles, reference numbers, and full body
text with no login wall visible in the indexed content).

**That domain is currently unreachable.** Three independent network paths
were tried against it:

1. This sandbox's own `curl_cffi` (all of `chrome124`, `chrome131`,
   `safari17_0`, `edge101`) — every attempt fails with
   `SSL_connect: Connection closed abruptly` (BoringSSL) or, at the raw
   `openssl s_client`/Python `ssl` level, an `unexpected eof while reading`
   with **zero bytes of ServerHello ever received**, regardless of TLS
   version (1.0/1.1/1.2/1.3) or whether SNI was sent at all. Plain HTTP on
   port 80 times out completely (no RST, no response).
2. The Claude Code `WebFetch` tool (a different network/datacenter) —
   `net::ERR_CONNECTION_CLOSED` / "Socket is closed" on the same host.
3. Jina AI's reader proxy (`r.jina.ai`, a third, unrelated network, using a
   real headless browser) — `net::ERR_CONNECTION_CLOSED` navigating to the
   same URL.

Three unrelated networks failing identically at the TLS-handshake layer
(not a 403, not a CAPTCHA page, not a WAF challenge body) is a strong,
independently-corroborated signal of a genuine server-side outage, not an
IP-specific block — consistent with the portfolio's recurring "new e-GP
system down, check for a legacy/corporate fallback" pattern (Sierra Leone
and Tanzania, tender vertical Babak 25-26).

The three next-best ANEP/BOMOP-adjacent candidates were each checked and
each fails independently:

- **`bomopclassic.anep.dz`** (the old legacy PHP portal, adjacent IP,
  genuinely reachable) — its own homepage states plainly: *"Les
  utilisateurs ayant souscris un abonnement Internet auprès du Service
  BOMOP peuvent s'authentifier et télécharger la dernière édition du BOMOP
  au format PDF et HTML"* — i.e. viewing the actual bulletin content
  requires a **paid subscription + login**. Every plausible listing/detail
  endpoint probed (`liste.php`, `recherche.php`, `annonce_details.php`,
  etc.) is either a 404 or a 500 — there is no free-viewing path here. Stop
  condition: login wall required to view listings.
- **`marches-publics.gov.dz`** (Algeria's national e-procurement portal,
  officially launched December 2021) — dead: direct requests time out /
  connection-refused on both ports 80 and 443, and the Wayback Machine's
  CDX index shows **no crawl since April 2023**. A cached 2023 snapshot
  shows this portal *did* publish full tender text publicly on its
  homepage (no login needed to read), but every "Détails" button already
  routed to `signin.xhtml` even then, and the live site is gone now
  regardless.
- **BAOSEM** (`baosem.com` — Bulletin des Appels d'Offres du Secteur de
  l'Énergie et des Mines, an ANEP-adjacent bulletin for the energy/mining
  sector, jointly owned by Sonatrach/Sonelgaz) — the site itself is live,
  but its `/site/tenders/` page is a login/subscription **request** page
  (a "TENDERS ACCESS" login widget plus a "SUBSCRIPTION SERVICE" contact
  block), not an actual tender listing. Stop condition: login/paid
  subscription wall.

## Pivot — decentralized ministry sites (same pattern as Botswana/Namibia)

Per the portfolio's established fallback pattern, individual Algerian
ministries are legally required to publish their own tender notices (in
BOMOP/national press **and** on their own site) even when the central
aggregator is unreachable. A French-language search across `.gov.dz`
ministry domains turned up several live, independent candidates:

| Candidate | Verdict |
|---|---|
| Ministry of Commerce (`commerce.gov.dz/fr/avis/collection/avis-dappel-doffre`) | Live, public, clean Drupal pagination — but **stale**: newest item at recon time was dated 22.05.2024, over two years old. Feed appears abandoned. |
| Ministry of Environment (`me.gov.dz/fr/appels-doffres/`) | Live and fresh (page cache timestamp same-day as recon), but notices are **scanned images/JPEGs** of the printed notice, not machine-readable text — much lower data quality. |
| Ministry of Justice (`mjustice.dz`) | `robots.txt` request returns a WAF "Web Page Blocked" page (HTTP 500) — deprioritized. |
| SAFQATIC (`safqatic.dz`, postal/telecom sector portal) | Live, no `robots.txt` restriction, real PDF-linked notices — a viable secondary candidate, not used here to keep scope to one well-verified source. |
| **Ministry of National Defense (`mdn.dz`)** | **Selected.** See below. |

## Why MDN

`www.mdn.dz` (Ministère de la Défense Nationale) publishes its own tender
notices at `/site_principal/sommaire/appels/appels_fr.php` (current) and
`/site_principal/sommaire/appels/archives_appels_fr.php` (older overflow).
At recon time the current page's newest entry was dated **24 August
2026 — three days before this recon**, confirming an actively maintained
feed, not an abandoned one. Despite the ministry name, the notices
themselves are ordinary public-sector procurement: barracks/garrison
public-works repairs, hospital medical-equipment purchases, catering and
general-supplies contracts for military regions and affiliated public
hospitals — not classified defense material.

## robots.txt / WAF

```
User-agent: *
Disallow: /logs/
Disallow: /site_principal/css/
Disallow: /site_principal/js/
... (site_em_anp, site_cfa, site_cfdat, site_cfn, site_cft, site_cgn, site_cgr -- all css/js only)
```

A single `User-agent: *` group. No blanket `Disallow: /`, no mention of
`Claude`/`ClaudeBot`/`anthropic-ai` anywhere, and `/site_principal/sommaire/
appels/*.php` is not covered by any Disallow rule.

No WAF/CDN challenge was observed on any request: a plain `curl_cffi`
`chrome124` GET with no cookies returns `200` with real content on the
first try, every time.

**TLS quirk:** `mdn.dz` serves a certificate chain missing its intermediate
CA — the identical class of bug already documented for Nepal/Eswatini in
this portfolio (`unable to get local issuer certificate`). `verify=False`
is required; this does not affect TLS fingerprinting/impersonation, only
certificate-chain validation.

## No login required to view any listing

Both `appels_fr.php` and `archives_appels_fr.php` were fetched with a plain
unauthenticated GET, no cookies, no session — `200` with full real content
every time. No login link, button, or gated section exists anywhere on
either page.

## Data source — single page, two windows, no API/RSS

No OCDS endpoint, JSON API, or RSS feed was found — MDN's own PHP page is
the only public view of these notices. The page is hand-rolled HTML (no
CMS/JS framework): a flat sequence of

```html
<button class="accordion">24 Août 2026 </button>
<div class="panel">
<p><a href="AppelsFr_24082026/Plac_Fr_1.pdf" target="_blank">
Avis d'Appel d'offre national ouvert ... N° 158/2026/D4/T/5°RM portant sur ...
</a></p>
...
</div>
```

one `<button>`/`<div class="panel">` pair per calendar day, one `<p><a>`
per notice published that day (each linking straight to the official PDF).
At recon time:

- `appels_fr.php` ("latest") — **202 days**, **2,202 notices**, spanning
  roughly 02 November 2025 to 24 August 2026 (a ~10-month rolling window).
- `archives_appels_fr.php` ("archived") — **42 days**, **407 notices**,
  spanning 01 December 2025 to 29 January 2026 — the older overflow window
  the site keeps once items roll off the current page. No year parameter
  or deeper multi-year archive exists; this appears to be the full extent
  of what MDN keeps published.

Both pages were fetched in full and every day-block/notice parsed with
zero failures (`0` empty panels, `0` non-PDF links). Response bytes decode
as strictly valid UTF-8 (verified byte-for-byte: `é`/`û`/`è` are correct
2-byte UTF-8 sequences) — any mojibake seen in this session's own terminal
output during manual recon was a local Windows-console display artifact,
not a real data issue.

Four notice types are mixed together on the same pages and classified with
a best-effort keyword rule (never fatal — the full raw text is always kept
verbatim regardless of classification success): straightforward tenders
("Avis d'Appel d'offre"), deadline extensions ("Avis de prorogation"),
award/provisional-award notices, cancellations, corrigenda, and — notably —
**"Mise en demeure"** (formal default notices naming a specific contractor
in breach of an existing contract, including the company name and original
contract number) — a transparency-relevant record type also seen at other
tender-vertical actors in this portfolio.

An Arabic-language mirror of both pages exists (`appels_ar.php` /
`archives_appels_ar.php`, confirmed reachable) but was not scraped —
it publishes the same underlying notices in Arabic rather than additional
ones, so it would be a redundant duplicate rather than added coverage.

## TLS profile

`chrome124`, consistent with the portfolio-wide default. No profile-specific
blocking was ever observed on this target.
