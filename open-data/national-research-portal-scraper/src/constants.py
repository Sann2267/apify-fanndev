"""Portals, endpoints and per-portal capabilities.

Three national research portals, all verified open on 2026-09-18 with plain
HTTP, no key, no login, no proxy:

* **Garuda** (Indonesia, Ministry of Higher Education) --
  ``garuda.kemdiktisaintek.go.id``. Server-rendered HTML with three separate
  indexes: documents, journals and authors. 7,461 documents for "machine
  learning", 29,195 authors for "budi", 3,059 pages of journals.
  NOTE: the old ``garuda.kemdikbud.go.id`` host **no longer resolves** -- the
  portal moved with the ministry's split, the same way SINTA did.
* **CiNii Research** (Japan, National Institute of Informatics) --
  ``cir.nii.ac.jp/opensearch``. A documented OpenSearch API returning JSON,
  with real total counts and cursor-style paging.
* **KCI** (Korea Citation Index, National Research Foundation) --
  ``kci.go.kr``. Server-rendered results table; the working search path is
  ``poArtiSearList.kci`` with ``poSearchBean.searchQuery`` (the paths that look
  right in the UI -- ``poSereArtiSearList.kci`` -- return 404).

**Lattes (Brazil) is deliberately not supported.** ``buscatextual.cnpq.br``
answers 200 but its result list needs a POST inside an established session and
returns nothing to a plain query, so shipping it would mean shipping an empty
portal. The recon is written up in CRAWLING_METHOD.md for whoever picks it up.
"""

TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5

MODES = ("documents", "journals", "authors", "reference")
PORTALS = ("garuda", "cinii", "kci")

# Which portal can answer which mode. An unsupported combination produces an
# explicit error row naming the portals that *do* support it, instead of an
# empty dataset the user has to guess about.
PORTAL_MODES = {
    "garuda": ("documents", "journals", "authors"),
    "cinii": ("documents",),
    "kci": ("documents",),
}

PORTAL_NAMES = {
    "garuda": "Garuda - Garba Rujukan Digital (Indonesia)",
    "cinii": "CiNii Research (Japan)",
    "kci": "Korea Citation Index (South Korea)",
}

GARUDA_BASE = "https://garuda.kemdiktisaintek.go.id"
GARUDA_DOCUMENTS = GARUDA_BASE + "/documents?q={query}&page={page}"
GARUDA_JOURNALS = GARUDA_BASE + "/journal?q={query}&page={page}"
GARUDA_AUTHORS = GARUDA_BASE + "/author?q={query}&page={page}"

CINII_SEARCH = "https://cir.nii.ac.jp/opensearch/all"
CINII_ARTICLES = "https://cir.nii.ac.jp/opensearch/articles"
# The API returns at most 200 per request and pages with a 1-based `start`.
CINII_PAGE_SIZE = 50

KCI_BASE = "https://www.kci.go.kr"
KCI_SEARCH = KCI_BASE + "/kciportal/po/search/poArtiSearList.kci"
KCI_ARTICLE = KCI_BASE + "/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId={arti_id}"
KCI_PAGE_SIZE = 50
