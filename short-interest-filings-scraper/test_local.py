"""Standalone local runner -- exercises every mode without the Apify platform.

Usage:
    python test_local.py short-interest [TICKER]
    python test_local.py short-volume [YYYY-MM-DD]
    python test_local.py filings [TICKER]
    python test_local.py filing-search "<query>"
    python test_local.py company [TICKER]
    python test_local.py reference
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import (
    run_company_profiles,
    run_filing_search,
    run_filings,
    run_reference,
    run_short_interest,
    run_short_volume,
)


def show(records, limit=2, keys=None):
    for r in records[:limit]:
        if keys:
            print("   ", {k: r.get(k) for k in keys})
        else:
            print(json.dumps(r, ensure_ascii=False, indent=2)[:900], "...")
    print(f"-> {len(records)} record(s)\n")


SI_KEYS = ["symbol", "settlementDate", "shortInterest", "avgDailyShareVolume", "daysToCover", "exchange"]
SV_KEYS = ["symbol", "date", "venue", "shortVolume", "totalVolume", "shortVolumeRatio"]
FIL_KEYS = ["companyName", "form", "filingDate", "reportDate", "accessionNumber", "filingUrl"]
FTS_KEYS = ["companyDisplayName", "form", "fileDate", "fileType", "relevanceScore", "totalMatches"]


async def smoke():
    print("== short-interest: TSLA (Nasdaq-listed) ==")
    si = await run_short_interest(["TSLA"], "stocks", 30, True, None)
    show(si, 2, SI_KEYS)
    assert si and not si[0].get("_error"), "short-interest returned no usable row"
    assert si[0]["shortInterest"] and si[0]["settlementDate"], "short interest row is missing its numbers"
    assert si[0]["settlementDate"][4] == "-", "settlementDate was not normalised to ISO"

    print("== short-interest: GME (NYSE) must report the source's own limit ==")
    nyse = await run_short_interest(["GME"], "stocks", 5, True, None)
    show(nyse, 1, ["_input", "_error", "_errorDetail"])
    assert nyse[0].get("_error") == "not_published", "NYSE symbol did not produce the documented not_published row"

    print("== short-interest: nonsense ticker ==")
    bad = await run_short_interest(["ZZZZQQ"], "stocks", 5, False, None)
    show(bad, 1, ["_input", "_error", "_errorDetail"])
    assert bad[0].get("_error") == "not_found", "unknown ticker did not produce not_found"

    print("== short-volume: latest published FINRA day, filtered to 3 symbols ==")
    sv = await run_short_volume([], "consolidated", ["TSLA", "GME", "AAPL"], 50, None)
    show(sv, 3, SV_KEYS)
    assert sv and not sv[0].get("_error"), "short-volume returned no usable row"
    assert sv[0]["shortVolumeRatio"] is not None, "shortVolumeRatio was not computed"
    assert {r.get("symbol") for r in sv} >= {"TSLA", "GME"}, "symbol filter dropped requested tickers"

    print("== short-volume: whole file (cap 5) ==")
    whole = await run_short_volume([], "consolidated", [], 5, None)
    show(whole, 2, SV_KEYS)
    assert len(whole) == 5, "maxItems cap not honoured on the full file"

    print("== filings: AAPL 8-K only ==")
    fil = await run_filings(["AAPL"], ["8-K"], None, 10, None)
    show(fil, 2, FIL_KEYS)
    assert fil and not fil[0].get("_error"), "filings returned no usable row"
    assert all(r.get("form") == "8-K" for r in fil if not r.get("_error")), "form filter leaked other forms"
    assert fil[0]["filingUrl"].startswith("https://www.sec.gov/Archives/"), "filingUrl was not built"

    print("== filings: by bare CIK ==")
    bycik = await run_filings(["320193"], [], None, 3, None)
    show(bycik, 1, FIL_KEYS)
    assert bycik and not bycik[0].get("_error"), "CIK lookup failed"

    print("== company: AAPL + NVDA profiles ==")
    co = await run_company_profiles(["AAPL", "NVDA"], None)
    show(co, 2, ["companyName", "cik", "tickers", "exchanges", "sicDescription", "filingCount"])
    assert co and co[0].get("companyName"), "company profile is missing its name"

    print("== filing-search: full-text across EDGAR ==")
    fts = await run_filing_search('"reverse stock split"', ["8-K"], "2026-08-01", "2026-09-18", 8, None)
    show(fts, 2, FTS_KEYS)
    assert fts and not fts[0].get("_error"), "filing-search returned no usable row"
    assert fts[0].get("documentUrl"), "documentUrl was not built"

    print("== reference: probe every source ==")
    ref = await run_reference(None)
    for r in ref:
        print("   ", r.get("source"), r.get("isAvailable"), r.get("detail"), r.get("sample"))
    assert any(r["source"] == "nasdaq-short-interest" and r["isAvailable"] for r in ref), "Nasdaq source down"
    assert any(r["source"] == "finra-consolidated" and r["isAvailable"] for r in ref), "FINRA source down"
    assert any(r["source"] == "sec-submissions" and r["isAvailable"] for r in ref), "SEC source down"

    print("\nALL MODES OK")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if mode == "all":
        await smoke()
    elif mode == "short-interest":
        show(await run_short_interest([arg or "TSLA"], "stocks", 30, True, None), 5, SI_KEYS)
    elif mode == "short-volume":
        show(await run_short_volume([arg] if arg else [], "consolidated", [], 10, None), 5, SV_KEYS)
    elif mode == "filings":
        show(await run_filings([arg or "AAPL"], [], None, 10, None), 5, FIL_KEYS)
    elif mode == "filing-search":
        show(await run_filing_search(arg or '"short interest"', ["8-K"], None, None, 10, None), 5, FTS_KEYS)
    elif mode == "company":
        show(await run_company_profiles([arg or "AAPL"], None), 3)
    elif mode == "reference":
        show(await run_reference(None), 10)
    else:
        print(__doc__)


asyncio.run(main())
