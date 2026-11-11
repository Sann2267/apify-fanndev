"""URLs, facets, headers -- all in one place.

Recon summary (2026-09-08): alodokter.com is one of Indonesia's two main
consumer health platforms. Its `/cari-dokter` section is **server-rendered**
and every listing page embeds a schema.org `ItemList` of `Physician`
objects carrying the whole record -- name, sub-specialty, hospital and its
address, consultation price in IDR, satisfaction rating and review count,
and next-available-schedule text. No login, no WAF challenge.

Why Alodokter and not Halodoc: Babak 42 of ACTOR_MARKET_RESEARCHER_NEW.md
named Halodoc as the primary Indonesian target on a 286 KB probe.
Re-checked here, halodoc.com/cari-dokter is an **Angular SPA** that renders
"Maaf, dokter tidak dapat ditemukan" (no doctors found) without a location,
carries no doctor data in its HTML, exposes no `__NEXT_DATA__`/`__NUXT__`
payload, and its main bundle (123 KB) holds no API host at all -- the data
path lives in lazy-loaded chunks. Page weight was mostly framework, not
records. Alodokter, the other Indonesian target listed in the same Babak,
serves the same data type fully rendered, so it is the executable one.

BookingCare (VN, Next.js with `__NEXT_DATA__`, 317 KB) remains a live
option for the same vein in a different jurisdiction.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.alodokter.com"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

# --- routes ------------------------------------------------------------
# Specialty listing:        /cari-dokter/<specialty>
# Specialty + city:         /cari-dokter/<specialty>/<city>
# Page N (both shapes):     ?page=N        <- query string, NOT a path segment
# Doctor profile:           /cari-dokter/<doctor-slug>
PATH_SPECIALTY = "/cari-dokter/{specialty}"
PATH_SPECIALTY_CITY = "/cari-dokter/{specialty}/{city}"

MODES = ["specialty", "doctor", "reference"]

# 10 doctors per listing page (numberOfItems in the ItemList). A page past
# the end (?page=500) returns 200 with an ItemList of zero items, so an
# empty page is a clean stop signal -- unlike some sites in this portfolio,
# it does not clamp back to page 1.
PAGE_SIZE = 10

# Specialty slugs verified live on 2026-09-08 -- each returned a listing
# with 10 doctors. Slugs that do NOT exist return HTTP 200 with a ~17 KB
# soft-404 shell (dokter-rehabilitasi-medik, dokter-anestesi,
# dokter-kulit-dan-kelamin were all rejected this way), so page weight is
# the tell, not the status code.
SPECIALTIES = [
    "dokter-anak",
    "dokter-kandungan",
    "dokter-umum",
    "dokter-gigi",
    "dokter-kulit",
    "dokter-jantung",
    "dokter-saraf",
    "dokter-tht",
    "dokter-mata",
    "dokter-penyakit-dalam",
    "dokter-bedah",
    "dokter-paru",
    "dokter-gizi",
    "dokter-ortopedi",
    "dokter-urologi",
    "dokter-jiwa",
    "psikiater",
]

# A listing shorter than this (in bytes) is the soft-404 shell, not a real
# specialty page.
SOFT_404_MAX_BYTES = 40_000

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
