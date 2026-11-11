"""Local smoke test: runs the scraping core without the Apify runtime."""
import asyncio, json, logging, sys, datetime as dt
logging.basicConfig(level=logging.INFO)
from src.client import TravelokaClient
from src.hotels import months_from, scrape_hotel
from src.resolver import hotel_id_from_url, resolve_query

async def main():
    c = TravelokaClient(locale="en-id", currency="IDR", request_delay=0.3)
    c.bootstrap()
    print("URL parse:", hotel_id_from_url("https://www.traveloka.com/id-id/hotel/indonesia/hotel-borobudur-jakarta-7584"))
    hotels, geos = await resolve_query(c, "Hotel Borobudur Jakarta", 5, "en-id", "IDR")
    print("autocomplete hotels:", [(h.get("id"), h.get("name")) for h in hotels][:3])
    ci = dt.date.today() + dt.timedelta(days=30)
    parts = lambda d: {"year": str(d.year), "month": str(d.month), "day": str(d.day)}
    opts = {
        "stay": {"checkInDate": parts(ci), "checkOutDate": parts(ci+dt.timedelta(days=1)),
                 "numOfNights":1,"numAdults":2,"numChildren":0,"childAges":[],
                 "numInfants":0,"numRooms":1,"currency":"IDR"},
        "months": months_from(ci, 1), "adults": 2, "rooms": 1,
        "includeRooms": True, "includeCalendar": True, "includeReviewSummary": True,
    }
    hid = str(hotels[0]["id"]) if hotels else "2000000113168"
    rec = await scrape_hotel(c, hid, opts)
    print("\n=== record", rec.get("recordType"), rec.get("name"))
    for k in ("hotelId","accommodationType","starRating","city","latitude","longitude",
              "checkInTime","roomCount","currency","url"):
        print(f"  {k}: {rec.get(k)}")
    print("  facilities:", len(rec.get("facilityNames") or []))
    print("  images:", len(rec.get("images") or []))
    print("  reviewSummary:", rec.get("reviewSummary"))
    print("  priceSummary:", json.dumps(rec.get("priceSummary"), indent=2))
    cal = rec.get("priceCalendar") or []
    print("  calendar nights:", len(cal))
    for n in cal[:4]: print("    ", n)
    print("  rooms sample:", json.dumps((rec.get("rooms") or [{}])[0], ensure_ascii=False)[:340])
    print("  warnings:", rec.get("warnings"))
    bad = await scrape_hotel(c, "999999999999", opts)
    print("\nbogus id ->", bad.get("recordType"), str(bad.get("error"))[:120])

asyncio.run(main())
