# Crawling Method — Nigeria Government Tenders (NOCOPO/BPP)

**Last verified:** 2026-08-27

## Target discovery — NOCOPO, run by the Bureau of Public Procurement

Nigeria's Bureau of Public Procurement (BPP, the statutory regulator under
the Public Procurement Act, 2007) operates the **Nigeria Open Contracting
Portal (NOCOPO)** at `https://nocopo.bpp.gov.ng`. It was co-created with
civil society in 2017 as Commitment 2 of Nigeria's Open Government
Partnership National Action Plan and is explicitly modelled on the Open
Contracting Data Standard (OCDS). Confirmed independently, not from a
tender-alert blog:

- BPP's own official site (`bpp.gov.ng`) links to it from its "Procurement
  Management System" page.
- The Open Contracting Partnership's own Data Registry lists BPP as a
  publisher (`data.open-contracting.org/en/publication/64`), naming
  `nocopo.bpp.gov.ng` as the source and confirming OCID prefix
  `ocds-gyl66f` and OCDS-conformant JSON/Excel/CSV downloads.
- The portal's own `Open-Data` page footer reads "Copyright 2026 by
  NOCOPO", and every OCDS package this actor downloads carries
  `"publisher": {"name": "The Bureau of Public Procurement", "scheme":
  "NG-BPP", "uid": "BPP-01"}`.

`nocopo.bpp.gov.ng` runs on **DotNetNuke (DNN)**, a .NET CMS — evident from
the `/App_Browsers/`, `/App_GlobalResources/`, `/Providers/` paths in
robots.txt and the `dnn_IsMobile`/`.ASPXANONYMOUS` cookies on every request.
The page footer credits a named Nigerian developer/agency
(`Bola Saheed, bola.saheed[at]adroitsoft.ng`) rather than one of this
project's previously-confirmed shared e-GP vendors (European Dynamics,
Perago Systems, Bonfire, TenderLink) — this looks like a bespoke/local build
specific to BPP, not (yet) a lineage seen elsewhere in this portfolio.

`bpp.gov.ng` itself (the ministry's own corporate site, separate host) is
not used by this actor — all tender/award/contract data lives on the
`nocopo.bpp.gov.ng` subdomain.

## robots.txt

`nocopo.bpp.gov.ng/robots.txt`:

```
User-agent: *
Disallow: /*/ctl/       # Googlebot permits *
Disallow: /admin/
Disallow: /App_Browsers/
Disallow: /App_Code/
Disallow: /App_Data/
Disallow: /App_GlobalResources/
Disallow: /bin/
Disallow: /Components/
Disallow: /Config/
Disallow: /contest/
Disallow: /controls/
Disallow: /Documentation/
Disallow: /HttpModules/
Disallow: /Install/
Disallow: /Providers/
Disallow: /Activity-Feed/userId/    # Do not index user profiles
```

A single flat `User-agent: *` group — no other `User-agent:` line exists
anywhere in the file — no blanket `Disallow: /`, and no
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai
mention anywhere. Every path this actor touches (`/Open-Data`,
`/PublishedRecordHandler.ashx`, `/ocdsjson.ashx`, `/downloads.aspx`) is a
public application route, none of them under any of the disallowed
CMS-internals prefixes above.

## No login required to browse or download

The `/Open-Data` page itself, its listing endpoint
(`PublishedRecordHandler.ashx`), and its per-record OCDS download endpoint
(`ocdsjson.ashx`) were all confirmed reachable with a fresh, cookie-less
client — no session, no API key, no CSRF token beyond the anonymous
`.ASPXANONYMOUS` cookie DNN issues to every visitor automatically. NOCOPO
does have MDA-side data-entry logins (for the ~700+ agencies that submit
their own procurement records), but nothing gates *viewing or downloading*
published data.

## No WAF / TLS-fingerprint gate observed

Every endpoint below returned clean `200`s to a plain `curl` request with a
generic Chrome desktop User-Agent and no other browser-mimicry — no
Cloudflare/Akamai/PerimeterX/DataDome challenge page, no `cf-ray` header, no
403 on a bare TLS handshake. This actor still uses `curl_cffi` with the
portfolio-default `chrome124` impersonation profile for resilience, but no
profile-specific blocking was ever observed during recon.

## The real find: a genuine public OCDS export behind an old-style DataTables listing

`/Open-Data` itself is server-rendered HTML shell (DNN skin chrome) whose
actual table is populated client-side via jQuery DataTables
(`../PublishedRecordHandler.ashx` as `sAjaxSource`), and its per-row
"Download" button and page-level "Download All data" button both call a
second endpoint, `ocdsjson.ashx`. Both endpoints were read directly out of
the page's own custom JS (`js/ComposeOCIDPublishdata.js`) rather than
reverse-engineered from network traffic blind.

### 1. Listing: `PublishedRecordHandler.ashx`

```
GET https://nocopo.bpp.gov.ng/PublishedRecordHandler.ashx
    ?sEcho=1&iDisplayStart=0&iDisplayLength=25&sSearch=
    &iColumns=8&iSortingCols=1&iSortCol_0=3&sSortDir_0=desc
    &mDataProp_0=ID&mDataProp_1=MDA_Code&mDataProp_2=pi_Project_Title
    &mDataProp_3=DatePublished&mDataProp_4=pi_Package_Number
    &mDataProp_5=pi_Lot_Number&mDataProp_6=pb_BudgetYear&mDataProp_7=MDA_Code
```

This is the **legacy pre-1.10 jQuery DataTables server-side protocol**
(`sEcho`/`iDisplayStart`/`iDisplayLength`/`sSearch`/`iSortCol_0`, not the
modern `draw`/`start`/`length`/`order[0][column]` names) — sending the
modern param names gets a bare ASP.NET `500 Runtime Error`. The DataTable's
own client-side config (`bServerSide: true` with no `"ajax": {...}` object,
just a bare `sAjaxSource` string) is itself the tell that this is the old
API generation. Response shape:

```json
{"iTotalRecords": 99447, "iTotalDisplayRecords": 99421, "aaData": [ {...250 columns...} ]}
```

`sSearch` performs a genuine server-side full-text filter (confirmed:
`sSearch=hospital` narrowed `iTotalDisplayRecords` from 99,447 to 3,893 and
returned rows whose buyer name contains "HOSPITAL", not just rows whose
title contains the literal word). Sorting by `iSortCol_0=3` (`DatePublished`)
descending surfaces genuinely live data — the newest row seen during
verification was dated **2026-08-21**, six days before this actor was built.

**Quirk — each row is a raw ~250-column internal database record, not a
tender.** The handler ignores the `mDataProp_*` column list entirely and
always returns the full underlying SQL row: dozens of workflow-milestone
date pairs (`ps_*`/`tp_*`/`cf_*`/`ip_*` prefixes for pre-qualification,
tendering, contract, and implementation phases), almost all populated with
the placeholder `"0001-01-01T00:00:00"` (i.e. never set) rather than real
values, plus internal-only fields like `Cr8_User_ID`/`RptRow`/
`ot_Freeze_user_update`. This is clearly an internal admin-grid endpoint
reused as-is for the public page, not a purpose-built public API. This
actor deliberately extracts only the 8 columns NOCOPO's own visible table
renders (id, ocid, procuring entity, project title, date published,
package number, lot number, budget year) rather than passing through ~240
meaningless null/placeholder fields — see `extractor.py`.

### 2. Detail: `ocdsjson.ashx` → zip → one OCDS release package

```
GET https://nocopo.bpp.gov.ng/ocdsjson.ashx?d=1&ocid=<MDA_Code>
    -> 302 Found -> Location: https://nocopo.bpp.gov.ng//downloads.aspx?file=Exported/JSON/<random>.zip
    -> 200 OK, application/zip (Content-Disposition: attachment)
```

The zip contains exactly one `.json` file: a genuine OCDS release package
(`version`, `publishedDate`, `releases: [...]`, `publisher`, `license`,
`publicationPolicy`). Each entry in `releases` is a dated snapshot tagged
with one or more of `planning`/`tender`/`award`/`contract`/
`implementation` — a single OCID accumulates a new release every time the
procurement process advances a stage, so a fully-completed procurement
looks like several releases sharing one `ocid`. A real example
(`ocds-gyl66f-521049001-00065`, a completed hospital medical-gas-plant
contract) carries all five tags across its release history with a real
award value (`129,453,710.30 NGN`) and supplier identity.

**Quirk — an unknown/invalid `ocid` still returns `200` and a valid zip.**
It is not a 404; the zip's single JSON entry is just an empty `{}` (no
`releases` key at all). This actor detects that case (`client.py`'s
`fetch_record_detail`) and raises `RecordNotFound`, which becomes a clean
`_error: "not_found"` record rather than a false "blocked" retry.

**This actor's `tenderTitle`/`tenderStatus`/`totalAwardAmount`/etc. summary
fields are its own fold across the raw `releases` array** (keep the latest
non-null value per field, in ascending release-date order; concatenate all
`awards`/`contracts` seen) — **not** an upstream "compiled release" the way
e.g. Tanzania's NeST API returns natively. NOCOPO's API has no server-side
merged view; this actor's `_merge_releases()` (`extractor.py`) is
documented as a local convenience, and the full unmodified `releases` array
is always included alongside it so nothing is lost to the fold.

### Also found, deliberately not used: the bulk "download all" export

`ocdsjson.ashx?ocid=all` (the page's own "Download All data" button, when no
rows are selected) returns a working zip too — but it unzips to a **single
~220 MB JSON file** containing every release ever published (spanning May
2021 to the present, ~99,000+ underlying rows). This is a genuine, public,
no-login bulk export and is worth knowing about for an offline/one-off
analysis, but it is impractical to fetch on every actor run (a 220 MB
download + in-memory JSON parse per run) — this actor sticks to the paged
listing + per-OCID detail endpoints instead, which scale with `maxResults`.

## TLS profile

`curl_cffi` `chrome124`, consistent with the portfolio-wide default. No
WAF or fingerprint gate was observed on any endpoint at any point during
recon or testing, so no fallback profile was needed.
