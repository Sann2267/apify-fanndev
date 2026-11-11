"""Shared constants for Indonesia's SPSE Nasional (national tender search)
scraper.

See CRAWLING_METHOD.md for how these endpoints were discovered and
verified. `spse.inaproc.id` is LKPP's (Lembaga Kebijakan Pengadaan
Barang/Jasa Pemerintah -- the National Public Procurement Agency) national
aggregator over Indonesia's ~600+ independent LPSE (Layanan Pengadaan Secara
Elektronik) instances, one per government agency/region. Its `/nasional`
section is a single, purpose-built cross-agency search -- not a proxy into
any one LPSE -- so this actor covers the whole country from one host,
instead of needing 600+ separate per-agency actors.
"""

ROOT = "https://spse.inaproc.id"
BASE = f"{ROOT}/nasional"

# The search page itself. A fresh GET here (with the desired filter query
# params -- tahun/kategoriId/instansiId/rekanan) is required before every
# listing POST: it issues the SPSE_SESSION cookie, embeds a fresh
# `authenticityToken`, AND computes the filtered AJAX URL this actor must
# POST to next -- see client.py's SpseSession.warm_up().
SEARCH_PAGE = f"{BASE}/lelang"

# Fallback/default shape of the server-side DataTables listing endpoint
# behind the search page's "CARI PAKET" table -- normally overwritten per
# request by whatever filtered AJAX URL warm_up() discovers. The DataTable's
# own client-side "search box" (`search[value]` in the POST body) is a decoy
# -- confirmed ignored server-side; real filtering only works via the search
# page's query string. See CRAWLING_METHOD.md.
LIST_ENDPOINT = f"{BASE}/dt/lelang"

# One tender's public announcement detail page. Requires a same-origin
# Referer header (see CRAWLING_METHOD.md) -- without it the app's own router
# (not a WAF) returns its "Akses Ditolak" (Access Denied) error page.
DETAIL_ENDPOINT_TEMPLATE = f"{BASE}/lelang/{{kode}}/pengumumanlelang"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

AJAX_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0  # seconds, exponential backoff

# Rows per /dt/lelang request. The endpoint's own recordsTotal/recordsFiltered
# are a non-functional int32-max placeholder (see CRAWLING_METHOD.md) -- an
# empty "data" array is the only reliable end-of-results signal, not a count.
LIST_PAGE_SIZE = 25
LIST_PAGE_DELAY = 1.0  # pause between sequential list-page requests
MAX_LIST_PAGES_SAFETY_CAP = 400

# The site's own "Tahun Anggaran" (fiscal year) filter dropdown, observed
# 2022-2028 at build time -- LKPP adds a new year at each end as budget
# cycles roll forward, so this is a soft default/sanity bound, not enforced.
KNOWN_YEAR_RANGE = (2015, 2035)
