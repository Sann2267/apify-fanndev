"""Local end-to-end test: run the actor per mode against local Apify storage.

    python test_local.py              # all cases
    python test_local.py apps         # cases whose name starts with 'apps'
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
    "topConcurrent": {"mode": "topConcurrent", "maxItems": 100, "proxyConfiguration": NOPROXY},
    "topConcurrent_lean": {"mode": "topConcurrent", "maxItems": 10, "includeStoreDetails": False, "minPlayers": 50000, "proxyConfiguration": NOPROXY},
    "topDailyPeak": {"mode": "topDailyPeak", "maxItems": 100, "proxyConfiguration": NOPROXY},
    "appsCurrent": {"mode": "appsCurrent", "apps": ["730", "https://store.steampowered.com/app/570/Dota_2/", "https://steamcharts.com/app/440",
                                                    "Elden Ring", "3393110", "99999999", "zzqqxxnotagame", "https://example.com/nothing"],
                    "includeSteamchartsStats": True, "proxyConfiguration": NOPROXY},
    "appHistory": {"mode": "appHistory", "apps": ["730", "https://steamdb.info/app/1245620/charts/", "3393110"], "proxyConfiguration": NOPROXY},
    "appHistory_90d": {"mode": "appHistory", "apps": ["570"], "historyDays": 90, "proxyConfiguration": NOPROXY},
    "steamchartsTop": {"mode": "steamchartsTop", "maxItems": 260, "proxyConfiguration": NOPROXY},
    "steamchartsTop_min": {"mode": "steamchartsTop", "maxItems": 5000, "minPlayers": 20000, "proxyConfiguration": NOPROXY},
    "steamOnline": {"mode": "steamOnline", "proxyConfiguration": NOPROXY},
    "apps_missing": {"mode": "appsCurrent", "apps": [], "proxyConfiguration": NOPROXY},
}

COMMON = ["_input", "_source", "_scrapedAt", "recordType"]
REQUIRED = {
    "TOP_CONCURRENT": COMMON + ["rank", "appid", "concurrent_in_game", "peak_in_game", "lastUpdate"],
    "TOP_DAILY_PEAK": COMMON + ["rank", "appid", "peak_in_game", "rollupDate"],
    "APP_CURRENT": COMMON + ["appid", "player_count", "name", "checkedAt"],
    "APP_HISTORY": COMMON + ["appid", "name", "currentPlayers", "peak24h", "allTimePeak", "months"],
    "STEAMCHARTS_TOP": COMMON + ["rank", "appid", "name", "currentPlayers", "peakPlayers30d", "hoursPlayed30d"],
    "STEAM_ONLINE": COMMON + ["label", "usersOnline", "usersOnlineAt", "peak48h", "low48h"],
    "ERROR": ["_input", "_source", "_scrapedAt", "_error", "_errorDetail"],
}


def run(name: str, actor_input: dict, keep: bool) -> tuple[int, list[dict]]:
    storage = HERE / "storage"
    if not keep:
        shutil.rmtree(storage, ignore_errors=True)
    shutil.rmtree(storage / "datasets" / "default", ignore_errors=True)
    kvs = storage / "key_value_stores" / "default"
    kvs.mkdir(parents=True, exist_ok=True)
    (kvs / "INPUT.json").write_text(json.dumps(actor_input), encoding="utf8")
    env = dict(os.environ, APIFY_LOCAL_STORAGE_DIR=str(storage), PYTHONIOENCODING="utf8",
               CRAWLEE_PURGE_ON_START="0" if keep else "1")
    p = subprocess.run([PY, "-m", "src"], cwd=HERE, env=env, capture_output=True, timeout=900)
    log = (p.stdout + p.stderr).decode("utf8", "replace").strip().splitlines()
    print(f"\n===== {name}  exit={p.returncode}")
    for line in log[-6:]:
        print("   |", line[:220])
    items = []
    ds = storage / "datasets" / "default"
    for f in (sorted(x for x in ds.glob("*.json") if not x.name.startswith("__")) if ds.exists() else []):
        items.append(json.loads(f.read_text(encoding="utf8")))
    return p.returncode, items


def check(items: list[dict]) -> list[str]:
    problems = []
    by_type: dict[str, int] = {}
    for it in items:
        rt = it.get("recordType", "?")
        by_type[rt] = by_type.get(rt, 0) + 1
        for k in REQUIRED.get(rt, COMMON):
            if k not in it:
                problems.append(f"{rt} missing {k}: {json.dumps(it)[:160]}")
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
        code, items = run(name, inp, keep)
        problems = check(items)
        for it in items[:2]:
            s = {k: (v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} len={len(v)}>") for k, v in it.items()}
            print("   sample:", json.dumps(s, ensure_ascii=False)[:600])
        errs = [i for i in items if i.get("recordType") == "ERROR"]
        for e in errs:
            print("   error row:", e["_input"], e["_error"], e["_errorDetail"][:120])
        for pr in problems[:5]:
            print("   !!", pr)
        bad += bool(problems)
    print("\nFAILED CASES WITH SCHEMA PROBLEMS:", bad)


if __name__ == "__main__":
    main()
