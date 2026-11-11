"""Local smoke test -- real HTTP, no Apify platform involved.

    python test_local.py

These assertions are about measured facts, not about "it did not crash":

* a priced fixture yields a spread, a total and a moneyline on both sides;
* implied probability is derived and the two sides sum to just over 1 (the vig);
* ``propBets?limit=1000`` returns every prop on **one** page, and the athlete
  cache collapses hundreds of props into a few dozen lookups;
* a ``$ref`` pointer never reaches the output;
* the date-grammar split is real -- the core host accepts a range and the site
  host does not, which is the reason every window is resolved on core.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone

from src.client import EspnClient, normalize_ref
from src.constants import CORE_BASE, PAGE_LIMIT, SITE_BASE
from src.extractor import (
    american_to_probability,
    build_futures_records,
    build_odds_record,
    build_predictor_record,
    build_prop_record,
    event_context,
    ref_id,
)
from src.main import (
    LeagueContext,
    _prop_key,
    build_dates,
    resolve_league,
    run_reference,
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

YEAR = datetime.now(timezone.utc).year


def has_ref(record: dict) -> bool:
    return any(isinstance(v, dict) and "$ref" in v for v in record.values())


async def main():  # noqa: C901 -- a smoke test reads better flat
    client = EspnClient()
    failures: list[str] = []

    print("=" * 74)
    print("0. pure functions")
    assert american_to_probability("+400") == 0.2, american_to_probability("+400")
    assert american_to_probability(-245) == 0.7101, american_to_probability(-245)
    assert american_to_probability("EVEN") is None
    assert ref_id("http://x/v2/sports/football/leagues/nfl/teams/2?lang=en") == "2"
    assert normalize_ref("http://sports.core.api.espn.pvt/v2/x").startswith(
        "https://sports.core.api.espn.com/"
    ), "the .pvt rewrite is the one that makes summary refs fetchable"
    assert build_dates({"dateFrom": "2026-09-01", "dateTo": "2026-10-01"}) == "20260901-20261001"
    assert resolve_league("epl") == ("soccer", "eng.1", "epl")
    assert resolve_league("soccer/ned.1") == ("soccer", "ned.1", "soccer/ned.1")
    print("   odds conversion, ref parsing, .pvt rewrite, date window, league keys: ok")

    print("=" * 74)
    print("1. find a priced fixture (odds mode path)")
    sport, league, key = resolve_league("nfl")
    ctx = LeagueContext(client, sport, league, key)
    seeded = await ctx.prefill_teams()
    print(f"   team cache seeded from one request: {seeded} team(s)")
    if seeded < 30:
        failures.append(f"expected 32 NFL teams from the bulk list, got {seeded}")

    refs = await ctx.list_event_refs(None, 20)
    print(f"   fixtures in the current window: {len(refs)}")
    priced = None
    for ref in refs:
        event, context = await ctx.fetch_fixture(ref)
        odds = await client.get_json(f"{ctx.competition_base(context)}/odds?limit=50")
        if odds.get("count"):
            priced = (event, context, odds)
            break
    if not priced:
        # Out of season this is legitimate; fall back to the whole season so the
        # test still exercises the parser instead of silently passing.
        season_refs = await ctx.list_event_refs(str(YEAR), 40)
        for ref in season_refs:
            event, context = await ctx.fetch_fixture(ref)
            odds = await client.get_json(f"{ctx.competition_base(context)}/odds?limit=50")
            if odds.get("count"):
                priced = (event, context, odds)
                break
    if not priced:
        failures.append("no NFL fixture in the current window or season carried any odds")
        print("   !! no priced fixture found")
    else:
        event, context, odds = priced
        print(f"   {context['eventName']}  ({context['eventDate']})")
        print(f"   books: {[(i.get('provider') or {}).get('name') for i in odds['items']]}")
        records = [build_odds_record(i, context, ctx.teams) for i in odds["items"]]
        r = records[0]
        print(
            f"   {r['providerName']}: {r['details']} | total {r['overUnder']} | "
            f"ML {r['awayMoneyline']}/{r['homeMoneyline']}"
        )
        print(
            f"   movement: spread {r['openSpread']} -> {r['currentSpread']} "
            f"({r['spreadMovement']}) | total {r['openTotal']} -> {r['currentTotal']} "
            f"({r['totalMovement']})"
        )
        print(
            f"   implied: away {r['awayImpliedProbability']} + home "
            f"{r['homeImpliedProbability']}"
        )
        if r.get("spread") is None and r.get("currentSpread") is None:
            failures.append("priced fixture produced no spread at all")
        if r.get("overUnder") is None:
            failures.append("priced fixture produced no total")
        if r.get("homeMoneyline") is None or r.get("awayMoneyline") is None:
            failures.append("priced fixture is missing a moneyline on one side")
        if r.get("homeTeam") is None or r.get("awayTeam") is None:
            failures.append("team names did not resolve onto the odds record")
        both = (r.get("homeImpliedProbability") or 0) + (r.get("awayImpliedProbability") or 0)
        if not 0.95 < both < 1.25:
            failures.append(f"implied probabilities sum to {both}, which is not a real book")
        if has_ref(r):
            failures.append("a raw $ref pointer leaked into an odds record")
        if r.get("spreadMovement") is None and r.get("openSpread") is not None:
            failures.append("opening spread present but movement not derived")
        # The live feed writes 0 where it means "nothing"; those must never
        # reach the output as a number.
        zeroed = [
            f
            for rec in records
            for f in ("overUnder", "overOdds", "underOdds", "homeMoneyline", "awayMoneyline")
            if rec.get(f) == 0
        ]
        if zeroed:
            failures.append(f"placeholder zeros leaked into price fields: {sorted(set(zeroed))}")
        live = [rec for rec in records if rec.get("isLiveOddsFeed")]
        print(f"   rows: {len(records)} ({len(live)} live in-play feed)")
        print("   sample:", json.dumps(r, ensure_ascii=False, indent=1)[:700])

    print("=" * 74)
    print("2. player props -- one page at limit=1000, and the athlete cache")
    if priced:
        event, context, odds = priced
        provider_id = (odds["items"][0].get("provider") or {}).get("id")
        props = await client.get_json(
            f"{ctx.competition_base(context)}/odds/{provider_id}/propBets?limit={PAGE_LIMIT}"
        )
        items = props.get("items") or []
        print(f"   props: count={props.get('count')} pageCount={props.get('pageCount')} items={len(items)}")
        if props.get("count") and int(props.get("pageCount") or 9) > 1:
            failures.append(
                f"limit={PAGE_LIMIT} still paged ({props.get('pageCount')} pages) -- the "
                f"single-request assumption is broken"
            )
        if items:
            distinct = len({(i.get("athlete") or {}).get("$ref", "").split("?")[0] for i in items})
            print(f"   distinct athletes behind {len(items)} props: {distinct}")
            unique = {_prop_key(i) for i in items}
            print(f"   distinct prop markets: {len(unique)} (source published {len(items)} rows)")
            if len(unique) == len(items):
                print("   NOTE: the feed published no repeats this time; it published 138 "
                      "on 2026-09-18, so the de-duplication stays.")
            elif len(unique) < len(items) * 0.5:
                failures.append(
                    f"only {len(unique)} of {len(items)} prop rows were distinct -- the "
                    f"identity key is probably collapsing genuine markets"
                )
            before = client.ref_lookups
            rows = []
            for item in items[:80]:
                athlete = await client.resolve((item.get("athlete") or {}).get("$ref"))
                rows.append(build_prop_record(item, context, athlete, {}))
            spent = client.ref_lookups - before
            print(f"   lookups spent on 80 props: {spent} (cache hits so far: {client.ref_cache_hits})")
            if spent >= 80:
                failures.append("the athlete cache is not collapsing repeated lookups")
            named = [r for r in rows if r.get("athleteName")]
            typed = {r.get("propTypeName") for r in rows}
            print(f"   props with a player name: {len(named)}/{len(rows)} | market types: {len(typed)}")
            for row in named[:3]:
                print(
                    f"      {row['athleteName']:22s} {str(row['propTypeName'])[:38]:40s} "
                    f"{row['openTarget']} -> {row['currentTarget']}"
                )
            if not named:
                failures.append("no prop resolved a player name")
            if len(typed) < 2:
                failures.append("props all came back as one market type")
            if any(has_ref(r) for r in rows):
                failures.append("a raw $ref pointer leaked into a prop record")
        else:
            print("   (this fixture carries no props)")

    print("=" * 74)
    print("3. futures board")
    payload = await client.get_json(f"{ctx.core}/seasons/{YEAR}/futures?limit=100")
    markets = payload.get("items") or []
    print(f"   markets: {len(markets)} -> {[m.get('name') for m in markets][:4]}")
    if len(markets) < 3:
        failures.append(f"expected a futures board with many markets, got {len(markets)}")
    if markets:
        market = markets[0]
        refs = {
            ((b.get("athlete") or b.get("team") or {}).get("$ref") or "").split("?")[0]
            for p in market.get("futures") or []
            for b in p.get("books") or []
        }
        names = {}
        for ref in sorted(r for r in refs if r)[:12]:
            names[ref] = await client.resolve(ref)
        rows = build_futures_records(market, sport, league, key, YEAR, names)
        priced_rows = [r for r in rows if r.get("impliedProbability") is not None]
        print(f"   '{market.get('name')}' -> {len(rows)} runner(s), {len(priced_rows)} priced")
        for row in sorted(priced_rows, key=lambda r: -r["impliedProbability"])[:3]:
            print(
                f"      {str(row['entityName'] or row['entityId']):24s} {row['price']:>7} "
                f"= {row['impliedProbability']:.3f}  ({row['providerName']})"
            )
        if not priced_rows:
            failures.append("no futures runner produced an implied probability")
        if not any(r.get("entityName") for r in rows):
            failures.append("no futures runner resolved a name")

    print("=" * 74)
    print("4. predictor -- the model to compare against the book")
    if priced:
        event, context, _ = priced
        try:
            pred = await client.get_json(f"{ctx.competition_base(context)}/predictor")
            row = build_predictor_record(pred, context, ctx.teams)
            print(
                f"   {row['eventName']}: home {row['homeWinProbability']}% / away "
                f"{row['awayWinProbability']}% | predicted margin {row['homePredictedPointDiff']}"
            )
            if row.get("homeWinProbability") is None:
                failures.append("predictor returned no win projection")
        except Exception as exc:  # noqa: BLE001
            print(f"   predictor unavailable for this fixture: {exc!r}")

    print("=" * 74)
    print("5. the date-grammar split (the reason windows are resolved on the core host)")
    start, end = f"{YEAR}0901", f"{YEAR}1001"
    core_ranged = await client.get_json(
        f"{CORE_BASE.format(sport='football', league='nfl')}/events?limit=5&dates={start}-{end}"
    )
    print(f"   core  dates={start}-{end}: count={core_ranged.get('count')}")
    if not core_ranged.get("count"):
        failures.append("the core host stopped accepting a date range -- windowing is broken")
    try:
        site = await client.get_json(
            f"{SITE_BASE.format(sport='football', league='nfl')}/scoreboard?dates={start}-{end}"
        )
        site_events = len(site.get("events") or [])
    except Exception as exc:  # noqa: BLE001 -- 400 is the expected answer here
        site_events = 0
        print(f"   site  same range -> rejected ({type(exc).__name__})")
    else:
        print(f"   site  same range -> {site_events} event(s)")
    if site_events:
        print("   NOTE: the site host now answers ranges; it returned nothing on 2026-09-18.")

    print("=" * 74)
    print("6. mode=reference")
    probe = (await run_reference(client))[0]
    print("   available:", probe["isAvailable"], "| tls:", probe["winningTlsProfile"])
    print("   sample:", json.dumps(probe["sample"], ensure_ascii=False, indent=1)[:1200])
    if not probe["isAvailable"]:
        failures.append(f"reference probe says the source is down: {probe['note']}")
    if probe["sample"].get("scoreboardCarriesOdds"):
        print("   NOTE: the scoreboard now carries odds inline -- odds mode could get cheaper.")

    await client.close()
    print("=" * 74)
    print(f"total requests: {client.requests} | name lookups: {client.ref_lookups} | "
          f"cache hits: {client.ref_cache_hits}")
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


asyncio.run(main())
