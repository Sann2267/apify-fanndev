"""Local smoke test -- real HTTP, no Apify platform involved.

    python test_local.py

The most important assertion here is the hollow-record one: a publication page
seeds 167 post references with no articles behind them, and the parser must
drop all 167 rather than emit empty rows.
"""

import asyncio
import json
import sys

from src.client import MediumClient
from src.constants import URL_AUTHOR, URL_FEED_PUBLICATION, URL_TAG, URL_TAG_SECTION
from src.extractor import extract_apollo, parse_apollo_posts, parse_feed, parse_post_detail

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def main():
    client = MediumClient()
    failures: list[str] = []

    print("=" * 72)
    print("1. mode=tag -- artificial-intelligence")
    html, profile = await client.get(URL_TAG.format(slug="artificial-intelligence"))
    posts, hollow = parse_apollo_posts(html, "medium-tag-apollo-top", "ai")
    print(f"   TLS profile that won: {profile}")
    print(f"   usable posts: {len(posts)} | hollow refs dropped: {hollow}")
    if len(posts) < 10:
        failures.append(f"expected ~35 posts on a tag page, got {len(posts)}")
    clapped = [p for p in posts if p.get("clapCount") is not None]
    paywalled = [p for p in posts if p.get("isPaywalled")]
    authored = [p for p in posts if p.get("authorName")]
    print(f"   with claps: {len(clapped)} | paywalled: {len(paywalled)} | with author resolved: {len(authored)}")
    if not clapped:
        failures.append("no post carried a clap count -- the engagement field is the whole point")
    if not authored:
        failures.append("no post resolved its author -- the __ref walk is broken")
    top = sorted(clapped, key=lambda p: p["clapCount"], reverse=True)[:3]
    for p in top:
        print(f"   {p['clapCount']:>7} claps  {str(p['title'])[:44]:46s} by {p['authorName']}")
    sample = dict(posts[0])
    print("   sample:", json.dumps(sample, ensure_ascii=False, indent=2)[:900])
    if any(isinstance(v, dict) and "__ref" in v for v in posts[0].values()):
        failures.append("an unresolved __ref pointer leaked into the output")

    print("=" * 72)
    print("2. tag sections")
    for section, path in (("archive", "archive"), ("recommended", "recommended")):
        shtml, _ = await client.get(
            URL_TAG_SECTION.format(slug="artificial-intelligence", section=path)
        )
        srecords, shollow = parse_apollo_posts(shtml, f"medium-tag-apollo-{section}", "ai")
        print(f"   {section:12s} usable={len(srecords):3d} hollow={shollow}")
        if not srecords:
            failures.append(f"tag section {section} returned nothing")

    print("=" * 72)
    print("3. mode=author -- @medium")
    ahtml, _ = await client.get(URL_AUTHOR.format(handle="medium"))
    aposts, ahollow = parse_apollo_posts(ahtml, "medium-author-apollo", "@medium")
    print(f"   usable={len(aposts)} hollow={ahollow}")
    if aposts:
        print(f"   e.g. {aposts[0]['title'][:50]!r} claps={aposts[0]['clapCount']}")
    else:
        failures.append("author page returned no posts")

    print("=" * 72)
    print("4. THE PUBLICATION TRAP -- hollow refs must all be dropped")
    phtml, _ = await client.get("https://medium.com/better-programming")
    cache = extract_apollo(phtml)
    refs = [k for k in cache if k.startswith("Post:")]
    pposts, phollow = parse_apollo_posts(phtml, "medium-publication-apollo", "better-programming")
    print(f"   Post: keys in cache: {len(refs)}")
    print(f"   emitted: {len(pposts)} | dropped as hollow: {phollow}")
    if pposts:
        print("   ! publication pages now carry usable posts -- the mode could switch to Apollo")
    if phollow != len(refs) and not pposts:
        failures.append(f"hollow count {phollow} does not account for all {len(refs)} refs")
    if len(pposts) not in (0, len(refs)):
        # Partial is fine in principle, but every emitted row must have a title.
        if any(not p.get("title") for p in pposts):
            failures.append("a titleless post was emitted -- the hollow guard leaked")

    print("=" * 72)
    print("5. mode=publication -- via RSS, which is what actually works")
    xml, _ = await client.get(URL_FEED_PUBLICATION.format(slug="better-programming"), min_bytes=2000)
    feed = parse_feed(xml, "medium-publication-rss", "better-programming")
    print(f"   feed items: {len(feed)}")
    withbody = [f for f in feed if f.get("contentHtml")]
    print(f"   with body html: {len(withbody)}")
    if not feed:
        failures.append("publication feed returned no items")
    if not withbody:
        failures.append("no feed item carried the article body -- that is the feed's whole value")
    full = [f for f in feed if f.get("isContentFull")]
    print(f"   full articles: {len(full)} | preview only: {len(feed) - len(full)}")
    for f in feed[:3]:
        print(f"   full={str(f['isContentFull']):5s} body={len(f.get('contentText') or ''):6d} "
              f"{str(f['title'])[:34]:36s} by {f['authorName']}")
    # These four are the assertions that an HTML parser silently failed:
    if any("CDATA" in str(f.get("title") or "") for f in feed):
        failures.append("a CDATA wrapper leaked into a feed title")
    if any(not f.get("authorName") for f in feed):
        failures.append("a feed row has no author -- the dc:creator namespace is not resolving")
    if any(not f.get("publishedAtRaw") for f in feed):
        failures.append("a feed row has no publication date")
    titles = [f.get("title") for f in feed]
    if len(set(titles)) != len(titles):
        failures.append("feed rows share a title -- per-item lookups are escaping the item")
    if feed and feed[0]["clapCount"] is not None:
        failures.append("a feed row claimed a clap count -- the feed publishes none")

    print("=" * 72)
    print("6. mode=post -- a single article")
    target = posts[0]["url"]
    ptext, _ = await client.get(target)
    detail = parse_post_detail(ptext, target)
    print(f"   {str(detail['title'])[:56]}")
    print(f"   paragraphs={detail['paragraphCount']} truncated={detail['isTruncated']} "
          f"paywalled={detail['isPaywalled']} claps={detail['clapCount']}")
    print(f"   body chars: {len(detail.get('bodyText') or '')}")
    if not detail.get("bodyText"):
        failures.append("post detail returned no body text at all")

    print("=" * 72)
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


asyncio.run(main())
