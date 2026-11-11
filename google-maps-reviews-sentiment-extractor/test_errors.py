"""Unit-ish checks for resolver parsing, geo filters, sentiment and exporters."""
import asyncio, json, sys

from src.geo import GeoFilter, haversine_km
from src.sentiment import score_review, summarise
from src.exporters import to_csv, to_ndjson, to_json, to_xlsx, flatten
from src.resolver import _extract_from_url, _name_from_url, cid_from_fid, FID_RE
from src.extractor import clean_text, unwrap_response, parse_review
from src.client import UnexpectedShape

fails = []
def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  <- {extra}"))
    if not cond: fails.append(name)

print("== URL parsing ==")
u1 = "https://www.google.com/maps/place/Eiffel+Tower/@48.8583701,2.2944813,17z/data=!3m1!4b1!4m6!3m5!1s0x47e66e2964e34e2d:0x8ddca9ee380ef7e0!8m2!3d48.8583701!4d2.2944813"
g1 = _extract_from_url(u1)
check("fid from data= url", g1.get("feature_id") == "0x47e66e2964e34e2d:0x8ddca9ee380ef7e0", g1)
check("coords prefer !3d/!4d", (g1.get("latitude"), g1.get("longitude")) == (48.8583701, 2.2944813), g1)
check("name from url path", g1.get("name") == "Eiffel Tower", g1)
check("name skips data= segment", _name_from_url("https://www.google.com/maps/place/data=!4m2!3m1!1s0x1:0x2") is None)
g2 = _extract_from_url("https://www.google.com/maps?cid=10222232094831998944")
check("cid from url", g2.get("cid") == "10222232094831998944", g2)
g3 = _extract_from_url("https://www.google.com/maps/place/?q=place_id:ChIJLU7jZClu5kcR4PcOOO6p3I0")
check("place_id from url", g3.get("place_id") == "ChIJLU7jZClu5kcR4PcOOO6p3I0", g3)
check("cid_from_fid", cid_from_fid("0x47e66e2964e34e2d:0x8ddca9ee380ef7e0") == "10222232094831998944")

print("== geo ==")
box = GeoFilter(bounding_box=[48.0, 2.0, 49.0, 3.0])
check("bbox inside", box.matches(48.8583, 2.2944) is True)
check("bbox outside", box.matches(40.0, -73.0) is False)
check("bbox undecidable w/o coords", box.matches(None, None) is None)
rad = GeoFilter(center_lat=48.8583, center_lng=2.2944, radius_km=5)
check("radius inside", rad.matches(48.86, 2.30) is True)
check("radius outside", rad.matches(48.99, 2.90) is False)
check("named area", GeoFilter(area_name="jakarta").matches(-6.2, 106.8) is True)
check("inactive filter passes all", GeoFilter().matches(None, None) is True)
try:
    GeoFilter(bounding_box=[1, 2]); check("bad bbox raises", False)
except ValueError: check("bad bbox raises", True)
try:
    GeoFilter(area_name="atlantis"); check("unknown area raises", False)
except ValueError: check("unknown area raises", True)
# Eiffel Tower -> central London great-circle is ~341 km.
check("haversine sane", 335 < haversine_km(48.8583, 2.2944, 51.5074, -0.1278) < 350,
      haversine_km(48.8583, 2.2944, 51.5074, -0.1278))
check("haversine zero", haversine_km(1.0, 2.0, 1.0, 2.0) == 0.0)

print("== sentiment ==")
s = score_review("Absolutely wonderful, the staff were amazing!", 5, "en")
check("positive", s.label == "positive" and s.method == "text+rating", s)
s = score_review("Terrible service, rude staff, never coming back.", 1, "en")
check("negative", s.label == "negative", s)
s = score_review(None, 3, None)
check("rating-only neutral", s.label == "neutral" and s.method == "rating-only", s)
s = score_review(None, None, None)
check("no signal -> none", s.method == "none" and s.label == "neutral", s)
s = score_review("Чудовий ресторан", 5, "uk", "Wonderful restaurant")
check("translated path", s.method == "translated+rating", s)
s = score_review("Чудовий ресторан", 5, "uk", None)
check("non-en w/o translation falls back", s.method == "rating-only", s)
sarcasm = score_review(
    "Love surprises? This company will cancel your plans at the last minute for "
    "someone with more money. Highly thrilling experience.", 1, "en")
check("sarcasm: rating overrides positive text",
      sarcasm.label == "negative" and sarcasm.ratingTextConflict is True, sarcasm)
check("no conflict on agreement",
      score_review("Wonderful!", 5, "en").ratingTextConflict is False)
check("no conflict on mid rating",
      score_review("Awful awful awful terrible", 3, "en").ratingTextConflict is False)

print("== summarise ==")
recs = [
  {"sentiment": {"label": "positive", "score": 0.8}, "rating": 5, "text": "a", "ownerResponse": {"text": "x"}, "likesCount": 2, "photos": [1]},
  {"sentiment": {"label": "negative", "score": -0.6}, "rating": 1, "text": "b", "ownerResponse": None, "likesCount": 0, "photos": []},
]
sm = summarise(recs)
check("summary counts", sm["sentimentCounts"] == {"positive":1,"neutral":0,"negative":1}, sm)
check("summary conflict counter", sm["ratingTextConflicts"] == 0, sm)
check("owner rate", sm["ownerResponseRatePercent"] == 50.0, sm)
check("avg rating", sm["averageRating"] == 3.0, sm)
check("histogram", sm["ratingHistogram"]["5"] == 1 and sm["ratingHistogram"]["1"] == 1, sm)
check("empty summarise safe", summarise([])["reviewsAnalysed"] == 0)

print("== extractor ==")
check("clean <br>", clean_text("a<br><br>b") == "a\n\nb", clean_text("a<br><br>b"))
check("clean entities", clean_text("Tom &amp; Jerry &#39;x&#39;") == "Tom & Jerry 'x'")
check("clean passthrough None", clean_text(None) is None)
check("unwrap empty payload", unwrap_response(None) == ([], None))
check("unwrap short envelope", unwrap_response([1]) == ([], None))
try:
    unwrap_response({"a": 1}); check("unwrap bad root raises", False)
except UnexpectedShape: check("unwrap bad root raises", True)
check("parse_review rejects non-list", parse_review("x") is None)
check("parse_review needs id", parse_review([None]*10) is None)

print("== exporters ==")
rows = [{"recordType":"REVIEW","reviewId":"a","rating":5,"text":"hi <b>there</b>",
         "sentiment":{"label":"positive","score":0.8},"photos":[{"url":"u"}],"reviewer":{"name":"N"}}]
csv_bytes = to_csv(rows)
check("csv has BOM", csv_bytes.startswith(b"\xef\xbb\xbf"))
head = csv_bytes.decode("utf-8-sig").splitlines()[0]
check("csv flattens nested", "sentiment.label" in head and "reviewer.name" in head, head)
check("csv drops bulky cols", "photos" not in head, head)
check("ndjson lines", len(to_ndjson(rows).decode().strip().splitlines()) == 1)
check("json valid", json.loads(to_json(rows).decode())[0]["reviewId"] == "a")
x = to_xlsx(rows)
check("xlsx built", x is not None and x[:2] == b"PK", type(x))
check("csv empty safe", to_csv([]) == b"")
check("flatten nested", flatten({"a":{"b":1}}) == {"a.b":1})

print()
if fails:
    print(f"{len(fails)} FAILED: {fails}"); sys.exit(1)
print("ALL CHECKS PASSED")
