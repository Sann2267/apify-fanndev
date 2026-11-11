"""Offline checks: place parsing, geo targeting, enrichment, exporters."""
import json
import sys

from src.enrich import extract_contacts, find_contact_page, _valid_email
from src.exporters import flatten, to_csv, to_json, to_ndjson, to_xlsx
from src.geo import BoundingBox, GeoTarget, bbox_from_radius, haversine_km, tile_bbox
from src.places import (_parse_hours, _parse_phone, _parse_rating, _parse_website,
                        extract_search_places, parse_place)

fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  <- {extra}"))
    if not cond:
        fails.append(name)


print("== rating parsing ==")
full = [None, None, None, ["https://x/reviews", "546 reviews", None, "t"], None, None, None, 4.9, 546]
check("full block", _parse_rating(full) ==
      {"rating": 4.9, "reviewsCount": 546, "reviewsUrl": "https://x/reviews"}, _parse_rating(full))
# A whole-number rating arrives as an int -- the bug that made every count null.
check("int rating", _parse_rating([None]*7 + [5]) ==
      {"rating": 5.0, "reviewsCount": None, "reviewsUrl": None}, _parse_rating([None]*7 + [5]))
check("locale count", _parse_rating(
    [None, None, None, ["https://x", "1.139 reviews"], None, None, None, 4.9])["reviewsCount"] == 1139)
check("no block", _parse_rating(None)["rating"] is None)
check("rating out of range ignored", _parse_rating([None]*7 + [99])["rating"] is None)
check("bool not a rating", _parse_rating([None]*7 + [True])["rating"] is None)

print("== phone / website ==")
phone = [["+61 2 8296 7351", [["(02) 8296 7351", 1], ["+61 2 8296 7351", 2]], None, "+61282967351"]]
p = _parse_phone(phone)
check("phone pretty", p["phone"] == "+61 2 8296 7351", p)
check("phone e164", p["phoneE164"] == "+61282967351", p)
check("phone local", p["phoneLocal"] == "(02) 8296 7351", p)
check("phone none-safe", _parse_phone(None)["phone"] is None)
w = _parse_website(["https://ex.com/?utm=1", "ex.com"])
check("website", w["website"] == "https://ex.com/?utm=1" and w["websiteDomain"] == "ex.com", w)
check("website none-safe", _parse_website(None)["website"] is None)

print("== hours ==")
hours_raw = [[["Wednesday", 3, [2026, 9, 16], [["10.00 am–8.00 pm", [[10], [20]]]], 0, 1],
              ["Thursday", 4, [2026, 9, 17], [["Closed"]], 0, 1]]]
h = _parse_hours(hours_raw)
check("hours days", [d["day"] for d in h["openingHours"]] == ["Wednesday", "Thursday"], h)
check("hours text", h["openingHours"][0]["hours"] == ["10.00 am–8.00 pm"], h)
check("hours none-safe", _parse_hours(None)["openingHours"] == [])

print("== parse_place ==")
rec = [None] * 260
rec[10] = "0x1:0x2"; rec[11] = "Acme Dental"; rec[13] = ["Dentist", "Clinic"]
rec[39] = "1 Main St"; rec[9] = [None, None, -6.2, 106.8]; rec[78] = "ChIJabc"
rec[4] = [None]*7 + [4.5, 30]
lead = parse_place(rec)
check("name/cat", lead["name"] == "Acme Dental" and lead["primaryCategory"] == "Dentist", lead)
check("coords", (lead["latitude"], lead["longitude"]) == (-6.2, 106.8), lead)
check("rating", lead["rating"] == 4.5 and lead["reviewsCount"] == 30, lead)
check("enrichment defaults seeded",
      lead["emails"] == [] and lead["enrichmentStatus"] == "no_website", lead)
check("hours completeness flag", lead["openingHoursComplete"] is False)
check("rejects non-list", parse_place("x") is None)
check("rejects missing name", parse_place([None]*20) is None)
check("search extract tolerates junk", extract_search_places({"a": 1}) == [])
check("search extract empty", extract_search_places(None) == [])

print("== geo ==")
box = GeoTarget(bounding_box=[48.0, 2.0, 49.0, 3.0])
check("bbox inside", box.matches(48.5, 2.5) is True)
check("bbox outside", box.matches(40.0, -73.0) is False)
check("bbox no coords", box.matches(None, None) is None)
check("bbox has centres", len(box.search_centres()) >= 1)
rad = GeoTarget(center_lat=48.8583, center_lng=2.2944, radius_km=5)
check("radius inside", rad.matches(48.86, 2.30) is True)
check("radius outside", rad.matches(48.99, 2.90) is False)
check("named area", GeoTarget(area_name="jakarta").matches(-6.2, 106.8) is True)
check("inactive passes", GeoTarget().matches(None, None) is True)
check("inactive has no centres", GeoTarget().search_centres() == [])
try:
    GeoTarget(bounding_box=[1, 2]); check("bad bbox raises", False)
except ValueError:
    check("bad bbox raises", True)
try:
    GeoTarget(area_name="atlantis"); check("unknown area raises", False)
except ValueError:
    check("unknown area raises", True)
# Eiffel Tower -> central London is ~341 km.
check("haversine", 335 < haversine_km(48.8583, 2.2944, 51.5074, -0.1278) < 350)
check("haversine zero", haversine_km(1.0, 2.0, 1.0, 2.0) == 0.0)
b = bbox_from_radius(-6.2, 106.8, 10)
check("radius bbox contains centre", b.contains(-6.2, 106.8))
tiles = tile_bbox(BoundingBox(-6.4, 106.6, -6.0, 107.0), 8)
check("tiling covers area", len(tiles) >= 4, len(tiles))
check("tiling bounded", len(tile_bbox(BoundingBox(-40, 100, 40, 180), 0.5)) <= 1600)
check("big area larger tiles", GeoTarget(area_name="indonesia")._default_tile_km() >= 25)

print("== enrichment ==")
html = """<a href="https://facebook.com/sharer/sharer.php?u=x">share</a>
<a href="https://www.facebook.com/acgsydney">fb</a>
<a href="https://twitter.com/share?text=x">tw</a>
<a href="https://instagram.com/australiancruisegroup/">ig</a>
<a href="https://wa.me/6281234567890">wa</a>
<a href="mailto:book@acg.com.au">mail</a> logo@2x.png sprite@3x.png
<a href="/contact-us">Contact</a><a href="/about">About</a>"""
c = extract_contacts(html)
check("email found", c["emails"] == ["book@acg.com.au"], c["emails"])
check("image @2x rejected", not any("@2x" in e for e in c["emails"]))
# Share widgets must not become "accounts" -- the main noise source.
check("facebook widget filtered", c["socialProfiles"]["facebook"] == ["acgsydney"], c["socialProfiles"])
check("twitter widget filtered", "twitter" not in c["socialProfiles"], c["socialProfiles"])
check("instagram", c["socialProfiles"]["instagram"] == ["australiancruisegroup"])
check("whatsapp", c["socialProfiles"]["whatsapp"] == ["6281234567890"])
check("empty html safe", extract_contacts("")["emails"] == [])
check("reject placeholder", not _valid_email("you@example.com"))
check("accept real", _valid_email("hi@clinic.co.id"))
cp = find_contact_page(html, "https://acg.com.au/")
check("prefers contact over about", cp == "https://acg.com.au/contact-us", cp)
check("offsite link ignored",
      find_contact_page('<a href="https://other.com/contact">x</a>', "https://acg.com.au/") is None)
check("no contact link", find_contact_page("<p>none</p>", "https://acg.com.au/") is None)

print("== exporters ==")
rows = [{"recordType": "LEAD", "name": "A", "phone": "123", "emails": ["a@b.c"],
         "socialProfiles": {"instagram": ["x"]}, "openingHours": [{"day": "Mon"}],
         "rating": 4.5}]
csv_bytes = to_csv(rows)
head = csv_bytes.decode("utf-8-sig").splitlines()[0]
check("csv BOM", csv_bytes.startswith(b"\xef\xbb\xbf"))
check("csv lead-first columns", head.split(",")[0] == "name", head)
check("csv flattens socials", "socialProfiles.instagram" in head, head)
check("csv drops bulky", "openingHours" not in head, head)
check("ndjson", len(to_ndjson(rows).decode().strip().splitlines()) == 1)
check("json", json.loads(to_json(rows).decode())[0]["name"] == "A")
x = to_xlsx(rows)
check("xlsx", x is not None and x[:2] == b"PK")
check("csv empty safe", to_csv([]) == b"")
check("flatten", flatten({"a": {"b": 1}}) == {"a.b": 1})

print()
if fails:
    print(f"{len(fails)} FAILED: {fails}")
    sys.exit(1)
print("ALL CHECKS PASSED")
