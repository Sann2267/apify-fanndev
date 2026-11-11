"""Endpoints, TLS ladder and labels for the PSA cert lookup Actor.

Recon 2026-09-18. PSA sits behind Cloudflare and the **TLS fingerprint decides
everything** -- the same request, same IP, same second:

| profile           | /cert/<n>            | /pop      | api.psacard.com |
|-------------------|----------------------|-----------|-----------------|
| chrome124         | 403 (Security Check) | login     | 403             |
| chrome99_android  | 403 (Security Check) | login     | 403             |
| safari17_0        | 403 (Security Check) | login     | 403             |
| edge101           | 403 (Security Check) | login     | 403             |
| **firefox133**    | **200 / 145 KB**     | login     | 429             |

So ``firefox133`` is not a preference, it is the entry condition. The ladder
below keeps the others as fallbacks in case Cloudflare's rule changes, with the
Firefox profile always tried first.

What is public and what is not:

* ``/cert/<certNumber>`` -- **open**. Carries the graded item's details, PSA's
  own price estimate, the population at that grade, the population higher, and
  a table of recent comparable sales with prices, dates and cert numbers.
* ``/pop/...`` (the full population report) and ``/auctionprices/...`` detail
  pages -- **redirect to a login**. They are account-only and out of scope, so
  this Actor never touches them. The population number it does return is the
  one the public cert page itself prints.
"""

BASE = "https://www.psacard.com"
URL_CERT = BASE + "/cert/{cert}"

# Firefox first -- see the table above.
TLS_LADDER = ("firefox133", "firefox135", "chrome124", "safari17_0")

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0

MODES = ("cert", "sales", "range", "reference")

# Cloudflare's interstitial. Detected by body marker, not only by status code,
# because a challenge can arrive with a 200.
CHALLENGE_MARKERS = (
    b"Security Check",
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
)

# The cert page prints item attributes as <dt>/<dd> pairs. This maps PSA's
# labels onto stable field names; an unmapped label still ships inside
# itemInformation, so a new attribute is never lost.
ITEM_FIELDS = {
    "Cert Number": "certNumber",
    "Item Grade": "itemGrade",
    "Label Type": "labelType",
    "Reverse Cert/Barcode": "reverseCertBarcode",
    "Year": "year",
    "Brand/Title": "brand",
    "Subject": "subject",
    "Card Number": "cardNumber",
    "Category": "category",
    "Variety/Pedigree": "varietyPedigree",
    "Set Name": "setName",
}

# Ceiling for the sequential range mode, so a typo cannot start a 10-million
# request run.
MAX_RANGE = 5000
