"""Geographic filtering of input places.

Scope, stated plainly: Google exposes no HTTP-only place-search surface any
more, so this actor cannot *discover* places inside an area. What it can do is
filter the places you supply. A place therefore needs coordinates before any
geo filter can apply to it, and the only reliable HTTP-only source of a place's
coordinates is the Maps URL itself (the !3d/!4d pair, or @lat,lng).

Google's place resolver returns a fixed world-view viewport for every place, so
it cannot supply coordinates -- that was verified, not assumed.

Places with no coordinates are never silently dropped: they are either kept or
emitted as a skip record according to `onMissingCoordinates`, so a run never
loses inputs without saying so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088

# Rough bounding boxes for the city/country shorthand, as
# (south, west, north, east). Deliberately a small, honest list: a real
# geocoder is a network dependency this actor does not need. Anything not in
# here should be expressed as an explicit bounding box.
NAMED_AREAS: dict[str, tuple[float, float, float, float]] = {
    "jakarta": (-6.4, 106.6, -6.0, 107.0),
    "bandung": (-7.0, 107.5, -6.8, 107.8),
    "surabaya": (-7.4, 112.6, -7.1, 112.9),
    "bali": (-8.9, 114.4, -8.0, 115.8),
    "singapore": (1.13, 103.6, 1.48, 104.1),
    "kuala lumpur": (2.9, 101.5, 3.3, 101.8),
    "bangkok": (13.5, 100.3, 14.0, 100.9),
    "london": (51.28, -0.51, 51.70, 0.33),
    "paris": (48.80, 2.22, 48.91, 2.47),
    "new york": (40.48, -74.27, 40.92, -73.68),
    "san francisco": (37.70, -122.52, 37.84, -122.35),
    "seattle": (47.48, -122.44, 47.74, -122.22),
    "sydney": (-34.0, 150.9, -33.7, 151.35),
    "tokyo": (35.5, 139.5, 35.85, 139.95),
    "dubai": (24.9, 54.9, 25.4, 55.5),
    "indonesia": (-11.0, 95.0, 6.0, 141.0),
    "malaysia": (0.8, 99.6, 7.4, 119.3),
    "singapore country": (1.13, 103.6, 1.48, 104.1),
    "thailand": (5.6, 97.3, 20.5, 105.6),
    "united kingdom": (49.9, -8.6, 60.9, 1.8),
    "france": (41.3, -5.1, 51.1, 9.6),
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
        # Box straddles the antimeridian.
        return lng >= self.west or lng <= self.east


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class GeoFilter:
    """Bounding box, radius-around-a-point, or named area. At most one applies."""

    def __init__(
        self,
        bounding_box: list | None = None,
        center_lat: float | None = None,
        center_lng: float | None = None,
        radius_km: float | None = None,
        area_name: str | None = None,
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
            self.description = f"radius({center_lat},{center_lng},{radius_km}km)"
        elif area_name:
            key = area_name.strip().lower()
            if key not in NAMED_AREAS:
                raise ValueError(
                    f"unknown area {area_name!r}. Known areas: "
                    f"{', '.join(sorted(NAMED_AREAS))}. For anywhere else, pass an "
                    "explicit boundingBox."
                )
            self.box = BoundingBox(*NAMED_AREAS[key])
            self.description = f"area({key})"

    @property
    def active(self) -> bool:
        return self.box is not None or self.center is not None

    def matches(self, lat: float | None, lng: float | None) -> bool | None:
        """True/False when decidable, None when the place has no coordinates."""
        if not self.active:
            return True
        if lat is None or lng is None:
            return None
        if self.box is not None:
            return self.box.contains(lat, lng)
        assert self.center is not None and self.radius_km is not None
        return haversine_km(self.center[0], self.center[1], lat, lng) <= self.radius_km
