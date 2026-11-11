---
name: bbox-quadtree
description: "Recursively subdivide a geographic bounding box into a quadtree so an area-paginated API's per-bbox cap doesn't drop results in dense regions. Use when scraping Zillow, Google Maps places, Realtor, or Yelp and one bbox hits its result limit."
---

# Geospatial Bounding-Box Quadtree Subdivision

> **APIs that paginate by geographic area (Zillow listings, Google Maps places, Realtor, Yelp) cap results per bbox (e.g. 500 map markers, 800 list items).** A naive scrape misses dense areas. The quadtree pattern recursively subdivides until each tile fits under the cap.

## Problem

Real-estate and points-of-interest APIs return results within a bounding box with a hard cap:

- Zillow: 800 list / 500 map markers
- Google Maps places: ~60 per call (varies)
- Realtor: ~2000-2200 cumulative across pages

In dense areas (Manhattan, downtown LA), the cap silently truncates. You don't know how many listings you missed.

## Solution: recursive bbox quadtree

If a tile returns `total > ceiling`, split it into 4 equal sub-tiles and recurse. Stop at a minimum span to avoid infinite recursion in absurdly dense spots.

### Core split function

```python
from dataclasses import dataclass

@dataclass
class BBox:
    west:  float   # min lon
    east:  float   # max lon
    south: float   # min lat
    north: float   # max lat
    
    @property
    def span_lat(self): return self.north - self.south
    @property
    def span_lon(self): return self.east - self.west


def split_bbox(b: BBox) -> list[BBox]:
    """4-way midpoint split: NW, NE, SW, SE."""
    mid_lat = (b.south + b.north) / 2
    mid_lon = (b.west + b.east) / 2
    return [
        BBox(b.west, mid_lon, mid_lat, b.north),  # NW
        BBox(mid_lon, b.east, mid_lat, b.north),  # NE
        BBox(b.west, mid_lon, b.south, mid_lat),  # SW
        BBox(mid_lon, b.east, b.south, mid_lat),  # SE
    ]
```

### Driver — recursive scrape with cap detection

```python
MIN_TILE_SPAN_DEG = 0.005    # ~500m at the equator
CEILING_TOTAL    = 800       # Zillow's list cap
CEILING_MAP      = 500       # Zillow's map-marker cap

async def scrape_bbox_recursive(bbox: BBox, fetch_fn, emit_fn):
    """
    fetch_fn(bbox) -> (results: list, total_advertised: int)
    emit_fn(record) -> push to dataset
    """
    # 1. Try this tile
    results, total = await fetch_fn(bbox)
    
    # 2. Did we get capped? Sub-divide
    if total > CEILING_TOTAL and bbox.span_lat > MIN_TILE_SPAN_DEG:
        for sub in split_bbox(bbox):
            await scrape_bbox_recursive(sub, fetch_fn, emit_fn)
        return
    
    # 3. Not capped — emit results
    for r in results:
        await emit_fn(r)
```

### Variant: cap detection via map marker count

Some APIs return both `listResultsCount` and `mapResultsCount`. When map markers > 500, split even if list count is OK (map count is a more honest density signal).

```python
def needs_subdivision(meta: dict) -> bool:
    return (
        meta.get("listResultsCount", 0) > CEILING_TOTAL
        or meta.get("mapResultsCount", 0) > CEILING_MAP
    )
```

### Pattern: dedup across overlapping tiles

Sub-tiles share edges. Listings on the boundary appear in 2 tiles. Dedup by primary ID:

```python
class DedupSet:
    def __init__(self):
        self._seen: set[str] = set()
    
    def mark_and_check(self, item_id: str) -> bool:
        """Returns True if newly seen, False if duplicate."""
        if item_id in self._seen:
            return False
        self._seen.add(item_id)
        return True

dedup = DedupSet()

async def emit_unique(record):
    if dedup.mark_and_check(record["id"]):
        await Actor.push_data(record)
```

### Min-span calibration

| Use case | MIN_TILE_SPAN_DEG | Real-world equivalent |
| --- | --- | --- |
| Real-estate listings | 0.005 (~500m) | A few city blocks |
| Restaurants (Yelp/Google) | 0.002 (~200m) | One city block |
| Gas stations / POIs | 0.01 (~1km) | Neighborhood |
| Properties for sale (rural) | 0.05 (~5km) | Small town |

**Hitting the min-span and STILL being capped** is a real-world signal: emit a warning record (`_warning: "min_span_reached_capped"`) so consumers know that tile is undersampled.

## Pattern: depth budget

In ultra-dense areas (a single high-rise has 100+ units), recursion can blow the stack. Cap depth instead of using only span:

```python
MAX_DEPTH = 6   # 4^6 = 4096 leaf tiles max from one input bbox

async def scrape_bbox_recursive(bbox, fetch_fn, emit_fn, depth=0):
    if depth > MAX_DEPTH:
        await emit_warning(bbox, "max_depth_reached")
        results, _ = await fetch_fn(bbox)
        for r in results:
            await emit_fn(r)
        return
    ...
```

## Pattern: concurrent sub-tile fan-out

Sub-tiles are independent — fetch them concurrently with bounded semaphore:

```python
async def scrape_bbox_recursive_concurrent(bbox, fetch_fn, emit_fn, sem, depth=0):
    async with sem:
        results, total = await fetch_fn(bbox)
    
    if total > CEILING_TOTAL and bbox.span_lat > MIN_TILE_SPAN_DEG:
        subs = split_bbox(bbox)
        await asyncio.gather(*(
            scrape_bbox_recursive_concurrent(s, fetch_fn, emit_fn, sem, depth + 1)
            for s in subs
        ))
        return
    
    for r in results:
        await emit_fn(r)
```

## Caveats

- **Coordinate system gotcha:** west/east are longitude (X-axis), south/north are latitude (Y-axis). Don't swap.
- **Don't subdivide when API has page-based pagination AND high enough cap.** If page=1..N gives you everything, paginate; only quadtree when even page=N is capped.
- **Quadtree multiplies request count.** A single dense bbox can fan out to 64+ leaves. Plan proxy budget accordingly.
- **Tile dedup must happen at top level, not per sub-tile.** Per-tile dedup misses overlaps.
- **Don't recurse on transient failures.** If a tile returns 403 (WAF block), subdividing won't help — the next tile in the same proxy session faces the same block. Handle WAF retry separately from quadtree logic.
- **Track quadtree as a label-router state.** When using Crawlee, label requests as `SEARCH` → `BBOX_SPLIT` → `DETAIL` so the trace is auditable.

## Where used

- Real-Estate Zillow scraper (40/page, 800 list cap + 500 map cap → recursive subdivision)
- `split_bbox()` 4-way midpoint split with `MIN_TILE_SPAN_DEG = 0.005°`
- Label-router (`SEARCH / DETAIL / BBOX_SPLIT`) — Crawlee Python labels

## See also
- [`stacks/python-apify-actor.md`](../../stacks/python-apify-actor.md) (label routing in Crawlee)
- [`skills/session-pool-rotation.md`](../session-pool-rotation/SKILL.md) (per-region session keying)
