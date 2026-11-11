# Crawling Method — DR Congo Public Procurement (SIGMAP / ARMP)

**Last verified:** 2026-08-27

## Target discovery — three domains, two of them genuine, one a decoy/duplicate

The DRC's Autorité de Régulation des Marchés Publics (ARMP) was created by
Law N°10/010 of 27 April 2010. Independent web search (English and French)
surfaced three candidate domains:

- **`armp-rdc.cd`** — a WordPress site, real ARMP branding, live news
  ("Le Directeur Général de l'ARMP échange avec..." dated August 2026),
  footer credits a `wp-json` oEmbed route. This is ARMP's own
  marketing/policy site (news, laws, reports) — no tender-listing data lives
  here, only links out to the actual e-procurement platform.
- **`marchepublic.cd`** — titled "Système Intégré de Gestion des Marchés
  Publics" (SIGMAP), footer explicitly identifies itself as run by ARMP
  ("AUTORITE DE REGULATION DES MARCHES PUBLICS (ARMP)", same Kinshasa-Gombe
  address, same `armpdg@armp-rdc.org` contact email as `armp-rdc.cd`) and
  links back to `armp-rdc.cd` as "ARMP" in its own footer. **This is the
  real e-procurement/tender-listing platform and this actor's target.**
- **`www.armp-rdc.org`** (note `.org`, not `.cd`) — a separate, seemingly
  unrelated deployment (its `robots.txt` is served by Cloudflare with a
  Google/OpenAI/Anthropic-style "Content-Signal" AI-crawling policy, a
  completely different stack from the WordPress `.cd` site) that explicitly
  **blocks `ClaudeBot`** (see below). It was not used for anything — the
  genuine `.cd` platform (confirmed live, current, and cross-linked from
  `marchepublic.cd`'s own footer) was sufficient and does not carry this
  restriction.

## robots.txt / WAF

```
GET https://marchepublic.cd/robots.txt  -> HTTP 404 (no file exists)
GET https://armp-rdc.cd/robots.txt      -> HTTP 200, plain Yoast SEO default:
                                            User-agent: *
                                            Disallow:
                                            (blanket allow, no Claude/anthropic-ai mention)
```

`www.armp-rdc.org/robots.txt` (the domain **not** used by this actor) does
carry an explicit block:
```
User-agent: ClaudeBot
Disallow: /
```
among several other AI crawlers (GPTBot, CCBot, Bytespider, Google-Extended,
etc.) — this is exactly the kind of stop condition this project watches for,
but it applies to a different, unused domain. `marchepublic.cd` (the actual
target) has no `robots.txt` at all, and `armp-rdc.cd` (linked from it, not
itself scraped for data) has a blanket allow. Neither of the two domains
this actor actually touches names Claude/anthropic-ai anywhere.

No WAF/CDN fingerprint was found on `marchepublic.cd` itself: plain
`curl_cffi` (`chrome124`) requests returned `200` on the first try, no
`cf-ray`, no bot-challenge HTML, no `_abck`/`bm_sz`/`__cf_bm` cookies.

## No login required to view listings

Every listing view this actor uses was confirmed reachable with a fresh,
unauthenticated session:
- The public "Publications" mega-menu (procurement plans, calls for
  tenders, expressions of interest, non-objection notices, approvals,
  levy certificates, and every lifecycle-stage sub-item under each) is
  visible and clickable with no session cookie beyond the anonymous
  `JSESSIONID` the server itself sets on first contact.
- `CONNEXION`/`INSCRIPTION` (login/sign-up) links exist in the same menu,
  but nothing this actor touches (browsing any publication-type listing)
  ever redirected to them or returned truncated data.

## Data source — a Java (JSF/PrimeFaces) app, not a REST API

`marchepublic.cd` is a **JavaServer Faces (JSF) app built with PrimeFaces**
(`?ln=primefaces&v=11.0.0-RC2`), a fifth distinct e-procurement vendor
lineage for this tender/procurement vertical (alongside European
Dynamics/ePPS, Perago Systems, Nextenders, and the Korean-origin
JSP/UMUCYO-style vendor already seen elsewhere in this portfolio). No JSON
REST API, no OCDS endpoint, and no RSS feed were found. Unlike a classic
server-rendered PHP/JSP site, **plain GET requests to a listing URL don't
work** — the mega-menu items are `<a href="#" onclick="PrimeFaces.ab(...)">`
JavaScript AJAX postbacks, not real links.

### The actual protocol (fully HTTP-only, no browser needed)

Reverse-engineered directly from the page's own `PrimeFaces.ab({...})`
config objects and confirmed end-to-end with `curl_cffi`:

1. `GET /portail/index.xhtml` — primes a `JSESSIONID` cookie and returns a
   fresh `javax.faces.ViewState` token (JSF's server-side view state,
   embedded as a hidden form field).
2. `POST /portail/index.xhtml` — a PrimeFaces AJAX postback simulating a
   click on one mega-menu leaf item (`javax.faces.source:
   "landing-menu:j_idtNN"`, `javax.faces.partial.ajax: true`, plus the
   `ViewState` from step 1). The server does **not** render the new content
   inline — it replies with a bare partial-response instructing a client
   redirect: `<partial-response><redirect url="/portail/publication.xhtml">`.
   Server-side, this stores *which publication type was clicked* in a
   session-scoped backing bean.
3. `GET /portail/publication.xhtml` — same session/cookies — renders a
   PrimeFaces `DataView` grid of whatever type step 2 selected.

**Gotcha found during recon: the ViewState is effectively single-use.**
Reusing the same `ViewState` value for a second AJAX postback in the same
session (e.g. to try a different category without re-priming) silently
produced the platform's own generic "no criteria" validation response
instead of real content, rather than an HTTP error — this actor re-primes a
fresh ViewState (step 1) before every single category click rather than
attempting to cache/reuse one.

**A separate, real keyword-search widget also exists** (`searchForm` on the
homepage, submitting to the same page via its own AJAX button) but its
`category`/`autoriteContractante` dropdown filters were found to have **no
effect** on results during recon (every category value tested returned the
identical result set) — PrimeFaces `SelectOneMenu` components normally
require their own `valueChange` AJAX round-trip to actually update the
backing bean, which a same-request form submit does not trigger. This
actor does not use the search widget at all; it navigates via the
mega-menu's own per-type click, which is what actually filters correctly.

### Confirming completeness independently

Before settling on the mega-menu approach, the search widget's free-text
`searchCriteria` field was used to brute-force enumerate every publication
on the platform (looping every letter `a`-`z` as a substring query and
de-duplicating results by row content) as a cross-check. This surfaced
exactly the same **4 total publications**, system-wide, across every
category, that the mega-menu approach finds — independent confirmation
that the per-category crawl in this actor is not missing anything, and that
the platform's current catalogue really is this small (see "Known limits"
below).

## Listing page shape

Each publication renders as one `div.product-grid-item` card inside
`div.ui-dataview-content`, with: a short category code (`MF`/`MT`, i.e.
Marché de Fournitures/goods vs. Marché de Travaux/works) and its label, the
contracting authority, the publication's own reference number (in italics),
a short description, a "Date de publication" label, a "Télécharger"
(download) button linking straight to the official PDF
(`/portail/rest/files/publication/<file>.pdf`, no auth needed — confirmed
with a fresh, cookie-less request), and a "Détails" button.

**Every "Détails" button observed at recon time was `disabled`** (`type=
"button" ... disabled="disabled"`, unlike the working "Télécharger" button
next to it) — none of the 4 live publications currently expose a richer
detail view beyond what's already on the card plus its PDF. This actor
therefore does not implement a separate detail-page parser: there is no
live record to reverse-engineer that flow against, and building one
unverified against real data would violate this project's "test against
real data, don't fail silently" principle. If ARMP/SIGMAP later publishes a
record with an active "Détails" button, that flow (almost certainly another
PrimeFaces AJAX postback, following the same pattern as the mega-menu
click) would need fresh recon before being added.

An empty category renders the literal text "Aucun enregistrement trouvé"
inside the same `div.ui-dataview-content` container instead of any cards —
treated as a valid empty result, not an error.

## Known limits

- **The entire platform held only 4 publications at recon time** (2 in
  "Plans de passation des marchés" / procurement plans, 2 in "Avis de Non
  Objection (ANO)"), all from a single contracting authority (MINISTERE DU
  BUDGET), all dated the same day (24/07/2026), across all 22 publication
  types this actor covers. This looks like a platform that is live and
  genuinely public, but not yet widely adopted across DRC's government
  agencies — plausible given the country's broader infrastructure and
  institutional-capacity challenges. Re-run this actor periodically; the
  crawl logic itself does not depend on data volume.
- **Pagination beyond page 1 was not exercised.** The PrimeFaces `DataView`
  widget is configured for 10 rows/page; every category seen during recon
  had at most 2 records, so a same-category "next page" AJAX interaction
  was never observed live and is not implemented. If any single publication
  type ever exceeds 10 records, only the first 10 would currently be
  returned for that type — revisit this if/when the platform's volume
  grows.
- **No detail-page mode** (see above) — only what each listing card itself
  exposes (including its direct PDF link) is captured.
- The mega-menu's `landing-menu:j_idtNN` component ids are assigned by JSF
  from the page's own compiled component tree order. They were stable
  across every recon session but are not guaranteed stable across a future
  ARMP redeploy that restructures the menu — if every category starts
  returning `blocked_or_transient`/`FetchFailed` errors at once, re-fetch
  `index.xhtml` and re-map the ids from the mega-menu's own `onclick`
  attributes (see `src/constants.py` for the full current mapping).

## TLS profile

`chrome124`, consistent with the portfolio-wide default. No profile-specific
blocking was observed on `marchepublic.cd` — plain `curl_cffi` cleared every
endpoint on the first try.
