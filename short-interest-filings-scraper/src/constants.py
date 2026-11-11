"""Endpoints, headers and static tables for the short-interest / filings Actor.

Three independent official sources, verified live 2026-09-18 with plain HTTP,
no key, no login, no proxy:

1. **Nasdaq** ``api.nasdaq.com`` -- bi-monthly short interest per ticker, 24
   settlement dates per response. Published **only for Nasdaq-listed stocks**;
   NYSE names (GME, AMC, F, T) come back with data=null and an explicit
   ``message``. See MSG_NOT_NASDAQ.
2. **FINRA** ``cdn.finra.org`` -- daily short-sale volume for *every* US
   symbol (~12,300 rows/day), pipe-delimited text, published with a 1-2 day
   lag. A date that is not published yet answers **403 AccessDenied** from S3,
   which means "no file", not "blocked".
3. **SEC** ``data.sec.gov`` / ``efts.sec.gov`` / ``www.sec.gov`` -- filing
   history per company, EDGAR full-text search, and the ticker-to-CIK map.

Header policy differs per host and that difference matters:

* Nasdaq **rejects** a custom User-Agent (HTTP/2 stream reset) because it no
  longer matches the impersonated TLS fingerprint. It gets the browser UA.
* SEC asks automated clients to identify themselves with a contact address, and
  accepts that override happily.
"""

# --- Nasdaq ---------------------------------------------------------------
NASDAQ_SHORT_INTEREST = "https://api.nasdaq.com/api/quote/{symbol}/short-interest?assetClass={asset_class}"
NASDAQ_INFO = "https://api.nasdaq.com/api/quote/{symbol}/info?assetclass={asset_class}"
NASDAQ_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nasdaq.com/",
    "Origin": "https://www.nasdaq.com",
}
# The exact sentence Nasdaq returns for non-Nasdaq listings. Matched as a
# prefix so wording drift downgrades to a generic empty answer rather than
# silently mislabelling a real outage as "not listed".
MSG_NOT_NASDAQ = "Short interest is not available"

# --- FINRA ----------------------------------------------------------------
# CNMS = consolidated NMS (all venues). The venue-specific files share the
# same columns, which is why one parser serves all of them.
FINRA_DAILY = "https://cdn.finra.org/equity/regsho/daily/{venue}shvol{date}.txt"
FINRA_VENUES = {
    "consolidated": "CNMS",
    "nasdaq-carteret": "FNSQ",
    "nasdaq-chicago": "FNQC",
    "nyse": "FNYX",
    "finra-adf": "FORF",
}
FINRA_COLUMNS = ("Date", "Symbol", "ShortVolume", "ShortExemptVolume", "TotalVolume", "Market")

# --- SEC ------------------------------------------------------------------
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik10}.json"
SEC_FULLTEXT = "https://efts.sec.gov/LATEST/search-index"
SEC_TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"
SEC_FILING_INDEX = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{document}"
SEC_FILING_PAGE = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik10}&type=&dateb=&owner=include&count=40"
# SEC's fair-access policy asks for a declared identity and <=10 requests/s.
SEC_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Apify Actor short-interest-filings-scraper (contact via apify.com/fanndev)",
}
# EDGAR full-text search returns at most 100 hits per page and refuses to page
# past 10,000 -- both limits are enforced by the API, not chosen here.
SEC_FULLTEXT_PAGE = 100
SEC_FULLTEXT_MAX = 10000

TLS_PROFILE = "chrome124"
MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5

MODES = (
    "short-interest",
    "short-volume",
    "filings",
    "filing-search",
    "company",
    "reference",
)

# How many trading days back the reference / auto-date logic is willing to walk
# looking for the newest published FINRA file.
FINRA_LOOKBACK_DAYS = 8
