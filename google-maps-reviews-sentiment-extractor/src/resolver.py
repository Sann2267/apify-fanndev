"""Turn whatever the user supplied into a Google Feature ID (FID).

Accepted inputs, all verified live:
  * feature id      0x47e66e2964e34e2d:0x8ddca9ee380ef7e0
  * place id        ChIJLU7jZClu5kcR4PcOOO6p3I0
  * cid (decimal)   10222232094831998944
  * any Google Maps URL that carries one of the above
  * maps.app.goo.gl / goo.gl/maps short links (resolved by redirect)

Free-text search is deliberately NOT supported: Google closed every HTTP-only
place-search surface (see CRAWLING_METHOD.md). Callers get a clear error rather
than a silently wrong place.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

from src.client import MapsClient
from src.constants import CAPTCHA_MARKERS, CONSENT_MARKERS, PLACE_RESOLVER_URL

FID_RE = re.compile(r"0x[0-9a-fA-F]{6,16}:0x[0-9a-fA-F]{6,16}")
PLACE_ID_RE = re.compile(r"^(ChIJ|Ei|Gh|EicR|EhI)[A-Za-z0-9_\-]{10,}$")
CID_RE = re.compile(r"^\d{10,26}$")
# /maps/place/Name/@48.8583701,2.2944813,17z/...
AT_COORDS_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")
# ...!8m2!3d48.8583701!4d2.2944813
D_COORDS_RE = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")
SHORT_LINK_HOSTS = {"maps.app.goo.gl", "goo.gl", "maps.goo.gl"}
# /maps/place/Eiffel+Tower/data=... -- the only place a name is still available.
URL_NAME_RE = re.compile(r"/maps/place/([^/@?]+)")


@dataclass
class ResolvedPlace:
    feature_id: str
    raw_input: str
    source: str
    name: str | None = None
    place_id: str | None = None
    cid: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def maps_url(self) -> str:
        return f"https://www.google.com/maps/place/data=!4m2!3m1!1s{self.feature_id}?hl=en"


class ResolutionError(ValueError):
    """The input could not be turned into a feature id."""


def cid_from_fid(feature_id: str) -> str | None:
    """Second half of a feature id is the CID, as an unsigned decimal."""
    try:
        return str(int(feature_id.split(":")[1], 16))
    except (IndexError, ValueError):
        return None


def fid_from_cid(cid: str) -> str | None:
    """Build a feature id from a CID alone.

    Only the second half of a feature id identifies the place; the first half
    can be zero. Google's own review permalinks use exactly this form
    (!1s0x0:0x...), and the reviews endpoint returns identical results for
    '0x0:<cid hex>' as for the full feature id -- verified against live data.
    This makes CID input a pure local computation, with no lookup request.
    """
    try:
        return f"0x0:0x{int(cid):x}"
    except (TypeError, ValueError):
        return None


def _coords_from_url(url: str) -> tuple[float | None, float | None]:
    """Pull place coordinates out of a Maps URL.

    Prefer the !3d/!4d pair (the place's own point) over @lat,lng (the map
    viewport centre, which can sit some distance from the place).
    """
    match = D_COORDS_RE.search(url) or AT_COORDS_RE.search(url)
    if not match:
        return None, None
    try:
        return float(match.group(1)), float(match.group(2))
    except ValueError:
        return None, None


def _name_from_url(url: str) -> str | None:
    """Read the place name out of a Maps URL path.

    Google's resolver no longer returns a place name for any URL form, so a
    name pasted into the URL path is the only source left. Identifier-only
    segments (data=..., place_id:...) are not names.
    """
    match = URL_NAME_RE.search(url)
    if not match:
        return None
    segment = match.group(1)
    if segment.startswith("data=") or ":" in segment or segment.startswith("@"):
        return None
    name = unquote(segment).replace("+", " ").strip()
    return name or None


def _extract_from_url(url: str) -> dict:
    """Best-effort scrape of identifiers out of a Maps URL without a network call."""
    found: dict = {}
    decoded = unquote(url)
    name = _name_from_url(url)
    if name:
        found["name"] = name

    fid = FID_RE.search(decoded)
    if fid:
        found["feature_id"] = fid.group(0).lower()

    query = parse_qs(urlparse(decoded).query)
    if "cid" in query and CID_RE.match(query["cid"][0]):
        found["cid"] = query["cid"][0]

    # ?q=place_id:ChIJ... and the bare placeid/place_id params
    for key in ("q", "placeid", "place_id", "query_place_id"):
        for value in query.get(key, []):
            candidate = value.split("place_id:")[-1].strip()
            if PLACE_ID_RE.match(candidate):
                found["place_id"] = candidate
    match = re.search(r"place_id[:=]([A-Za-z0-9_\-]{10,})", decoded)
    if match and "place_id" not in found:
        found["place_id"] = match.group(1)
    # !1s0x..:0x.. is covered by FID_RE above; !19sChIJ... carries a place id
    match = re.search(r"!19s(ChIJ[A-Za-z0-9_\-]{10,})", decoded)
    if match:
        found.setdefault("place_id", match.group(1))

    lat, lng = _coords_from_url(decoded)
    if lat is not None:
        found["latitude"], found["longitude"] = lat, lng
    return found


def _parse_resolver_blob(html: str) -> tuple[str | None, str | None]:
    """Read the FID and place name out of the resolver page's embedded blob.

    The page ships an XSSI-prefixed array inside APP_INITIALIZATION_STATE whose
    first element is [feature_id, place_name, viewport]. That viewport is always
    Google's default world view, never the place's own coordinates, so it is
    deliberately ignored here.
    """
    match = re.search(r"window\.APP_INITIALIZATION_STATE\s*=\s*(\[.+?\]);", html, re.DOTALL)
    blob = None
    if match:
        try:
            state = json.loads(match.group(1))
            for element in state[3] or []:
                if isinstance(element, str) and element.startswith(")]}"):
                    blob = element
                    break
        except (ValueError, IndexError, TypeError):
            blob = None

    if blob:
        try:
            parsed = json.loads(blob[blob.index("\n") + 1:])
            head = parsed[0]
            if isinstance(head, list) and len(head) > 1:
                fid = head[0] if isinstance(head[0], str) else None
                name = head[1] if isinstance(head[1], str) else None
                if fid and FID_RE.match(fid):
                    return fid.lower(), name
        except (ValueError, IndexError, TypeError):
            pass

    found = FID_RE.search(blob or html)
    return (found.group(0).lower() if found else None), None


async def resolve(raw: str, client: MapsClient) -> ResolvedPlace:
    """Resolve one user-supplied identifier to a ResolvedPlace."""
    value = (raw or "").strip()
    if not value:
        raise ResolutionError("empty input")

    # 1. Bare feature id -- nothing to look up.
    if FID_RE.fullmatch(value):
        fid = value.lower()
        return ResolvedPlace(fid, raw, "input-feature-id", cid=cid_from_fid(fid))

    place_id: str | None = None
    cid: str | None = None
    url_name: str | None = None
    lat = lng = None

    if value.startswith("http://") or value.startswith("https://"):
        host = (urlparse(value).hostname or "").lower()
        if host in SHORT_LINK_HOSTS:
            # Short links carry no identifier; follow the redirect to the real URL.
            try:
                await client.ensure_warm()
                session = client.session
                resp = await session.get(
                    value, headers={"accept": "text/html"}, allow_redirects=True
                )
                value = str(resp.url)
            except Exception as exc:
                raise ResolutionError(f"could not follow short link: {exc}") from exc

        found = _extract_from_url(value)
        lat, lng = found.get("latitude"), found.get("longitude")
        if found.get("feature_id"):
            fid = found["feature_id"]
            return ResolvedPlace(
                fid, raw, "url-feature-id", name=found.get("name"),
                place_id=found.get("place_id"), cid=cid_from_fid(fid),
                latitude=lat, longitude=lng,
            )
        place_id = found.get("place_id")
        cid = found.get("cid")
        url_name = found.get("name")
        if not place_id and not cid:
            raise ResolutionError(
                "Maps URL carries no place identifier. Open the place in Google "
                "Maps and copy the URL from the address bar (it should contain "
                "'/data=!...!1s0x...' or '?cid='), or supply a Place ID."
            )
    elif PLACE_ID_RE.match(value):
        place_id = value
    elif CID_RE.match(value):
        cid = value
    else:
        raise ResolutionError(
            f"unrecognised input {value!r}. Supply a Google Maps URL, a Place ID "
            "(ChIJ...), a CID, or a feature id (0x...:0x...). Free-text place "
            "search is not supported by this actor."
        )

    # 2. A CID needs no lookup -- it *is* the second half of the feature id.
    if cid and not place_id:
        fid = fid_from_cid(cid)
        if not fid:
            raise ResolutionError(f"invalid CID {cid!r}")
        return ResolvedPlace(
            fid, raw, "cid-derived", name=url_name, cid=cid,
            latitude=lat, longitude=lng,
        )

    # 3. Otherwise ask Google's resolver page to turn the Place ID into a FID.
    lookup = f"place_id:{place_id}"
    html = await client.get_html(
        PLACE_RESOLVER_URL,
        params={"q": lookup, "hl": client.language, "gl": client.region},
    )
    fid, name = _parse_resolver_blob(html)
    if not fid:
        # Distinguish "Google refused to answer" from "Google says no such place".
        # Both produce a FID-less page, but they need opposite responses from the
        # operator, so reporting them identically sends people hunting the wrong bug.
        lowered = html.lower()
        if any(marker.lower() in lowered for marker in CAPTCHA_MARKERS):
            raise ResolutionError(
                f"Google served a CAPTCHA / 'unusual traffic' page instead of resolving "
                f"{lookup!r} ({len(html)} bytes). The exit IP is rate-limited -- retry "
                "with a different proxy session, or without a proxy."
            )
        if any(marker.lower() in lowered for marker in CONSENT_MARKERS):
            raise ResolutionError(
                f"Google served a consent interstitial instead of resolving {lookup!r} "
                f"({len(html)} bytes). This usually means the exit IP is in a region "
                "requiring GDPR consent."
            )
        raise ResolutionError(
            f"Google did not resolve {lookup!r} to a place (got a normal page of "
            f"{len(html)} bytes with no feature id). Check the identifier is current -- "
            "Place IDs are retired when a business closes or merges."
        )
    return ResolvedPlace(
        fid, raw, "resolver-place-id",
        name=name or url_name, place_id=place_id, cid=cid or cid_from_fid(fid),
        latitude=lat, longitude=lng,
    )
