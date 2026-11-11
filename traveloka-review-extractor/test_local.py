import asyncio, json, logging
logging.basicConfig(level=logging.INFO)
from src.client import TravelokaClient
from src.reviews import (detect_product, fetch_aggregate, fetch_count,
                         fetch_rating_tags, fetch_reviews, load_config_ids,
                         object_id_from_url, resolve_config)

HOTEL = "https://www.traveloka.com/id-id/hotel/indonesia/hotel-indonesia-kempinski-jakarta-2000000113168"
XPE = "https://www.traveloka.com/id-id/activities/indonesia/product/tiket-saung-angklung-udjo-2000858975309"

async def main():
    c = TravelokaClient(request_delay=0.3); c.bootstrap()
    cfg = await load_config_ids(c)
    print("config ids loaded:", len(cfg), "| hotel ->", cfg.get("HOTEL_GENERAL"))
    for url in (HOTEL, XPE):
        prod = detect_product(url); oid = object_id_from_url(url)
        cid, ptype, ref = resolve_config(prod, cfg)
        print(f"\n=== {prod} id={oid} cfg={cid}")
        agg = await fetch_aggregate(c, oid, cid, ptype, ref)
        print("  aggregate:", json.dumps({k:v for k,v in agg.items() if k!='distributions'}, ensure_ascii=False))
        tags = await fetch_rating_tags(c, oid, cid, ptype, ref)
        print("  tags:", len(tags), [ (t['label'], t['count']) for t in tags[:4] ])
        cnt = await fetch_count(c, oid, cid, ptype, ref, {})
        print("  count:", cnt)
        rv = await fetch_reviews(c, oid, cid, ptype, ref, 45, 20,
                                 "SORT_RATING_ASCENDING", {}, [], agg.get("objectName"))
        print("  reviews:", len(rv), "scores:", [x['score'] for x in rv[:8]])
        ids = [x['reviewId'] for x in rv]
        print("  unique ids:", len(set(ids)) == len(ids))
        s = rv[0]
        print("  sample:", json.dumps({k:s[k] for k in ('reviewId','reviewedAt','score','reviewerName','mediaCount','isMachineTranslated')}, ensure_ascii=False))
        print("  text:", (s.get('text') or '')[:120])

asyncio.run(main())
