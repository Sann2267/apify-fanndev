# Crawling Method — Indonesia Government Tenders (SPSE Nasional / LKPP)

**Last verified:** 2026-08-27

## Target discovery — a federated system with one real national aggregator

Indonesia's e-procurement law requires every ministry, agency, state
university, and regional government to run its own **LPSE** (Layanan
Pengadaan Secara Elektronik) instance -- there are 600+ of them,
independently hosted. Individually that would be far too fragmented for one
actor, matching this project's explicit stop condition. But **LKPP**
(Lembaga Kebijakan Pengadaan Barang/Jasa Pemerintah, the National Public
Procurement Agency) also runs a genuine national aggregator on top: **SPSE
Nasional**, at `https://spse.inaproc.id/nasional`, with its own
purpose-built cross-agency search ("CARI PAKET" / "Search Package") --
confirmed as the real, official, national-level source, not a fan-made
mirror:

- Reachable directly from the "CARI PAKET" nav link on `spse.inaproc.id`'s
  own homepage ("Portal SPSE - Pencarian LPSE Indonesia"), which itself is
  linked from LKPP's official site (`www.lkpp.go.id`) and INAPROC's own
  "Tentang Kami" page.
- Every tender's detail page footer/URL structure is served from the same
  `spse.inaproc.id/nasional/*` host LKPP controls -- not a third-party
  reseller.
- Live data spans real agencies nationwide in one search: national capital
  megaprojects (Otorita Ibu Kota Nusantara), state universities
  (Universitas Airlangga, Universitas Sriwijaya), and district/regency
  governments (Kab. Lampung Selatan, Kab. Lampung Timur) all appear in the
  same result set for the same query.

**Two other candidate sources were checked and ruled out:**

- **`inaproc.id`** (the flagship LKPP domain) is fully gated behind a
  Cloudflare "Verifikasi Singkat: Kami Sedang Memastikan Anda Manusia Asli!"
  managed challenge on every path tested (including `/robots.txt` itself),
  across all four TLS profiles (`chrome124`, `chrome131`, `safari17_0`,
  `edge101`) -- a genuine JS challenge wall, not used by this actor.
  `spse.inaproc.id` is a **separate subdomain** with its own, much lighter
  Cloudflare configuration (present, but not challenging plain `curl_cffi`
  requests) -- confirmed independently rather than assuming the same
  gate applies portfolio-wide across `*.inaproc.id`.
- **`opentender.net`** (a civil-society OCDS conversion of LKPP data,
  previously the go-to open-data source per Open Contracting Partnership
  case studies) now 301-redirects its entire root domain to
  `dev.opentender.net`, whose `robots.txt` is a blanket `User-agent: *` /
  `Disallow: /` -- ruled out as a stop condition on that specific host. No
  OCDS-standard JSON API was found live on LKPP's own infrastructure at
  build time (unlike Tanzania's NeST or Nigeria's NOCOPO in this
  portfolio) -- SPSE Nasional's own proprietary JSON/HTML is used instead.

## robots.txt

`spse.inaproc.id/robots.txt`:

```
User-agent: *
Allow: /
Allow: /surabaya
Allow: /kemenkeu
... (600+ explicit per-LPSE-slug Allow lines) ...
Allow: /nasional

Disallow: /test
Disallow: /test-error
Disallow: /_error
Disallow: /api/redirect

Allow: /*.css
Allow: /*.js
...

Sitemap: https://spse.inaproc.id/sitemap.xml
Crawl-delay: 1
```

A single flat `User-agent: *` group -- no other `User-agent:` line exists
anywhere in the file -- no blanket `Disallow: /`, and no
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai
mention anywhere. `/nasional` (everything this actor uses) is explicitly
`Allow`ed. A `Crawl-delay: 1` is honored via this actor's built-in 1-second
pause between sequential list-page requests.

## No login required to browse or view tender detail

The "CARI PAKET" search table and every tender's public "Pengumuman"
(Announcement) detail page were confirmed reachable with a fresh,
cookie-less client -- no account, no API key. `LOGIN` is a separate nav
item on the search page for registered bidders/procuring officers; nothing
gates *viewing* published tenders. The one access quirk found (below) is an
app-level Referer check, not a login wall.

## Session mechanics: a session cookie and a matching CSRF token, not a WAF

Unlike most actors in this portfolio, this target needs light session state
carried across requests, discovered by reading the search page's own inline
JS rather than reverse-engineering blind:

1. `GET /nasional/lelang` (the search page) issues an `SPSE_SESSION` cookie
   whose value literally embeds `___AT=<40-hex-char token>` -- the very
   same `authenticityToken` the page's inline script also uses as a form
   field when it initializes the DataTable:
   ```js
   var table = $("#tbllelang").DataTable({
       ajax: {
           url: "/nasional/dt/lelang?tahun=2028",
           type: 'POST',
           data: function (d) { d.authenticityToken = 'c57bfddb2c...'; }
       }
   })
   ```
2. `POST` to that exact `ajax.url` (with `draw`/`start`/`length`/
   `authenticityToken`, sent with the *same* cookie jar as step 1) returns
   the page of results as JSON.

Because the token is bound to that specific session cookie, this actor
keeps one `curl_cffi.AsyncSession` open per logical unit of work (the whole
`list` run, or one `detail` lookup) and reuses it for every request in that
unit, rather than this portfolio's usual "fresh session per request"
pattern -- see `client.py`'s `SpseSession`. A `403` mid-run triggers one
automatic re-warm (fresh `GET /nasional/lelang` with the same filters, for
a new cookie+token+ajax-url triple) and retry, treating an expired token as
a transient condition rather than a hard block.

**Quirk -- `recordsTotal`/`recordsFiltered` are a non-functional
`2147483647` (`int32` max) placeholder on every response**, regardless of
how few rows actually match. This actor never trusts that field; the only
reliable end-of-results signal is an empty `data` array, which was
confirmed by requesting `start=999999` and observing `{"data": []}`.

**Quirk -- the DataTable's own "search box" (`search[value]` in the POST
body) is silently ignored server-side.** Sending a nonsense value
(`zzzznonexistentxyz`) alongside `tahun=2026` returned byte-identical
results to sending no search value at all -- confirmed with a controlled
A/B request pair, not assumed from spot-checking titles. **Real filtering
happens through the search page's own query string instead**: the search
form (`kategoriId`, `tahun`, `instansiId`, `rekanan`, `kontrak_status`,
`kontrak_tipe` `<select>`/`<input>` elements, each wired to
`onchange="...this.form.submit()"`) is what the page actually reads server-side,
and it re-renders the *ajax URL itself* with those params baked in --
`GET /nasional/lelang?tahun=2026&kategoriId=7&instansiId=L4` renders
`ajax.url = "/nasional/dt/lelang?kategoriId=7&tahun=2026&instansiId=L4"`.
This actor's `SpseSession.warm_up()` does that filtered GET first and reads
the resulting `ajax.url` out of the response, instead of assuming a fixed
endpoint shape. Confirmed genuinely functional (not just cosmetically
present in the URL) for all three query-string filters used here:
- `tahun=2026` alone vs `tahun=2026&instansiId=L4` (BKKBN) -- the latter
  narrowed 25+ results down to exactly 1, matching BKKBN's real tender
  count for that year.
- `rekanan=PT` returned a materially different, smaller result set than no
  `rekanan` at all -- a genuine full-text filter on the winning
  contractor/company name (labeled "Nama Pemenang Berkontrak" in the UI).
- `kategoriId=7` vs `kategoriId=2` returned disjoint result sets, each
  internally consistent with that category's tenders.

`kategoriId`'s known option values (from the search page's own `<select>`):
`0`=Pengadaan Barang, `2`=Pekerjaan Konstruksi, `1`=Jasa Konsultansi Badan
Usaha Non Konstruksi, `5`=Jasa Konsultansi Badan Usaha Konstruksi,
`4`=Jasa Konsultansi Perorangan Non Konstruksi, `6`=Jasa Konsultansi
Perorangan Konstruksi, `3`=Jasa Lainnya, `7`=Pekerjaan Konstruksi
Terintegrasi. `instansiId` has hundreds of values (one per agency, e.g.
`L4`=BKKBN, `L25`=Kementerian Keuangan) -- exposed as a free-text input
rather than an exhaustive enum.

**Quirk -- the `tahun` (fiscal year) filter defaults to the *last* year in
the site's own dropdown (2028 at build time, out of a 2022-2028 range), not
the current year** -- because Indonesian multi-year construction contracts
(e.g. Ibu Kota Nusantara buildings spanning 2026-2028) are filed under every
budget year they touch, so a forward year still surfaces active current
tenders. This actor instead defaults `tahunAnggaran` to the current
calendar year for more intuitive "what's happening now" behavior, while
still letting the caller pick any year 2015-2035 (a soft bound, not
enforced upstream -- LKPP adds a year to each end of the dropdown as budget
cycles roll forward).

## Detail page: an app-level Referer check, not a WAF

`GET /nasional/lelang/<kode>/pengumumanlelang` **without** a `Referer`
header returns a `403` with the app's own "Terjadi Kesalahan" / "Akses
Ditolak! Anda tidak diizinkan membuka halaman ini" (Access Denied) page --
this is the application's own router guard (it wants to see the request
originate from the search results page), not a Cloudflare/WAF block: no
`cf-ray`-style challenge page, and it disappears entirely once
`Referer: https://spse.inaproc.id/nasional/lelang` is sent. A genuinely
unknown/invalid tender code instead 404s (a Cloudflare-templated error
page, since Cloudflare wraps the origin's own error responses) -- this
actor's `client.py` distinguishes the two and raises `RecordNotFound` only
for the 404 case, not for a missing Referer (which it always sends).

**Quirk -- detail-page fields are parsed generically by label, not fixed
position.** The announcement page is a plain `<table class="table-bordered">`
of Indonesian `<th>`/`<td>` label/value rows, but the exact set of rows
varies by procurement type (a Papua-restriction row is present-but-hidden
on some, a "Reverse Auction" row appears on some but not others, etc).
`extractor.py` translates ~15 known labels into readable camelCase keys via
a lookup table, and falls back to a slugified version of any *unrecognized*
label rather than dropping it -- confirmed live: a "Reverse Auction" row and
a "Peserta Tender" (participant count) row neither actor author anticipated
both came through correctly as `reverseAuction`/`pesertaTender` on the
first real test run, exactly because of this fallback.

**Quirk -- bidder identities are anonymized.** The separate `/peserta`
(participants) tab lists entries as literal "Peserta 1", "Peserta 2", etc,
not real company names -- SPSE itself masks bidder identity until an award
is finalized. This actor does not fetch that tab separately; the
announcement page's own "Peserta Tender: N peserta" summary line already
carries the only genuinely useful signal (participant count) from it.

**Quirk -- `nilaiKontrak` (contract value) is genuinely populated once
awarded**, not a permanent placeholder: most in-progress tenders show
"Nilai Kontrak belum dibuat" (contract not yet made, mapped to `null` by
this actor), but confirmed-completed tenders carry a real signed value in
exact rupiah (e.g. `Rp. 24.498.873.959,00` for a completed Universitas
Sriwijaya building contract) -- genuine award-value transparency, not
NOCOPO-Nigeria's pattern of a summary fold being needed to surface it.

## TLS profile

`curl_cffi` `chrome124`, consistent with the portfolio-wide default. No WAF
or fingerprint gate was observed on `spse.inaproc.id/nasional/*` at any
point during local recon or testing (the Cloudflare challenge seen on the
separate `inaproc.id` domain does not apply here) -- `chrome124` was
sufficient throughout, so no fallback profile ladder was needed.

## Proxy quirk found on the Apify platform: non-Indonesian residential exits 403

Recon (this document, above) was all done from a local machine's own IP and
passed cleanly with no proxy at all. Once deployed, though, the first
smoke-test run on the Apify platform -- using no proxy, then explicitly
using Apify's default Residential proxy group (no country pin) -- both
403'd on the very first `GET /nasional/lelang` warm-up request. Adding
`apifyProxyCountry: "ID"` to the same Residential proxy configuration fixed
it immediately (confirmed on the very next run, same code, same TLS
profile). This points to Cloudflare's bot-management scoring this
particular government portal's traffic by *geography*, not just TLS/JA3
fingerprint or datacenter-vs-residential ASN class -- a non-Indonesian
residential IP hitting a niche Indonesian public-sector site is apparently
enough signal on its own. This actor's `input_schema.json` default
`proxyConfiguration` pins `apifyProxyGroups: ["RESIDENTIAL"]` +
`apifyProxyCountry: "ID"` for exactly this reason; a user who overrides it
to a non-Indonesian country or plain Datacenter proxy should expect 403s.
