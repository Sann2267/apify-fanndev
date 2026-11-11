"""Endpoint map and hard limits for Traveloka's flight-pricing surface.

Only price *discovery* endpoints live here. The itinerary search that returns
individual flights (`/v2/flight/search/initial` and the SSE feed behind it) is
guarded by AWS WAF with the `captcha` action and cannot be read headlessly, so
this actor tracks fares rather than schedules. See the README.
"""

from __future__ import annotations

AIRPORT_SEARCH = ("/v2/airport/search-nexus", "flightDiscovery")
MONTHLY_CHEAPEST = ("/v2/flight/cheapest-price/monthly", "flightDiscovery")
PRICE_TABLE = ("/v2/flight/price-table", "flight")

REFERER_FLIGHT = "flight"

SEAT_CLASSES = ("ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST")

# `/v2/flight/price-table` silently returns ZERO cells once the depart-window
# times the return-window exceeds 100 date pairs. It does not error -- an
# oversized request just looks like "no fares on this route", so the actor
# chunks every grid to stay under the cap.
MAX_GRID_CELLS = 100
MAX_WINDOW_DAYS = 60

# The monthly endpoint answers with 12 forward months regardless of the date
# passed; the date only anchors which month the series starts from.
MONTHLY_SERIES_LENGTH = 12

AIRPORT_TYPES = ("AIRPORT", "AREA")
