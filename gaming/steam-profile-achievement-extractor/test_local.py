"""Local end-to-end test: run the actor per mode against local Apify storage.

    python test_local.py              # all cases
    python test_local.py profiles     # cases whose name starts with 'profiles'
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

ROBIN = "https://steamcommunity.com/id/robinwalker/"        # public profile, private game details
KING = "76561198742403126"                                   # public, game details public, plays ELDEN RING
LINHO = "linho"                                              # vanity, 42/42 ELDEN RING, rich showcases
HOLLOW = "76561199850987424"                                 # public profile, HIDDEN game details (hollow stats XML)
FRIENDSONLY = "76561199112309765"                            # friends-only profile
TF2_PLAYER = "76561199040282315"                             # TF2 -> legacy /stats/TF2 redirect

CASES = {
    "profiles": {"mode": "profiles", "includeEquippedItems": True, "proxyConfiguration": NOPROXY,
                 "profiles": [ROBIN, KING, LINHO, HOLLOW, FRIENDSONLY, "STEAM_0:0:84901", "[U:1:169802]",
                              "zzqq_no_such_user_xx", "https://store.steampowered.com/app/1", "76561190000000001"]},
    "userAch_explicit": {"mode": "userAchievements", "proxyConfiguration": NOPROXY,
                         "profiles": [KING, LINHO, HOLLOW, FRIENDSONLY, ROBIN],
                         "appIds": ["1245620", "https://store.steampowered.com/app/570/Dota_2/", "1091500", "notanapp"]},
    "userAch_recent": {"mode": "userAchievements", "proxyConfiguration": NOPROXY, "maxGamesPerProfile": 3,
                       "profiles": [LINHO, TF2_PLAYER], "language": "german"},
    "userAch_legacy_flat": {"mode": "userAchievements", "proxyConfiguration": NOPROXY, "flattenAchievements": True,
                            "onlyUnlocked": True, "profiles": [TF2_PLAYER], "appIds": ["440"]},
    "gameAch": {"mode": "gameAchievements", "proxyConfiguration": NOPROXY,
                "appIds": ["1245620", "440", "https://store.steampowered.com/app/730/", "570", "99999999", "x"]},
    "gameAch_flat": {"mode": "gameAchievements", "proxyConfiguration": NOPROXY, "flattenAchievements": True,
                     "appIds": ["1245620"], "language": "indonesian"},
    "friends": {"mode": "friends", "proxyConfiguration": NOPROXY, "maxItems": 50, "enrichProfiles": True,
                "profiles": [ROBIN, FRIENDSONLY, HOLLOW]},
    "badges": {"mode": "badges", "proxyConfiguration": NOPROXY, "maxItems": 400, "profiles": ["St4ck", ROBIN, FRIENDSONLY]},
    "groupMembers": {"mode": "groupMembers", "proxyConfiguration": NOPROXY, "maxItems": 1200,
                     "groups": ["https://steamcommunity.com/groups/Valve", "gmod", "zz_no_such_group_qq"]},
    "groupMembers_enrich": {"mode": "groupMembers", "proxyConfiguration": NOPROXY, "maxItems": 40, "enrichProfiles": True,
                            "groups": ["gmod"]},
    "proxy_fallback": {"mode": "gameAchievements", "appIds": ["620"],
                       "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}},
    "missing_input": {"mode": "friends", "profiles": [], "proxyConfiguration": NOPROXY},
}

COMMON = ["_input", "_source", "_scrapedAt", "recordType"]
REQUIRED = {
    "PROFILE": COMMON + ["steamId64", "personaName", "privacyState", "profileUrl", "vacBanned", "avatarFull"],
    "PLAYER_GAME_ACHIEVEMENTS": COMMON + ["steamId64", "appid", "gameName", "totalAchievements", "unlockedAchievements",
                                          "completionPct", "achievements", "ownershipConfirmed"],
    "PLAYER_ACHIEVEMENT": COMMON + ["steamId64", "appid", "apiname", "name", "achieved", "unlockedAt"],
    "GAME_ACHIEVEMENTS": COMMON + ["appid", "totalAchievements", "achievements", "rarestAchievement"],
    "GAME_ACHIEVEMENT": COMMON + ["appid", "apiname", "name", "globalPercent", "rank"],
    "FRIEND": COMMON + ["ownerSteamId64", "steamId64", "personaName", "profileUrl"],
    "BADGE": COMMON + ["ownerSteamId64", "title", "badgeType", "xp"],
    "GROUP_MEMBER": COMMON + ["groupId64", "steamId64", "profileUrl"],
    "ERROR": ["_input", "_source", "_scrapedAt", "_error", "_errorDetail"],
}


def run(name: str, actor_input: dict) -> tuple[int, list[dict], list[str]]:
    storage = HERE / "storage"
    shutil.rmtree(storage, ignore_errors=True)
    kvs = storage / "key_value_stores" / "default"
    kvs.mkdir(parents=True, exist_ok=True)
    (kvs / "INPUT.json").write_text(json.dumps(actor_input), encoding="utf8")
    env = dict(os.environ, APIFY_LOCAL_STORAGE_DIR=str(storage), PYTHONIOENCODING="utf8", CRAWLEE_PURGE_ON_START="1")
    p = subprocess.run([PY, "-m", "src"], cwd=HERE, env=env, capture_output=True, timeout=1200)
    log = (p.stdout + p.stderr).decode("utf8", "replace").strip().splitlines()
    print(f"\n===== {name}  exit={p.returncode}")
    for line in [ln for ln in log if "WARN" in ln or "ERROR" in ln or "Traceback" in ln][:8] + log[-3:]:
        print("   |", line[:240])
    items = []
    ds = storage / "datasets" / "default"
    for f in (sorted(x for x in ds.glob("*.json") if not x.name.startswith("__")) if ds.exists() else []):
        items.append(json.loads(f.read_text(encoding="utf8")))
    return p.returncode, items, log


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


ALL_ITEMS: list[dict] = []


def validate_against_output_schema(items: list[dict]) -> int:
    import jsonschema
    fields = json.loads((HERE / ".actor" / "output_schema.json").read_text(encoding="utf8"))["fields"]
    v = jsonschema.Draft7Validator(fields)
    bad = 0
    for it in items:
        for e in v.iter_errors(it):
            bad += 1
            print("   SCHEMA !!", it.get("recordType"), e.message[:160])
            break
    print(f"\nOutput-schema validation: {len(items)} records, {bad} invalid")
    return bad


def main() -> None:
    args = sys.argv[1:]
    bad = 0
    for name, inp in CASES.items():
        if args and not any(name.startswith(a) for a in args):
            continue
        code, items, _ = run(name, inp)
        ALL_ITEMS.extend(items)
        problems = check(items)
        shown = set()
        for it in items:
            if it.get("recordType") in shown or it.get("recordType") == "ERROR":
                continue
            shown.add(it.get("recordType"))
            s = {k: (v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} len={len(v)}>") for k, v in it.items()}
            print("   sample:", json.dumps(s, ensure_ascii=False)[:700])
        for e in [i for i in items if i.get("recordType") == "ERROR"]:
            print("   error row:", e["_input"][:45], "|", e["_error"], "|", e["_errorDetail"][:110])
        for pr in problems[:5]:
            print("   !!", pr)
        bad += bool(problems)
    print("\nFAILED CASES WITH SCHEMA PROBLEMS:", bad)
    validate_against_output_schema(ALL_ITEMS)


if __name__ == "__main__":
    main()
