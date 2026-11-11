# Crawling Method — Cameroon Government Tenders (ARMP)

**Last verified:** 2026-08-27

## Target discovery — armp.cm is genuinely the official platform, a WordPress lookalike was ruled out

The brief pointed at ARMP (Agence de Regulation des Marches Publics), Cameroon's
public procurement regulator, as the likely target. Two candidate domains
surfaced during search:

- **`armp.cm`** (and `www.armp.cm`) -- carries `<title>AGENCE DE RÉGULATION
  DES MARCHÉS PUBLICS</title>`, "République du Cameroun" / "Republic of
  Cameroon" branding, a real armoiries (coat of arms) image, live news items
  signed by "Le Directeur Général de l'ARMP, Monsieur Joseph NGO" dated
  August 2026, and a "PLATEFORME" menu linking out to `marchespublics.cm`
  (labelled "COLEPS", a separate Java/`.do`-action e-procurement backend) and
  `categorisation.armp.cm`. This is the real site.
- **`cameroonppa.com`** -- a WordPress site (`wp-json` REST route present)
  calling itself "Cameroon Public Procurement Authority" and citing **"Law
  N°25/2003 of 30/11/2003 governing public procurement"** -- but Cameroon's
  actual procurement regulator was created by decree in 2001/2004, and
  "Public Procurement Act, 2003 (Act 663)" is *Ghana's* statute, not
  Cameroon's. This reads as a templated/copy-pasted tender-alert site, not
  the genuine regulator, and was **not used**.

No decoy DNS (a `.gov.bb`/`.gov.fj`-style hallucinated hostname) was found for
this target -- `armp.cm` resolves and is the real, actively-updated site.

## robots.txt / WAF

Both `https://armp.cm/robots.txt` and `https://www.armp.cm/robots.txt` return
a real `200` with:

```
User-agent: *
Disallow:
```

A single group, blanket allow, no `Claude`/`ClaudeBot`/`anthropic-ai`
line anywhere, no plain-English AI/bot prohibition comment.

No WAF/CDN fingerprint was found: responses carry plain `Server: Apache`,
`X-Powered-By: PHP/7.4.33` / `PleskLin`, standard Laravel session cookies
(`XSRF-TOKEN`, `armp_session`) -- no `cf-ray`, no bot-challenge HTML, no
`_abck`/`bm_sz`/`__cf_bm`. `curl_cffi` `safari17_0`, `edge101`, and `chrome124`
(on retry) and `chrome131` all returned identical `200`s. One `chrome124`
attempt timed out and succeeded immediately on retry with the exact same
profile -- ordinary transient flakiness, not a TLS-fingerprint block; the
client's existing retry loop (3 attempts, exponential backoff) is sufficient,
no profile ladder was needed.

## No login required to view listings or publication detail

Checked directly against real IDs pulled from the site's own public
listings:

- `GET /` (homepage, mixed feed of every publication type) -> `200`, live
  data, zero auth.
- `GET /filtres?type=avis&val=<n>` (one of 7 procurement categories) -> same.
- `GET /details?type_publication=<T>&id_publication=<id>` (full publication
  text) -> same, for every type code observed (`AO`, `DC`, `AMI`, `DEC-ATTR`,
  `COMM`, `ADDITIF`).

A login system does exist (`/lang?val=fr|en` sets a session but no auth
gate), but nothing behind it was ever needed to browse or read a publication
-- this is consistent with the vertical's Babak 25/26 hypothesis that tender
transparency-law data tends to be genuinely public, unlike business
registries. An invalid `id_publication` (tried `1`, `999999999`) returns a
generic Laravel HTTP `500` "Server Error" page, instantly and reproducibly --
handled as a per-record `not_found_or_restricted` error (no retries wasted on
it, since it's deterministic, not transient), not a general block.

## Data source — server-rendered PHP/Laravel HTML, no JSON API found

No `fetch(`/`axios`/`/api/` calls were found in the homepage's own JS. This is
a classic server-rendered Laravel app (Bootstrap 4 + DataTables/jQuery for
cosmetics only) -- HTML scraping is the correct and only strategy here, no
API to reverse-engineer.

### Listing views (`mode: "list"`)

| `listType` | URL | `val` | Total rows (2026-08-27) |
|---|---|---|---|
| `latest` | `/` | (mixed) | 3,820+ (382 pages seen) |
| `national` | `/filtres?type=avis&val=1` | 1 | 7,038 |
| `quotation` | `/filtres?type=avis&val=5` | 5 | 1,143 |
| `expression_of_interest` | `/filtres?type=avis&val=12` | 12 | 557 |
| `international` | `/filtres?type=avis&val=4` | 4 | 172 |
| `proposal` | `/filtres?type=avis&val=7` | 7 | 20 |
| `restricted` | `/filtres?type=avis&val=21` | 21 | 5 |
| `agreement` | `/filtres?type=avis&val=6` | 6 | 3 |

Pagination is a plain `&page=N` query param (`page=1` explicit vs. omitted
confirmed byte-identical), 10 rows/page, server-fixed. Each row is one
`<li class="list-group-item">` inside `<ul id="tout_les_avis">`, regardless
of which document type (`AO`/`DC`/`AMI` original notices vs.
`DEC-ATTR`/`COMM`/`ADDITIF` award decisions/communiques/addenda) it actually
is -- `val` filters by **procurement category** (national/international/...),
not by document type, so a category listing naturally mixes original notices
together with their own later award decisions and addenda.

**Labels are rendered in whichever UI language the session defaults to**
(French "MO/AC"/"Publié le"/"Région" or English "PO/CA"/"Published on the
the"/"Region" were both observed live from plain unauthenticated requests,
seemingly session-dependent rather than URL-controlled) -- so the parser
extracts fields **positionally** (1st `.d-table-row` in the left info column
is always the procuring entity, 2nd is always the category type, 3rd region,
4th amount; same pattern for the right column's published/closing
date/closing time), not by matching label text, and raises `UnexpectedShape`
if the expected row count isn't found.

`closingDate`/`closingTime` are wrapped in a `class="d-none"` div (instead of
`class="d-table-cell"`) when armp.cm itself considers the field not
applicable for that record (typically award decisions/communiques, which
have no bid deadline) -- the parser reports `null` in that case rather than
passing through the placeholder sentinel value (`01-01-1970`) armp.cm hides
behind it.

**`_totalAvailable` is read live from the page's own sidebar "Publications"
badge** (present on every page, not just the homepage) rather than computed
from pagination -- exact and matched by category `val`, not fabricated.
`listType=latest` has no single matching badge (it mixes all categories), so
`_totalAvailable` is `null` there and `_lastPageSeen` (the highest page
number visible in the current response's own pagination nav -- a floor, not
a firm total, since Laravel's paginator only renders a window around the
current page) is reported instead.

### Detail view (`mode: "detail"`) — two genuine content shapes

`GET /details?type_publication=<T>&id_publication=<id>` always exposes
`div.ac_mo` (procuring entity) and `div.entete_avis` (title + optional
funding source), plus the original-notice/DAO PDF download links. Beyond
that, the body has two different real shapes depending on `type_publication`:

1. **Structured** (`AO`, `DC`, `AMI`, ...) -- numbered sections rendered by
   armp.cm's own template: `"1.Objet"`, `"2.Consistance des prestations"`,
   ... up to 17+ for a complex national tender. Parsed generically: each
   numbered `<strong>` label is slugified into a camelCase key (after
   stripping a `<span class="badge">New(Additif)</span>` marker that's
   present in the raw HTML even when CSS-hidden) and paired with its
   paragraph text, both as a `sections` dict and an ordered `sectionList` --
   new/renamed sections flow through automatically (raw-passthrough)
   instead of needing a hardcoded schema.
2. **Free-form** (`DEC-ATTR`, `COMM`, `ADDITIF`, ...) -- award
   decisions/communiques/addenda are literally pasted from Word
   (`MsoNormal`/table markup, `mso-*` inline styles), with no numbered
   sections at all. Parsed as a single `bodyText` field (whitespace
   collapsed per line, blank lines dropped, line breaks preserved) rather
   than forced into the structured shape.

**A parsing pitfall found and fixed during build**: `div.ac_mo` itself
carries a stray `my-4` class (`class="ac_mo text-center font-weigth-bold
my-4"`) -- a naive `soup.select_one("div.my-4")` for "the content wrapper"
silently grabs the procuring-entity header instead of the real body. Fixed
by anchoring on `div.clearfix` (the download-links row, which reliably
precedes the real content) and taking its next sibling `div.my-4`.

## TLS profile

`chrome124`, consistent with the portfolio-wide default. No profile-specific
blocking was observed (see WAF section above) -- retries alone handle the
occasional transient timeout.
