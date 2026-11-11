"""Local checks -- pure functions, dataset-schema regression, and one live smoke per surface.

    python test_local.py          # offline checks + live smoke
    python test_local.py offline  # offline checks only

The live assertions are about measured facts, not "it did not crash":
* ``RSC: 1`` returns text/x-component and parses to the same data as the HTML;
* a missing product answers HTTP 200 under ``RSC: 1`` and is still reported as not found;
* the category offset ceiling is real (f=975 has products, f=1000 has none);
* review pagination is ``?page=N`` and ``?f=`` is silently ignored;
* anonymous reviewers never leave the Actor with a name, company or LinkedIn URL.
"""

import asyncio
import json
import os
import sys

from src.client import NotFound, TrustRadiusClient
from src.constants import BASE
from src.extractor import html_to_text, parse_category_page, parse_product_page, parse_reviews_page, public_reviewer
from src.flight import parse_rows, resolve, stream_from_html
from src.main import NOT_FOUND_MARKER, category_slug, comparison_slug, error_record, parse_or_404, product_slug

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(f"   {'PASS' if cond else 'FAIL'}  {label}" + (f" -- {detail}" if detail else ""))
    if not cond:
        failures.append(label)


def offline() -> None:
    print("0. pure functions")
    check("product slug from URL", product_slug("https://www.trustradius.com/products/hubspot-crm/reviews?page=2") == "hubspot-crm")
    check("product slug bare", product_slug("hubspot-crm") == "hubspot-crm")
    check("category slug alias", category_slug("/crm") == category_slug("https://www.trustradius.com/categories/crm") == "crm")
    check("comparison 'a, b'", comparison_slug("asana, trello") == "asana-vs-trello")
    check("comparison URL", comparison_slug(f"{BASE}/compare-products/a-vs-b") == "a-vs-b")
    for bad in (f"{BASE}/search/?q=x", "https://www.g2.com/products/x", f"{BASE}/profile/abc"):
        try:
            product_slug(bad)
            check(f"rejects {bad}", False)
        except ValueError:
            check(f"rejects {bad}", True)
    check("html_to_text", html_to_text("<p>a&amp;b</p><ul><li>x</li></ul>") == "a&b\nx")

    print("1. flight decoder")
    # A T-row's length is in UTF-8 BYTES: an em dash is 3 bytes, 1 character.
    text = "a\u2014b"
    stream = f'0:["$","div",null,{{"children":"$1"}}]\n1:T{len(text.encode()):x},{text}2:"$$49"\n3:"$D2026-01-01"\n'
    rows = parse_rows(stream)
    check("T-row byte length", rows["1"] == text, repr(rows.get("1")))
    check("row after T-row", rows.get("2") == "$$49")
    check("$$ escape resolves to literal $", resolve(rows["2"], rows) == "$49")
    check("$D date", resolve(rows["3"], rows) == "2026-01-01")
    check("reference resolves", resolve(rows["0"], rows)[3]["children"] == text)
    html = '<script>self.__next_f.push([1,"0:\\"x\\"\\n"])</script>'
    check("stream from HTML", stream_from_html(html) == '0:"x"\n')

    print("2. privacy: the per-review flag wins over the account flag")
    raw = {"fullName": "A B", "companyName": "Co", "linkedInProfileUrl": "https://linkedin.com/in/ab",
           "authorPublic": True, "title": "CTO", "companySize": "11-50 employees"}
    anon = public_reviewer(raw, False)
    check("anonymous review hides name", "fullName" not in anon and "companyName" not in anon and "linkedInProfileUrl" not in anon)
    check("anonymous review keeps role", anon.get("title") == "CTO" and anon.get("companySize"))
    check("missing flag = anonymous", "fullName" not in public_reviewer(raw, None))
    check("public review shows name", public_reviewer(raw, True).get("fullName") == "A B")

    print("3. dataset schema accepts every record shape, error rows included")
    schema = json.load(open(os.path.join(".actor", "output_schema.json"), encoding="utf-8"))["fields"]
    typemap = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "object": dict, "array": list}
    samples = [
        {"_input": "x", "_source": "tr-rsc-reviews", "_scrapedAt": "2026-01-01T00:00:00Z", "recordType": "REVIEW", "rating": 8},
        error_record("x", "not_found", "NotFound: nope"),
    ]
    for rec in samples:
        for key, value in rec.items():
            spec = schema["properties"].get(key)
            if spec is None:
                check(f"{key} allowed by additionalProperties", schema.get("additionalProperties") is True)
                continue
            declared = spec.get("type")
            if declared is None:
                continue
            declared = declared if isinstance(declared, list) else [declared]
            if value is None:
                check(f"{rec['recordType']}.{key}=None allowed", "null" in declared)
            else:
                ok = any(isinstance(value, typemap[t]) for t in declared if t != "null")
                check(f"{rec['recordType']}.{key} type", ok, f"{type(value).__name__} vs {declared}")


async def live() -> None:
    client = TrustRadiusClient()
    try:
        print("4. RSC vs HTML")
        stream = await client.get_flight(f"{BASE}/products/hubspot-crm")
        html_stream = stream_from_html(await client.get_html(f"{BASE}/products/hubspot-crm"))
        a, b = parse_product_page(stream), parse_product_page(html_stream)
        check("same product from both payloads", a["slug"] == b["slug"] and a["rating"] == b["rating"])
        check("RSC is smaller", len(stream) < len(await client.get_html(f"{BASE}/products/hubspot-crm")))

        print("5. not-found under RSC")
        missing = await client.get_flight(f"{BASE}/products/does-not-exist-zz9")
        check("marker present", NOT_FOUND_MARKER in missing)
        try:
            parse_or_404(parse_product_page, missing, "product")
            check("raises NotFound", False)
        except NotFound:
            check("raises NotFound", True)

        print("6. category offset ceiling")
        _, at_975, _ = parse_category_page(await client.get_flight(f"{BASE}/categories/crm?f=975"))
        meta, at_1000, _ = parse_category_page(await client.get_flight(f"{BASE}/categories/crm?f=1000"))
        check("f=975 has products", len(at_975) > 0, str(len(at_975)))
        check("f=1000 has none", len(at_1000) == 0 and meta.get("missing") is True)

        print("7. review pagination")
        _, p1 = parse_reviews_page(await client.get_flight(f"{BASE}/products/hubspot-crm/reviews"))
        _, p2 = parse_reviews_page(await client.get_flight(f"{BASE}/products/hubspot-crm/reviews?page=2"))
        _, decoy = parse_reviews_page(await client.get_flight(f"{BASE}/products/hubspot-crm/reviews?f=10"))
        check("page 2 differs from page 1", {r["slug"] for r in p1}.isdisjoint({r["slug"] for r in p2}))
        check("?f= is a decoy (returns page 1)", [r["slug"] for r in decoy] == [r["slug"] for r in p1])
        check("10 per page", len(p1) == 10)
        leaked = [r for r in p1 + p2 if not r["reviewer"]["isPublic"] and "fullName" in r["reviewer"]]
        check("no anonymous reviewer leaks a name", not leaked)
    finally:
        await client.close()
    print(f"   requests={client.requests} challenges={client.challenges} tls={client.winning_profile}")


if __name__ == "__main__":
    offline()
    if "offline" not in sys.argv:
        asyncio.run(live())
    print("=" * 60)
    print("ALL PASS" if not failures else f"{len(failures)} FAILURE(S): {failures}")
    sys.exit(1 if failures else 0)
