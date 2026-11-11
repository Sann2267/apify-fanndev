"""Offline checks: claim detection, closure logic, scoring, filters, summary."""
import json, sys
from src.status import (CLOSED_BOILERPLATE, assess, closure_status, is_unclaimed,
                        matches_filters, summarise)
from src.exporters import to_csv, to_json
from src.geo import GeoTarget

fails = []
def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  <- {extra}"))
    if not cond: fails.append(name)

print("== claim detection ==")
check("claim link -> unclaimed",
      is_unclaimed([["Own this business?", "https://business.google.com/create?x=1"]]))
check("claimbz tag -> unclaimed", is_unclaimed(["...gmbsrc=id-en...claimbz_aoc_a..."]))
check("no link -> claimed", is_unclaimed([["Report a legal issue", "https://support.google.com/x"]]) is False)
check("empty -> claimed", is_unclaimed([]) is False)
check("None safe", is_unclaimed(None) is False)

print("== closure ==")
# Every record carries Google's own suggest-an-edit wording; matching "closed"
# naively marks the entire dataset closed. This was a real trap in recon.
boiler = [list(CLOSED_BOILERPLATE)]
check("boilerplate is not a closure", closure_status(boiler, {}) == "operational", closure_status(boiler, {}))
check("permanent detected", closure_status([["Permanently closed"]], {}) == "permanently_closed")
check("temporary detected", closure_status([["Temporarily closed"]], {}) == "temporarily_closed")
check("from openNow", closure_status([], {"openNow": "Temporarily closed"}) == "temporarily_closed")
check("default operational", closure_status([], {}) == "operational")

print("== scoring ==")
worst = assess(["claimbz"], {"name": "X", "reviewsCount": 0, "rating": 3.2})
check("unclaimed+nothing scores high", worst["opportunityScore"] >= 90, worst["opportunityScore"])
check("issues listed", "unclaimed" in worst["opportunityIssues"] and "no_website" in worst["opportunityIssues"], worst)
best = assess([["Report a legal issue"]], {"name": "Y", "website": "https://a.com",
                                           "phone": "1", "openingHours": [{"day": "Mon"}],
                                           "reviewsCount": 400, "rating": 4.8})
check("healthy scores 0", best["opportunityScore"] == 0, best["opportunityScore"])
check("healthy has no issues", best["opportunityIssues"] == [], best["opportunityIssues"])
check("claimed label", best["claimStatus"] == "claimed")
# A closed business is never a prospect however neglected it looks.
closed = assess(["claimbz", ["Permanently closed"]], {"name": "Z", "reviewsCount": 0})
check("permanently closed scores 0", closed["opportunityScore"] == 0, closed["opportunityScore"])
check("closed still flagged", closed["businessStatus"] == "permanently_closed")
check("score never exceeds 100", worst["opportunityScore"] <= 100, worst["opportunityScore"])

print("== filters ==")
a = assess(["claimbz"], {"name": "X", "reviewsCount": 0})
b = assess([["Report a legal issue"]], {"name": "Y", "website": "https://a.com", "phone": "1"})
check("onlyUnclaimed keeps", matches_filters(a, {"onlyUnclaimed": True}))
check("onlyUnclaimed drops", matches_filters(b, {"onlyUnclaimed": True}) is False)
check("onlyWithoutWebsite keeps", matches_filters(a, {"onlyWithoutWebsite": True}))
check("onlyWithoutWebsite drops", matches_filters(b, {"onlyWithoutWebsite": True}) is False)
check("minScore keeps", matches_filters(a, {"minOpportunityScore": 65}))
check("minScore drops", matches_filters(b, {"minOpportunityScore": 65}) is False)
check("no filters keeps all", matches_filters(b, {}))
check("excludePermanentlyClosed drops",
      matches_filters(closed, {"excludePermanentlyClosed": True}) is False)
check("onlyClosed drops operational", matches_filters(a, {"onlyClosed": True}) is False)

print("== summary ==")
s = summarise([a, b, closed])
check("counts", s["businessesAssessed"] == 3 and s["unclaimed"] == 2, s)
check("percent", s["unclaimedPercent"] == 66.67, s["unclaimedPercent"])
check("both signal", s["unclaimedAndNoWebsite"] == 2, s)
check("closed counted", s["permanentlyClosed"] == 1, s)
check("empty safe", summarise([])["businessesAssessed"] == 0)

print("== inherited ==")
check("geo named area", GeoTarget(area_name="jakarta").matches(-6.2, 106.8) is True)
check("csv", to_csv([{"name": "A", "opportunityScore": 75}]).startswith(b"\xef\xbb\xbf"))
check("json", json.loads(to_json([{"name": "A"}]).decode())[0]["name"] == "A")

print()
if fails:
    print(f"{len(fails)} FAILED: {fails}"); sys.exit(1)
print("ALL CHECKS PASSED")
