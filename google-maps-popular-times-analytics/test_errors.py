"""Offline checks: popular-times parsing, live detection, long format, exporters."""
import json
import pathlib
import sys

from src.exporters import flatten, to_csv, to_json, to_ndjson, to_xlsx
from src.geo import GeoTarget, haversine_km
from src.popular_times import DAY_NAMES, find_container, parse, to_long_rows

fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  <- {extra}"))
    if not cond:
        fails.append(name)


def hour(h, pct, label="Usually a little busy"):
    return [h, pct, label, "", f"{h} am", None, "6a"]


print("== structural detection ==")
container = [[7, None, 1], [1, [hour(6, 0, ""), hour(7, 20)], 0], [2, [hour(6, 10)], 0]]
check("finds a flat container", find_container(container) is container)
# Google moves this block between responses, so it must be found at any depth.
nested = [None, {"x": 1}, [[None, [container]]]]
check("finds it when nested", find_container(nested) is container)
check("no false positive on hours-of-operation shape",
      find_container([[["Monday", 2, [2026, 9, 16], [["9 am-5 pm"]], 0, 1]]]) is None)
check("no false positive on empty", find_container([]) is None)
check("no false positive on scalars", find_container([1, 2, 3]) is None)

print("== parsing ==")
record = [container, 3, None, 1, 11, None, "Less busy than usual", [11, 60]]
p = parse(record)
check("parsed", p is not None)
check("days sorted Mon..Sun", [d["dayNumber"] for d in p["popularTimes"]] == [1, 2, 7], p["popularTimes"])
check("day names", p["popularTimes"][0]["day"] == "Monday")
check("day 7 is Sunday", DAY_NAMES[7] == "Sunday")
check("no-data day flagged", p["popularTimes"][-1]["hasData"] is False)
check("daysWithData", p["daysWithData"] == 2, p["daysWithData"])
check("busiest", p["busiestDay"] == "Monday" and p["busiestHour"] == 7, (p["busiestDay"], p["busiestHour"]))
check("peak", p["peakOccupancyPercent"] == 20)
check("average", p["averageOccupancyPercent"] == 10.0, p["averageOccupancyPercent"])
check("live parsed", p["hasLiveData"] is True and p["liveOccupancyPercent"] == 60, p)
check("live hour", p["liveHour"] == 11)
check("current day/hour", (p["currentDay"], p["currentHour"]) == (3, 11), (p["currentDay"], p["currentHour"]))
check("absent -> None", parse([None] * 40) is None)

print("== live vs projection ==")
# "Now: ..." is Google projecting from the weekly curve, NOT a live measurement.
proj = parse([container, 3, None, 1, 11, None, "Now: Usually as busy as it gets"])
check("projection is not live", proj["hasLiveData"] is False, proj)
check("projection keeps its text", proj["liveStatusText"].startswith("Now:"))
check("projection has no percent", proj["liveOccupancyPercent"] is None)

print("== long format ==")
rows = to_long_rows({"name": "A", "placeId": "P", "latitude": 1.0, "longitude": 2.0}, p)
check("row per hour", len(rows) == 3, len(rows))
check("carries identity", rows[0]["name"] == "A" and rows[0]["placeId"] == "P")
check("carries coords", rows[0]["latitude"] == 1.0)
check("peak flagged once per day",
      sum(1 for r in rows if r["day"] == "Monday" and r["isPeakHour"]) == 1, rows)
check("no rows for empty day", all(r["day"] != "Sunday" for r in rows))

print("== real captures ==")
sp = pathlib.Path(r"C:/Users/F/AppData/Local/Temp/claude/d--FANN-Apify-actors"
                  r"/a573f04f-59ea-4a22-9576-6ea68f373416/scratchpad/gmaps2")
if (sp / "live_detail.json").exists():
    d = json.loads((sp / "live_detail.json").read_text(encoding="utf-8"))
    r = parse(d[6])
    check("real capture parses", r is not None and r["daysWithData"] == 7, r and r["daysWithData"])
    check("real capture live", r["hasLiveData"] and 0 <= r["liveOccupancyPercent"] <= 100, r)
    check("real long rows", len(to_long_rows({"name": "x"}, r)) > 100)
else:
    print("  SKIP real captures (scratchpad cleaned)")

print("== geo (inherited) ==")
check("named area", GeoTarget(area_name="jakarta").matches(-6.2, 106.8) is True)
check("outside", GeoTarget(area_name="jakarta").matches(48.0, 2.0) is False)
check("haversine", 335 < haversine_km(48.8583, 2.2944, 51.5074, -0.1278) < 350)
try:
    GeoTarget(area_name="atlantis"); check("unknown area raises", False)
except ValueError:
    check("unknown area raises", True)

print("== exporters ==")
recs = [{"recordType": "POPULAR_TIMES_HOUR", "name": "A", "day": "Monday", "hour": 7,
         "occupancyPercent": 20, "isPeakHour": True}]
csv_bytes = to_csv(recs)
check("csv BOM", csv_bytes.startswith(b"\xef\xbb\xbf"))
check("csv has hour cols", "occupancyPercent" in csv_bytes.decode("utf-8-sig").splitlines()[0])
check("ndjson", len(to_ndjson(recs).decode().strip().splitlines()) == 1)
check("json", json.loads(to_json(recs).decode())[0]["name"] == "A")
x = to_xlsx(recs)
check("xlsx", x is not None and x[:2] == b"PK")
check("csv empty safe", to_csv([]) == b"")
check("flatten", flatten({"a": {"b": 1}}) == {"a.b": 1})

print()
if fails:
    print(f"{len(fails)} FAILED: {fails}")
    sys.exit(1)
print("ALL CHECKS PASSED")
