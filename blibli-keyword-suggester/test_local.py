"""Local smoke test against the live site."""

import asyncio
import json
import sys

from src.client import BlibliClient
from src.constants import (
    ALPHABET,
    DIGITS,
    SOURCE_AUTOCOMPLETE,
    SOURCE_EXPANSION,
)
from src.keywords import (
    competition_level,
    expansion_prefixes,
    fetch_curated,
    fetch_related,
    fetch_suggestions,
    fetch_trending,
    harvest,
    keyword_record,
    measure_competition,
    search_url,
)

FULL = "--full" in sys.argv
SEED = "laptop"

_JSON_TYPES = {"string": str, "number": (int, float), "integer": int,
               "boolean": bool, "object": dict, "array": list}


def load_output_schema() -> dict:
    with open(".actor/output_schema.json", encoding="utf-8") as fh:
        return json.load(fh)["fields"]["properties"]


def schema_violations(records: list, schema: dict) -> list:
    problems = []
    for record in records:
        for field, spec in schema.items():
            if field not in record:
                continue
            value = record[field]
            declared = spec.get("type")
            allowed = declared if isinstance(declared, list) else [declared]
            if value is None:
                if "null" not in allowed:
                    problems.append(f"{field}=null but type is {declared}")
                continue
            flat = []
            for name in allowed:
                mapped = _JSON_TYPES.get(name)
                if mapped is None:
                    continue
                flat.extend(mapped if isinstance(mapped, tuple) else (mapped,))
            if flat and (
                not isinstance(value, tuple(flat))
                or (isinstance(value, bool) and bool not in flat)
            ):
                problems.append(f"{field}={value!r} ({type(value).__name__}) vs {declared}")
    return sorted(set(problems))


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    return condition


def check_schema(records, schema) -> bool:
    problems = schema_violations(records, schema)
    return check("matches output_schema.json", not problems, "; ".join(problems[:4]))


async def main() -> int:
    schema = load_output_schema()
    client = BlibliClient()
    failures = 0
    try:
        # ---- pure helpers -------------------------------------------------
        print("\n=== helpers ===")
        failures += not check("none -> seed only", expansion_prefixes(SEED, "none") == [SEED])
        failures += not check(
            "alphabet -> 1 + 26", len(expansion_prefixes(SEED, "alphabet")) == 1 + len(ALPHABET)
        )
        failures += not check(
            "alphanumeric -> 1 + 26 + 10",
            len(expansion_prefixes(SEED, "alphanumeric")) == 1 + len(ALPHABET) + len(DIGITS),
        )
        failures += not check(
            "search URL encoded",
            search_url("laptop gaming") == "https://www.blibli.com/cari/laptop%20gaming",
            search_url("laptop gaming"),
        )
        for count, want in ((500, "LOW"), (5_000, "MEDIUM"), (30_000, "HIGH"),
                            (80_000, "VERY_HIGH")):
            failures += not check(f"band {count} -> {want}", competition_level(count) == want)
        failures += not check("band None-safe", competition_level(None) is None)

        rec = keyword_record("laptop gaming murah", SEED, SOURCE_EXPANSION, 3, "laptop g")
        failures += not check("word count", rec["wordCount"] == 3)
        failures += not check("long tail flagged", rec["isLongTail"] is True)
        failures += not check("contains seed", rec["containsSeed"] is True)
        failures += not check(
            "lateral term not marked as containing seed",
            keyword_record("tas jinjing", SEED, SOURCE_EXPANSION, 1)["containsSeed"] is False,
        )

        # ---- live autocomplete ---------------------------------------------
        print("\n=== live autocomplete ===")
        terms = await fetch_suggestions(client, SEED)
        print(f"  '{SEED}' -> {len(terms)}: {terms[:6]}")
        failures += not check("got suggestions", bool(terms))
        failures += not check("terms are strings", all(isinstance(t, str) and t for t in terms))

        # Blibli publishes no volume; assert the claim still holds so a
        # future API change that ADDS one gets noticed rather than ignored.
        payload = await client.get_json(
            "https://www.blibli.com/backend/search/autocomplete",
            params={"searchTermPrefix": SEED}, referer="/",
        )
        raw = (payload.get("data") or {}).get("suggestions") or []
        volume_fields = {
            k: v for s in raw for k, v in s.items()
            if k in ("productCount", "count", "volume", "frequency") and v is not None
        }
        failures += not check(
            "still no volume field upstream (claim holds)",
            not volume_fields, str(volume_fields),
        )
        failures += not check(
            "dsScore still uninformative",
            {s.get("dsScore") for s in raw} <= {0.0, None},
            str({s.get("dsScore") for s in raw}),
        )

        # ---- expansion actually expands -------------------------------------
        print("\n=== expansion yield ===")
        collected = []
        async for term, source, position, prefix in harvest(client, SEED, "alphabet", 0):
            collected.append((term, source, position, prefix))
        keywords = [t for t, *_ in collected]
        print(f"  alphabet expansion -> {len(keywords)} unique keywords")
        failures += not check(
            "expansion beats bare seed", len(keywords) > len(terms) * 3,
            f"{len(keywords)} vs {len(terms)} bare",
        )
        failures += not check("no duplicates", len(keywords) == len({k.lower() for k in keywords}))
        sources = {s for _, s, _, _ in collected}
        failures += not check(
            "both sources present",
            SOURCE_AUTOCOMPLETE in sources and SOURCE_EXPANSION in sources, str(sources),
        )
        failures += not check(
            "expansion rows carry their prefix",
            all(p for t, s, _, p in collected if s == SOURCE_EXPANSION),
        )
        # Terms where the seed is NOT the leading word -- these are the
        # discoveries a merchant would never have thought to type.
        laterals = [t for t, *_ in collected if not t.lower().startswith(SEED)]
        print(f"  lateral discoveries (seed not leading): {len(laterals)} e.g. {laterals[:3]}")
        failures += not check("expansion finds lateral phrasings", bool(laterals))

        # ---- competition measurement -----------------------------------------
        print("\n=== competition measurement ===")
        counts = {}
        for kw in ("laptop", "laptop gaming"):
            counts[kw] = await measure_competition(client, kw)
        print("  ", counts)
        failures += not check("counts returned", all(isinstance(v, int) for v in counts.values()))
        failures += not check(
            "broad keyword has more competition than long tail",
            counts["laptop"] > counts["laptop gaming"],
            f"{counts['laptop']} vs {counts['laptop gaming']}",
        )

        # ---- other sources -----------------------------------------------------
        print("\n=== other sources ===")
        related = await fetch_related(client, "laptop gaming")
        print(f"  related('laptop gaming') -> {len(related)}: {related[:5]}")
        failures += not check("related terms", bool(related))
        trending = await fetch_trending(client)
        print(f"  trending -> {len(trending)}: {trending[:5]}")
        failures += not check("trending terms", bool(trending))
        curated = await fetch_curated(client)
        print(f"  curated -> {len(curated)}")
        failures += not check("curated keywords", bool(curated))

        # ---- record shape --------------------------------------------------------
        print("\n=== record shape ===")
        records = []
        for term, source, position, prefix in collected[:12]:
            r = keyword_record(term, SEED, source, position, prefix)
            r["competingProducts"] = await measure_competition(client, term)
            r["competitionLevel"] = competition_level(r["competingProducts"])
            records.append(r)
        failures += not check("competition on every row",
                              all(isinstance(r["competingProducts"], int) for r in records))
        failures += not check("levels assigned", all(r["competitionLevel"] for r in records))
        failures += not check_schema(records, schema)
        best = sorted(records, key=lambda r: r["competingProducts"])[:5]
        print("  EASIEST KEYWORDS (least competition):")
        for r in best:
            print(f"    {r['keyword']:38s} {r['competingProducts']:>7} products  "
                  f"{r['competitionLevel']:<10} longTail={r['isLongTail']}")
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
