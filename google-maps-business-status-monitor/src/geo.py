"""Geographic targeting and filtering.

Two distinct jobs, and it matters that they are separate:

1. **Targeting** -- deciding where Google searches. The tbm=map viewport block
   (`!1d` span, `!2d` lon, `!3d` lat) genuinely steers the result set, so a
   bounding box is covered by tiling it into overlapping search centres.
2. **Filtering** -- discarding leads outside the requested area. Google honours
   a viewport loosely and will happily return a place just outside it, so the
   final say belongs to each lead's own coordinates, which the search response
   supplies exactly.

Doing only (1) silently includes out-of-area leads; doing only (2) means Google
never looks in most of the box. Both are needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEG_LAT = 110.574

# Bounding boxes as (south, west, north, east). A deliberately small, honest
# list -- a real geocoder is a network dependency this actor does not need.
# Anything absent should be expressed as an explicit bounding box.
NAMED_AREAS: dict[str, tuple[float, float, float, float]] = {
    "jakarta": (-6.4, 106.6, -6.0, 107.0),
    "bandung": (-7.0, 107.5, -6.8, 107.8),
    "surabaya": (-7.4, 112.6, -7.1, 112.9),
    "medan": (3.5, 98.6, 3.7, 98.8),
    "bali": (-8.9, 114.4, -8.0, 115.8),
    "denpasar": (-8.75, 115.15, -8.6, 115.3),
    "singapore": (1.13, 103.6, 1.48, 104.1),
    "kuala lumpur": (2.9, 101.5, 3.3, 101.8),
    "bangkok": (13.5, 100.3, 14.0, 100.9),
    "manila": (14.4, 120.9, 14.75, 121.15),
    "ho chi minh city": (10.6, 106.5, 10.9, 106.9),
    "london": (51.28, -0.51, 51.70, 0.33),
    "paris": (48.80, 2.22, 48.91, 2.47),
    "berlin": (52.34, 13.09, 52.67, 13.76),
    "madrid": (40.31, -3.83, 40.64, -3.52),
    "new york": (40.48, -74.27, 40.92, -73.68),
    "los angeles": (33.70, -118.67, 34.34, -118.16),
    "chicago": (41.64, -87.94, 42.02, -87.52),
    "san francisco": (37.70, -122.52, 37.84, -122.35),
    "seattle": (47.48, -122.44, 47.74, -122.22),
    "toronto": (43.58, -79.64, 43.86, -79.12),
    "sydney": (-34.0, 150.9, -33.7, 151.35),
    "melbourne": (-38.0, 144.6, -37.6, 145.3),
    "tokyo": (35.5, 139.5, 35.85, 139.95),
    "dubai": (24.9, 54.9, 25.4, 55.5),
    "indonesia": (-11.0, 95.0, 6.0, 141.0),
    "malaysia": (0.8, 99.6, 7.4, 119.3),
    "thailand": (5.6, 97.3, 20.5, 105.6),
    "philippines": (4.6, 116.9, 21.1, 126.6),
    "vietnam": (8.2, 102.1, 23.4, 109.5),
    "united kingdom": (49.9, -8.6, 60.9, 1.8),
    "france": (41.3, -5.1, 51.1, 9.6),
    "germany": (47.3, 5.9, 55.1, 15.0),
    "united states": (24.4, -125.0, 49.4, -66.9),
    "australia": (-43.6, 112.9, -10.7, 153.6),
    "japan": (24.0, 122.9, 45.5, 153.9),
}


@dataclass
class BoundingBox:
    south: float
    west: float
    north: float
    east: float

    def contains(self, lat: float, lng: float) -> bool:
        if not (self.south <= lat <= self.north):
            return False
        if self.west <= self.east:
            return self.west <= lng <= self.east
        return lng >= self.west or lng <= self.east   # crosses the antimeridian

    @property
    def center(self) -> tuple[float, float]:
        return ((self.south + self.north) / 2, (self.west + self.east) / 2)

    @property
    def height_km(self) -> float:
        return (self.north - self.south) * KM_PER_DEG_LAT

    @property
    def width_km(self) -> float:
        mid_lat = math.radians((self.south + self.north) / 2)
        return (self.east - self.west) * KM_PER_DEG_LAT * max(math.cos(mid_lat), 0.01)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bbox_from_radius(lat: float, lng: float, radius_km: float) -> BoundingBox:
    d_lat = radius_km / KM_PER_DEG_LAT
    d_lng = radius_km / (KM_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01))
    return BoundingBox(lat - d_lat, lng - d_lng, lat + d_lat, lng + d_lng)


def tile_bbox(box: BoundingBox, tile_km: float) -> list[tuple[float, float]]:
    """Cover a bounding box with search centres roughly tile_km apart.

    Google returns a bounded number of results per query however wide the
    viewport, so one search over a whole city under-samples it badly. Tiling
    trades requests for coverage; the caller controls the trade via tile_km.
    """
    tile_km = max(tile_km, 0.2)
    rows = max(1, math.ceil(box.height_km / tile_km))
    cols = max(1, math.ceil(box.width_km / tile_km))
    # Guard against a pathological request turning into tens of thousands of calls.
    rows, cols = min(rows, 40), min(cols, 40)

    centres = []
    for r in range(rows):
        for c in range(cols):
            lat = box.south + (r + 0.5) * (box.north - box.south) / rows
            lng = box.west + (c + 0.5) * (box.east - box.west) / cols
            centres.append((lat, lng))
    return centres


class GeoTarget:
    """Resolves the user's geographic input into search centres plus a filter."""

    def __init__(
        self,
        bounding_box: list | None = None,
        center_lat: float | None = None,
        center_lng: float | None = None,
        radius_km: float | None = None,
        area_name: str | None = None,
        tile_km: float | None = None,
    ) -> None:
        self.box: BoundingBox | None = None
        self.center: tuple[float, float] | None = None
        self.radius_km: float | None = None
        self.description = "none"

        if bounding_box:
            if len(bounding_box) != 4:
                raise ValueError(
                    "boundingBox must be [south, west, north, east] -- got "
                    f"{len(bounding_box)} value(s)"
                )
            south, west, north, east = (float(v) for v in bounding_box)
            if south > north:
                raise ValueError("boundingBox south must be <= north")
            self.box = BoundingBox(south, west, north, east)
            self.description = f"bbox({south},{west},{north},{east})"
        elif center_lat is not None and center_lng is not None and radius_km:
            self.center = (float(center_lat), float(center_lng))
            self.radius_km = float(radius_km)
            self.box = bbox_from_radius(self.center[0], self.center[1], self.radius_km)
            self.description = f"radius({center_lat},{center_lng},{radius_km}km)"
        elif area_name:
            key = area_name.strip().lower()
            if key not in NAMED_AREAS:
                raise ValueError(
                    f"unknown area {area_name!r}. Known areas: "
                    f"{', '.join(sorted(NAMED_AREAS))}. For anywhere else, pass an "
                    "explicit boundingBox or a centre point with a radius."
                )
            self.box = BoundingBox(*NAMED_AREAS[key])
            self.description = f"area({key})"

        self.tile_km = tile_km

    @property
    def active(self) -> bool:
        return self.box is not None

    def search_centres(self) -> list[tuple[float, float]]:
        """Where to point Google. Empty when no area was requested."""
        if self.box is None:
            return []
        tile = self.tile_km or self._default_tile_km()
        return tile_bbox(self.box, tile)

    def _default_tile_km(self) -> float:
        """Keep small areas to one request and split large ones sensibly."""
        span = max(self.box.width_km, self.box.height_km) if self.box else 0
        if span <= 8:
            return max(span, 1.0)
        if span <= 40:
            return 8.0
        if span <= 200:
            return 25.0
        return 100.0

    def viewport_distance(self) -> float:
        """The !1d span in metres for a single search centre."""
        tile = self.tile_km or (self._default_tile_km() if self.box else 20.0)
        return max(tile * 1000.0, 1000.0)

    def matches(self, lat: float | None, lng: float | None) -> bool | None:
        """True/False when decidable, None when the lead has no coordinates."""
        if not self.active:
            return True
        if lat is None or lng is None:
            return None
        if self.center is not None and self.radius_km is not None:
            return haversine_km(self.center[0], self.center[1], lat, lng) <= self.radius_km
        assert self.box is not None
        return self.box.contains(lat, lng)
