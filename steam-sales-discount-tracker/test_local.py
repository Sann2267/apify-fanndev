"""Local end-to-end test: run the actor per mode against local Apify storage.

    python test_local.py              # all cases
    python test_local.py deals        # cases whose name starts with 'deals'
    python test_local.py --keep ...   # keep storage between cases (change-detection test)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PY = sys.executable
NOPROXY = {"useApifyProxy": False}

CASES = {
    "deals_basic": {"mode": "deals", "maxItems": 150, "proxyConfiguration": NOPROXY},
    "deals_filtered": {"mode": "deals", "country": "DE", "tags": ["Horror", "zzNotATag"], "category": "games",
                       "minDiscount": 50, "maxPrice": 10, "sortBy": "priceAsc", "maxItems": 60, "proxyConfiguration": NOPROXY},
    "deals_full_tag": {"mode": "deals", "tags": ["Cooking"], "maxItems": 20000, "proxyConfiguration": NOPROXY},
    "deals_lean": {"mode": "deals", "country": "ID", "maxItems": 30, "includeDiscountDetails": False,
                   "includeUsdPrices": False, "proxyConfiguration": NOPROXY},
    "featured": {"mode": "featured", "proxyConfiguration": NOPROXY},
    "freebies": {"mode": "freebies", "proxyConfiguration": NOPROXY},
    "prices_regional": {"mode": "appPrices", "apps": ["1808500", "https://store.steampowered.com/app/632360/Risk_of_Rain_2/",
                                                "Elden Ring", "730", "99999999", "https://example.com/x"],
                  "countries": ["US", "GB", "DE", "BR", "TR", "IN", "ID", "AR"], "proxyConfiguration": NOPROXY},
    "salePage": {"mode": "salePage", "saleUrls": ["https://store.steampowered.com/sale/TwoPointFranchiseSale2026",
                                                  "MachineGamesDevSale", "steamautumnsale", "not a sale!"],
                 "proxyConfiguration": NOPROXY},
    "saleEvents": {"mode": "saleEvents", "proxyConfiguration": NOPROXY},
    "bad_country": {"mode": "deals", "country": "ZZ", "proxyConfiguration": NOPROXY},
    "prices_missing": {"mode": "appPrices", "apps": [], "proxyConfiguration": NOPROXY},
}

COMMON = ["_input", "_source", "_scrapedAt", "recordType"]
PRICED = COMMON + ["itemKey", "name", "discountPct", "finalPrice", "originalPrice", "currency", "country"]
REQUIRED = {
    "DEAL": PRICED + ["position", "storeUrl", "finalPriceCents"],
    "DAILY_DEAL": PRICED[:4] + ["id", "name", "discountPct", "finalPrice", "currency"],
    "SPOTLIGHT": COMMON + ["dealCategory", "spotlightName", "url", "targetType"],
    "FEATURED_SPECIAL": COMMON + ["id", "name", "discountPct", "finalPrice", "currency"],
    "FREEBIE": COMMON + ["freebieType", "itemKey", "name", "storeUrl"],
    "APP_PRICE": COMMON + ["appid", "country", "priceAvailable", "currency", "finalPrice", "discountPct"],
    "SALE_PAGE": COMMON + ["saleName", "saleStartsAt", "saleEndsAt", "itemCount"],
    "SALE_ITEM": COMMON + ["saleName", "itemKey", "itemType", "id", "name", "discountPct", "finalPrice"],
    "SALE_EVENT": COMMON + ["eventType", "name", "startDate", "endDate", "status"],
    "DEAL_ENDED": COMMON + ["itemKey", "name", "lastFinalPriceCents"],
    "ERROR": ["_input", "_source", "_scrapedAt", "_error", "_errorDetail"],
}

PYTYPE = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}


def run(name: str, actor_input: dict, keep: bool) -> tuple[int, list[dict], list[str]]:
    storage = HERE / "storage"
    if not keep:
        shutil.rmtree(storage, ignore_errors=True)
    shutil.rmtree(storage / "datasets" / "default", ignore_errors=True)
    kvs = storage / "key_value_stores" / "default"
    kvs.mkdir(parents=True, exist_ok=True)
    (kvs / "INPUT.json").write_text(json.dumps(actor_input), encoding="utf8")
    env = dict(os.environ, APIFY_LOCAL_STORAGE_DIR=str(storage), PYTHONIOENCODING="utf8",
               CRAWLEE_PURGE_ON_START="0" if keep else "1")
    p = subprocess.run([PY, "-m", "src"], cwd=HERE, env=env, capture_output=True, timeout=1500)
    log = (p.stdout + p.stderr).decode("utf8", "replace").strip().splitlines()
    print(f"\n===== {name}  exit={p.returncode}")
    for line in log[-5:]:
        print("   |", line[:230])
    items = []
    ds = storage / "datasets" / "default"
    for f in (sorted(x for x in ds.glob("*.json") if not x.name.startswith("__")) if ds.exists() else []):
        items.append(json.loads(f.read_text(encoding="utf8")))
    return p.returncode, items, log


def check(items: list[dict]) -> list[str]:
    """Required fields per record type + type check against output_schema.json.

    Apify validates a whole push_data batch: one record whose value is null
    where the schema says a bare 'string' rejects the batch (exit 91, 0 rows).
    """
    schema = json.loads((HERE / ".actor" / "output_schema.json").read_text(encoding="utf8"))["fields"]["properties"]
    problems = []
    by_type: dict[str, int] = {}
    for it in items:
        rt = it.get("recordType", "?")
        by_type[rt] = by_type.get(rt, 0) + 1
        for k in REQUIRED.get(rt, COMMON):
            if k not in it:
                problems.append(f"{rt} missing {k}: {json.dumps(it)[:160]}")
        for k, v in it.items():
            decl = schema.get(k, {}).get("type")
            if decl is None:
                continue
            types = decl if isinstance(decl, list) else [decl]
            if v is None:
                if "null" not in types:
                    problems.append(f"{rt}.{k} is null but schema type is {decl}")
            elif not any(isinstance(v, PYTYPE[t]) for t in types if t in PYTYPE):
                problems.append(f"{rt}.{k}={v!r} does not match schema type {decl}")
    print("   records:", by_type)
    return problems


def main() -> None:
    args = sys.argv[1:]
    keep = "--keep" in args
    args = [a for a in args if a != "--keep"]
    bad = 0
    for name, inp in CASES.items():
        if args and not any(name.startswith(a) for a in args):
            continue
        code, items, _log = run(name, inp, keep)
        problems = check(items)
        for it in [i for i in items if i.get("recordType") != "ERROR"][:2]:
            s = {k: (v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} len={len(v)}>") for k, v in it.items()}
            print("   sample:", json.dumps(s, ensure_ascii=False)[:900])
        for e in [i for i in items if i.get("recordType") == "ERROR"]:
            print("   error row:", e["_input"], e["_error"], e["_errorDetail"][:140])
        for pr in problems[:6]:
            print("   !!", pr)
        bad += bool(problems)
    print("\nFAILED CASES WITH SCHEMA PROBLEMS:", bad)


if __name__ == "__main__":
    main()
