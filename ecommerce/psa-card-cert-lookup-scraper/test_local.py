"""Standalone local runner.

Usage:
    python test_local.py cert [certNumber]
    python test_local.py sales [certNumber]
    python test_local.py range [startCert] [count]
    python test_local.py reference
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_certs, run_reference

# A real, verified cert: 2018 Panini Prizm Emergent Luka Doncic #3, PSA 10.
SAMPLE_CERT = "49204884"


async def _no_proxy():
    return None


def show(records, limit=3, keys=None):
    for r in records[:limit]:
        print("   ", {k: r.get(k) for k in keys} if keys else json.dumps(r, ensure_ascii=False)[:600])
    print(f"-> {len(records)} record(s)\n")


async def collect(mode, certs, max_items=100, concurrency=2):
    out = []

    async def push(records):
        out.extend(records)

    await run_certs(mode, certs, max_items, concurrency, _no_proxy, push)
    return out


CERT_KEYS = ["certNumber", "itemGrade", "year", "brand", "subject", "cardNumber",
             "psaEstimate", "psaPopulation", "psaPopHigher", "recentSalesCount", "_tlsProfile"]
SALE_KEYS = ["sourceCertNumber", "soldPrice", "soldDate", "seller", "saleType", "grade", "certNumber", "lotNumber"]


async def smoke():
    print("== reference: which TLS profile gets through ==")
    ref = await run_reference(None)
    show(ref, 1, ["surface", "isAvailable", "detail", "sample"])
    assert ref[0]["isAvailable"], "the cert page is not reachable -- Cloudflare rule may have changed"

    print("== cert: a known graded card ==")
    certs = await collect("cert", [SAMPLE_CERT])
    show(certs, 1, CERT_KEYS)
    rec = certs[0]
    assert not rec.get("_error"), f"cert mode failed: {rec.get('_errorDetail')}"
    assert rec["itemGrade"], "item grade missing"
    assert rec["psaPopulation"] and rec["psaPopulation"] > 0, "population missing -- the stat block did not parse"
    assert rec["psaEstimate"], "PSA estimate missing"
    assert rec["subject"] and rec["year"], "item information did not parse"
    assert rec["recentSalesCount"] > 0, "no comparable sales parsed"
    assert rec["recentSaleAvg"], "sale summary not computed"

    print("== cert: accepts a full URL and a #-prefixed number ==")
    variants = await collect("cert", [f"https://www.psacard.com/cert/{SAMPLE_CERT}", f"#{SAMPLE_CERT}"])
    show(variants, 2, ["certNumber", "itemGrade"])
    assert all(not r.get("_error") for r in variants), "input normalisation failed"

    print("== sales: comparable sales as rows ==")
    sales = await collect("sales", [SAMPLE_CERT])
    show(sales, 3, SALE_KEYS)
    assert sales and not sales[0].get("_error"), "sales mode returned no usable row"
    assert sales[0]["soldPrice"] and sales[0]["soldDate"], "sale row missing price or date"
    assert sales[0]["soldDate"][4] == "-", "sale date was not normalised to ISO"

    print("== nonexistent cert must fail loud ==")
    bad = await collect("cert", ["999999999999"])
    show(bad, 1, ["_input", "_error", "_errorDetail"])
    assert bad[0].get("_error"), "an impossible cert number produced no error row"

    print("== invalid input must fail loud ==")
    junk = await collect("cert", ["not-a-cert"])
    show(junk, 1, ["_input", "_error"])
    assert junk[0].get("_error") == "invalid_cert", "junk input was not rejected"

    print("\nALL MODES OK")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if mode == "all":
        await smoke()
    elif mode == "reference":
        show(await run_reference(None), 1)
    elif mode == "range":
        start = int(arg or SAMPLE_CERT)
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        show(await collect("cert", [str(start + i) for i in range(count)]), count, CERT_KEYS)
    else:
        show(await collect(mode, [arg or SAMPLE_CERT]), 5)


asyncio.run(main())
