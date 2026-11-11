"""Endpoints and limits for Traveloka's intercity ground-transport surface.

Bus and shuttle inventory is fully open. Train is reachable but Traveloka's
backend currently answers every search with "Kereta Tidak Tersedia" regardless
of route, date, station-or-city code and provider, so the train endpoints are
recorded here for the day that changes rather than wired into a mode that would
return nothing. See the README.
"""

from __future__ import annotations

BUS_AUTOCOMPLETE = ("/v2/bus/search/autoComplete/v2", "bus")
BUS_INVENTORY = ("/v2/bus/search/inventory/v3", "bus")
BUS_TRIP_POLICY = ("/v2/bus/trip/policy", "bus")

# Verified reachable, verified empty (2026-09-20). Payload is
# {origin, destination, departureDate:{date,month,year}, numAdult, numInfant,
#  currency, roundTrip, providerType} with providerType in {KAI, KCIC}.
# Note the date object uses `date`, not `day`, unlike every other Traveloka API.
TRAIN_INVENTORY = ("/v2/train/search/inventoryv2", "train")
TRAIN_AUTOCOMPLETE = ("/v2/train/search/autocomplete", "train")

REFERER_BUS = "bus-and-shuttle/search"

# One city pair on one date can return several thousand inventories, because
# Traveloka expands every pickup-point x drop-off-point x departure combination.
# A single Jakarta-Bandung day measured 9,236 entries and ~38 MB.
DEFAULT_MAX_DEPARTURES = 200
HARD_MAX_DEPARTURES = 5000

DEDUPE_MODES = ("none", "trip", "operator")

PRODUCT_TYPES = ("BUS", "SHUTTLE")
