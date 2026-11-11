"""Endpoints, TLS choice and the hard limits Google imposes on this surface.

Source: ``www.google.com/travel`` -- Google Hotels. Two server-rendered
surfaces carry everything this Actor needs:

* ``/travel/search?q=<query>`` -- 2.7 MB of SSR HTML holding **21 hotel cards**
  per query, each with price, rating, review count, star class, amenities and
  a deal flag. Google's own pagination is a ``batchexecute`` RPC, so 21 is the
  HTTP-only ceiling for one query (see PAGINATION note below).
* ``/travel/hotels/entity/<entityId>/prices`` -- the rate table. Rows carrying
  ``data-is-organic="true"`` under a ``div[data-partner-id]`` are the real
  cross-OTA quotes: 17-23 OTAs per hotel on a major property (Expedia,
  Agoda, Booking.com, Trip.com, Klook, DerbySoft...). Rows behind ``/aclk?``
  are paid placements for *other* hotels and are exposed separately.

Recon 2026-09-18, plain HTTP from a residential IP, no cookie and no login.

Hard limits proven by probe, not assumed:

* **Currency cannot be chosen.** ``curr=``, ``currency=`` and ``gl=`` are all
  accepted and silently ignored -- the response currency follows the **exit
  IP**. The proxy country is therefore the currency control, and every record
  reports the currency actually returned instead of pretending it was asked
  for.
* **Dates cannot be chosen.** Google carries the stay window in the protobuf
  ``ts=`` parameter. ``checkin``/``checkout`` are ignored, and five
  hand-encoded ``ts`` layouts were all ignored too, so the quoted window is
  Google's default (tonight, 1 night). Every record carries the window Google
  actually priced, so a caller can never mistake it for a window they picked.
* **PAGINATION: there is none for search.** ``start=20`` returns the same 21
  hotels. Breadth comes from issuing narrower queries, not deeper pages.
"""

BASE = "https://www.google.com"
URL_SEARCH = BASE + "/travel/search?q={query}&hl={hl}&gl={gl}"
URL_ENTITY = BASE + "/travel/hotels/entity/{entity_id}/prices?hl={hl}&gl={gl}"

# chrome124 answered 200 on the first probe and stayed 200 across the whole
# recon. chrome131 is widely blocklisted in 2026 (.ai/CLAUDE.md rule 2), so it
# is deliberately last in the ladder rather than first.
TLS_PROFILE = "chrome124"
TLS_LADDER = ("chrome124", "firefox133", "safari17_0", "chrome99_android", "edge101", "chrome131")

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0

MODES = ("search", "hotel", "rates", "sponsored", "reference")

# Google hands back 21 cards per query; anything far below that on a 200 means
# a degraded page rather than a small city.
CARDS_PER_QUERY = 21

# A real Google Hotels page is 2.5 MB+. A 200 that is orders of magnitude
# smaller is a challenge, a consent wall or an error shell -- never content.
MIN_PAGE_BYTES = 250_000

# aria-label prefixes Google puts on the *secondary* links inside a card. They
# point at the same entity as the title link, so they are skipped when
# collecting hotels rather than being emitted as duplicate hotels.
SECONDARY_LABEL_PREFIXES = ("View prices for", "Photos for", "Photo of", "Photos of")
