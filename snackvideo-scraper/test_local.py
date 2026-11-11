"""Local end-to-end test: run the actor per mode against local Apify storage.

    python test_local.py            # all cases
    python test_local.py profile    # cases whose name starts with 'profile'
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
    "profile": {"mode": "profile", "usernames": ["@AgathisDammaraa41198", "https://www.snackvideo.com/@thisuserdoesnotexist_zz9"], "maxItems": 150, "proxyConfiguration": NOPROXY},
    "profile_statsonly": {"mode": "profile", "usernames": ["AgathisDammaraa41198"], "includeVideos": False, "includePlaylists": False, "proxyConfiguration": NOPROXY},
    "video": {"mode": "video", "videoUrls": ["https://www.snackvideo.com/@AgathisDammaraa41198/video/5256413826759439232", "5213911100033866771", "5256413826759439999", "not a url"], "proxyConfiguration": NOPROXY},
    "hashtag": {"mode": "hashtag", "hashtags": ["#kucing", "xqzvkwplnope"], "maxItems": 250, "proxyConfiguration": NOPROXY},
    "search": {"mode": "search", "searchKeywords": ["kucing"], "maxItems": 60, "proxyConfiguration": NOPROXY},
    "search_strict": {"mode": "search", "searchKeywords": ["kucing"], "maxItems": 15, "onlyKeywordMatches": True, "proxyConfiguration": NOPROXY},
    "trending": {"mode": "trending", "maxItems": 80, "proxyConfiguration": NOPROXY},
    "playlist": {"mode": "playlist", "playlistUrls": ["https://www.snackvideo.com/@AgathisDammaraa41198/playlist/164068021363540803", "999999999999999999"], "proxyConfiguration": NOPROXY},
    "proxy_default": {"mode": "video", "videoUrls": ["5256413826759439232"], "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}},
}

REQUIRED = {
    "VIDEO": ["_input", "_source", "_scrapedAt", "id", "videoUrl", "caption", "view_count", "like_count", "comment_count", "kwai_id", "playUrl", "createdAt"],
    "PROFILE": ["_input", "_source", "_scrapedAt", "id", "kwai_id", "user_name", "followers", "publicVideos", "ownerCount", "profile"],
    "PLAYLIST": ["_input", "_source", "id", "playlistUrl"],
    "ERROR": ["_input", "_error", "_errorDetail"],
}


def run(name: str, actor_input: dict) -> list[dict]:
    storage = HERE / "storage"
    shutil.rmtree(storage, ignore_errors=True)
    kvs = storage / "key_value_stores" / "default"
    kvs.mkdir(parents=True)
    (kvs / "INPUT.json").write_text(json.dumps(actor_input), encoding="utf8")
    env = dict(os.environ, APIFY_LOCAL_STORAGE_DIR=str(storage), PYTHONIOENCODING="utf8")
    p = subprocess.run([PY, "-m", "src"], cwd=HERE, env=env, capture_output=True, text=True, encoding="utf8", timeout=900)
    log = (p.stdout + p.stderr).strip().splitlines()
    print(f"\n===== {name}  exit={p.returncode}")
    for line in log[-8:]:
        print("   |", line[:200])
    items = []
    ds = storage / "datasets" / "default"
    for f in (sorted(x for x in ds.glob("*.json") if not x.name.startswith("__")) if ds.exists() else []):
        items.append(json.loads(f.read_text(encoding="utf8")))
    if p.returncode != 0:
        print("   !! non-zero exit")
    return items


def check(name: str, items: list[dict]) -> bool:
    ok = True
    by_type: dict[str, int] = {}
    for it in items:
        rt = it.get("recordType")
        by_type[rt] = by_type.get(rt, 0) + 1
        missing = [k for k in REQUIRED.get(rt, []) if it.get(k) in (None, "") and not (rt == "VIDEO" and k == "caption")]
        if missing:
            ok = False
            print(f"   !! {rt} {it.get('id')} missing {missing}")
    vids = [i for i in items if i.get("recordType") == "VIDEO"]
    dup = len(vids) - len({(v["_input"], v["id"]) for v in vids})
    if dup:
        ok = False
        print(f"   !! {dup} duplicate videos")
    errs = [(i["_input"], i["_error"]) for i in items if i.get("_error")]
    print(f"   records={len(items)} {by_type} dupes={dup} errors={errs}")
    if vids:
        v = vids[0]
        print("   sample:", json.dumps({k: v.get(k) for k in ("id", "kwai_id", "view_count", "like_count", "createdAt", "hashtags", "keywordMatched", "_source")}, ensure_ascii=False)[:300])
    return ok


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    results = {}
    for name, inp in CASES.items():
        if name.startswith(only):
            results[name] = check(name, run(name, inp))
    print("\nSUMMARY", results)
