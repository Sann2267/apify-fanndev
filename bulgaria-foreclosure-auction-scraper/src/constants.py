"""Endpoints and the Bulgarian-to-English field map.

Source: ``sales.bcpea.org`` -- the official public-sale portal of the Bulgarian
Chamber of Private Enforcement Agents (Камара на частните съдебни изпълнители).
Every foreclosure sale run by a private enforcement agent in Bulgaria is
published here by law.

Recon 2026-09-18, plain HTTP, no proxy, no login:

* ``/properties?perpage=<n>&p=<page>`` -- 200, server-rendered. **The paging
  parameters are lower-case ``perpage`` and ``p``**; the obvious ``page`` and
  ``perPage`` are silently ignored and return page 1 every time, which is the
  kind of failure that looks like "the site has 12 listings".
* ``perpage`` accepts at least 100 (715 KB, 100 distinct ids, 14 pages).
* ``/properties/<id>`` -- 200, fully server-rendered detail page.
* Property ids are **sequential** (92433, 92434, ...), so a range walk reaches
  sales that have already left the active list.

No WAF, no cookie gate, no challenge.
"""

BASE = "https://sales.bcpea.org"
URL_LIST = BASE + "/properties?perpage={perpage}&p={page}"
URL_PROPERTY = BASE + "/properties/{property_id}"

TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    # Bulgarian first: the portal publishes in Bulgarian and the field labels
    # this Actor maps are the Bulgarian ones.
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5

MODES = ("list", "property", "range", "reference")

MAX_PERPAGE = 100
MAX_RANGE = 2000

# Label -> field. Labels are upper-case on cards and mixed-case in the agent
# block, so lookups are done case-insensitively on the stripped label.
FIELD_MAP = {
    "площ": "area",
    "населено място": "locality",
    "окръжен съд": "districtCourt",
    "частен съдебен изпълнител": "enforcementAgent",
    "срок": "biddingPeriodRaw",
    "обявяване на": "announcementRaw",
    "описание": "description",
    "рег. № чси": "agentRegistrationNumber",
    "адрес": "agentAddress",
    "телефон": "agentPhone",
    "мобилен телефон": "agentMobile",
    "email": "agentEmail",
    "тип": "propertyType",
    "тип строителство": "constructionType",
    "сканирани обявления": "scannedAnnouncement",
}

# "Начална цена 3 884.00 EUR 7 596.44 лв." -- the portal prints both currencies
# since Bulgaria's euro changeover, so both are captured rather than one being
# converted and the other dropped.
PRICE_LABEL = "начална цена"
