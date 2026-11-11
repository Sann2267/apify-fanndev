"""Run each mode locally through the real Actor entry point and summarise the dataset.

    python run_modes.py                 # all modes
    python run_modes.py reviews compare # some modes
"""
import json, os, shutil, subprocess, sys, collections

PY = sys.executable
CASES = {
    "reviews":          {"mode": "reviews", "products": ["hubspot-crm", "https://www.trustradius.com/products/pipedrive/reviews"], "maxItems": 25, "includeReviewDetails": True},
    "products":         {"mode": "products", "products": ["hubspot-crm", "does-not-exist-xyz"]},
    "categoryProducts": {"mode": "categoryProducts", "categories": ["crm", "https://www.trustradius.com/categories/project-management"], "maxItems": 60},
    "alternatives":     {"mode": "alternatives", "products": ["hubspot-crm"]},
    "compare":          {"mode": "compare", "comparisons": ["hubspot-crm-vs-pipedrive", "asana, trello"]},
    "categories":       {"mode": "categories"},
}

def run(name, inp):
    base = os.path.join("storage")
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(os.path.join(base, "key_value_stores", "default"), exist_ok=True)
    inp = {**inp, "proxyConfiguration": {"useApifyProxy": False}}
    if os.environ.get("TR_PROXY") == "1":
        inp["proxyConfiguration"] = {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}
    json.dump(inp, open(os.path.join(base, "key_value_stores", "default", "INPUT.json"), "w"))
    env = {**os.environ, "APIFY_LOCAL_STORAGE_DIR": os.path.abspath(base), "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([PY, "-m", "src"], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    logs = [l for l in (p.stdout + p.stderr).splitlines() if any(k in l for k in ("INFO", "WARN", "ERROR", "Traceback", "Error"))]
    ds = os.path.join(base, "datasets", "default")
    items = []
    if os.path.isdir(ds):
        for f in sorted(os.listdir(ds)):
            if f.endswith(".json") and f != "__metadata__.json":
                items.append(json.load(open(os.path.join(ds, f), encoding="utf-8")))
    os.makedirs("output", exist_ok=True)
    json.dump(items, open(f"output/{name}.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"===== {name}: exit={p.returncode} records={len(items)} types={dict(collections.Counter(i.get('recordType') for i in items))}")
    for l in logs[-12:]:
        print("   ", l[:260])
    return items

if __name__ == "__main__":
    for name in (sys.argv[1:] or CASES):
        run(name, CASES[name])
