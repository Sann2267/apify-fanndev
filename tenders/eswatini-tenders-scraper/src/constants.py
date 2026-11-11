"""Shared constants for the ESPPRA (Eswatini Public Procurement Regulatory
Agency) scraper.

ESPPRA runs its own custom-built PHP site (footer literally reads "This
Website Is Created By ESPPRA IT Department") -- NOT one of the shared vendor
e-GP platforms seen elsewhere in this portfolio's tender vertical (European
Dynamics/"ePPS": Ghana/Zambia/Jamaica; Perago Systems: Sierra Leone/Malawi).
See CRAWLING_METHOD.md for the full recon writeup, including the
sppra.co.sz -> esppra.co.sz redirect and the missing-intermediate-cert issue
that requires verify=False on every request.
"""

BASE = "https://esppra.co.sz/sppra"

# Each entry is a public listing view, reachable with a plain GET, no login.
# "kind": "jobbox"     -- server-rendered HTML page, one <div class="list-item
#                          job-box"> per row, GET-paginated via ?Page=N.
# "kind": "json_table" -- a DataTables server-side JSON endpoint, single call,
#                          no pagination (register is small).
LIST_CONFIGS = {
    "tenders": {
        "path": f"{BASE}/tender.php",
        "kind": "jobbox",
        "title": "Invitation To Tender (currently open for bidding)",
    },
    "award_intentions": {
        "path": f"{BASE}/award_intention.php",
        "kind": "jobbox",
        "title": "Intention To Award (notice before contract signature)",
    },
    "suspended_suppliers": {
        "path": f"{BASE}/api/suspendedSupplier_list.php",
        "kind": "json_table",
        "title": "Suspended Suppliers (debarment register)",
    },
}

VALID_LIST_TYPES = tuple(LIST_CONFIGS.keys())

RECORD_TYPES = {
    "tenders": "TENDER_INVITATION",
    "award_intentions": "TENDER_AWARD_INTENTION",
    "suspended_suppliers": "SUSPENDED_SUPPLIER",
}

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0
