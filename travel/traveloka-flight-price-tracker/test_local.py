import asyncio, datetime as dt, json, logging
logging.basicConfig(level=logging.INFO)
from src.client import TravelokaClient
from src.flights import monthly_curve, price_grid, resolve_airport, summarise, _grid_chunks

async def main():
    c = TravelokaClient(request_delay=0.3); c.bootstrap()
    print("chunks 10x10:", _grid_chunks(10,10))
    print("chunks 20x10:", _grid_chunks(20,10))
    print("chunks 30x14:", _grid_chunks(30,14))
    o = await resolve_airport(c, "CGK"); d = await resolve_airport(c, "Denpasar")
    print("origin:", o); print("dest:", d)
    start = dt.date.today()+dt.timedelta(days=30)
    m = await monthly_curve(c, o, d, "TWO_WAY", start)
    print("monthly entries:", len(m))
    for x in m[:4]: print("  ", x)
    g = await price_grid(c, o, d, start, 10, start+dt.timedelta(days=7), 10,
                         "ECONOMY", 1, 0, 0, "en-id")
    print("grid cells:", len(g))
    for x in g[:4]: print("  ", x)
    print("summary:", json.dumps(summarise(m, g, 2000000), indent=2))
    bad = await resolve_airport(c, "zzzzqqq")
    print("bogus resolve ->", bad)

asyncio.run(main())
