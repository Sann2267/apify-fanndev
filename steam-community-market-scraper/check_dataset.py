"""Type-check local dataset items against .actor/output_schema.json (typed fields only)."""
import glob, json, sys

schema = json.load(open(".actor/output_schema.json", encoding="utf-8"))["fields"]
typed = {k: v["type"] for k, v in schema["properties"].items() if "type" in v}
PY = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "object": dict, "array": list, "null": type(None)}
bad, kinds = 0, {}
files = sorted(f for f in glob.glob("storage/datasets/default/*.json") if not f.endswith("__metadata__.json"))
for f in files:
    rec = json.load(open(f, encoding="utf-8"))
    kinds[rec.get("recordType")] = kinds.get(rec.get("recordType"), 0) + 1
    for field, t in typed.items():
        if field not in rec:
            if field in ("_input", "_source", "_scrapedAt", "recordType"):
                print("MISSING", field, f); bad += 1
            continue
        types = t if isinstance(t, list) else [t]
        if not isinstance(rec[field], tuple(PY[x] if not isinstance(PY[x], tuple) else PY[x][0] for x in types) + tuple(t2 for x in types if isinstance(PY[x], tuple) for t2 in PY[x])):
            print("TYPE", field, repr(rec[field])[:60], f); bad += 1
print(f"{len(files)} records {kinds} -> {'OK' if not bad else str(bad) + ' violations'}")
sys.exit(1 if bad else 0)
