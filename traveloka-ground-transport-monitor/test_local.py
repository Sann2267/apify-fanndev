import asyncio, datetime as dt, json, logging
logging.basicConfig(level=logging.INFO)
from src.client import TravelokaClient
from src.transport import resolve_location, search_departures, summarise_route

async def main():
    c = TravelokaClient(request_delay=0.4); c.bootstrap()
    o = await resolve_location(c, "Jakarta"); d = await resolve_location(c, "Bandung")
    print("origin:", o); print("dest:", d)
    route = {"originCode": o["code"], "originType": o["type"],
             "destinationCode": d["code"], "destinationType": d["type"],
             "originQuery": "Jakarta", "destinationQuery": "Bandung",
             "label": f"{o['label']} - {d['label']}"}
    day = dt.date.today() + dt.timedelta(days=10)
    deps, raw = await search_departures(c, route, day, 1, 40, "trip", [])
    print(f"raw={raw} kept={len(deps)}")
    for x in deps[:3]:
        print("  ", json.dumps({k: x[k] for k in
              ("operatorName","productType","departureTime","arrivalTime",
               "durationMinutes","fare","originalFare","discountPercent",
               "seatsAvailable","pickupPointName","pickupLatitude","operatorRating")},
              ensure_ascii=False))
    s = summarise_route(deps, route, day.isoformat(), raw)
    print("summary:", json.dumps({k: v for k, v in s.items() if k != "operators"},
                                 ensure_ascii=False))
    print("top operators:", json.dumps(s["operators"][:3], ensure_ascii=False))
    nodep, nraw = await search_departures(c, {**route, "destinationCode": o["code"],
        "destinationType": o["type"], "destinationQuery": "Jakarta"}, day, 1, 10, "trip", [])
    print("same-city search:", len(nodep), nraw)

asyncio.run(main())
