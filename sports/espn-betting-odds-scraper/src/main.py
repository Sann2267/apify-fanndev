"""Mode dispatch for the ESPN betting-odds Actor.

Every mode starts from the same place -- a list of fixtures resolved on the
**core** host, because that is the only one whose date grammar accepts a range
(see ``constants``). From there:

* ``odds``      -- one row per fixture per sportsbook, with the spread and total
                   movement since the book opened, which upstream does not publish.
* ``props``     -- player prop markets, ~659 per NFL game from 47 athletes.
* ``futures``   -- season markets (MVP, championship, divisions) with implied
                   probability per runner.
* ``events``    -- the schedule alone, no odds, for cheap calendar pulls.
* ``predictor`` -- ESPN's own BPI win projection, to compare against the book.
* ``providers`` -- the sportsbook catalogue for a league.
* ``reference`` -- probes the source and re-tests the design assumptions this
                   Actor rests on, per the portfolio convention: the prop page
                   ceiling, the SITE host's silent rejection of date ranges, and
                   whether the scoreboard still withholds odds.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from apify import Actor

from src.client import Blocked, EspnClient, NotFound, normalize_ref
from src.constants import (
    CORE_BASE,
    CORE_LEAGUES,
    CORE_SPORTS,
    DEFAULT_REF_BUDGET,
    EXPECTED,
    LEAGUES,
    LEAGUES_WITH_ODDS_SEEN,
    MODES,
    PAGE_LIMIT,
    SITE_BASE,
)
from src.extractor import (
    build_event_record,
    build_futures_records,
    build_no_odds_record,
    build_odds_record,
    build_predictor_record,
    build_prop_record,
    build_provider_record,
    event_context,
    extract_error,
    ref_id,
    wrap_reference,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


def envelope(record: dict, input_value: str) -> dict:
    record.setdefault("_input", input_value)
    record.setdefault("_source", "none")
    record.setdefault("recordType", "ODDS")
    record["_scrapedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return record


def resolve_league(raw: str) -> tuple[str, str, str]:
    """'nfl', 'soccer/ned.1' or 'football/nfl' -> (sport, league, key-as-given)."""
    value = (raw or "").strip().lower()
    if not value:
        raise ValueError("Provide a league, e.g. 'nfl', 'epl' or 'soccer/ned.1'.")
    if value in LEAGUES:
        sport, league = LEAGUES[value]
        return sport, league, value
    if "/" in value:
        sport, league = value.split("/", 1)
        if sport and league:
            return sport, league, value
    raise ValueError(
        f"Unknown league {raw!r}. Use one of {sorted(LEAGUES)} or the ESPN form "
        f"'sport/league' such as 'soccer/ned.1'."
    )


def build_dates(input_data: dict) -> str | None:
    """CORE accepts YYYYMMDD, YYYY and YYYYMMDD-YYYYMMDD. SITE does not -- see constants."""
    explicit = (input_data.get("dates") or "").strip()
    if explicit:
        return explicit
    start = (input_data.get("dateFrom") or "").strip().replace("-", "")
    end = (input_data.get("dateTo") or "").strip().replace("-", "")
    if start and end:
        return f"{start}-{end}"
    return start or end or None


class LeagueContext:
    """Per-league fixture discovery and the team-name cache."""

    def __init__(self, client: EspnClient, sport: str, league: str, league_key: str):
        self.client = client
        self.sport = sport
        self.league = league
        self.league_key = league_key
        self.core = CORE_BASE.format(sport=sport, league=league)
        self.site = SITE_BASE.format(sport=sport, league=league)
        self.teams: dict[str, dict] = {}

    async def prefill_teams(self) -> int:
        """One SITE request hands over every team in the league.

        Best-effort: competition-style leagues (UFC, golf, tennis) have no team
        list and answer 404. Records then fall back to per-team ``$ref`` lookups,
        which are cached, so nothing is lost beyond a few requests.
        """
        try:
            payload = await self.client.get_json(f"{self.site}/teams")
        except (NotFound, Blocked) as exc:
            log.info(f"no bulk team list for {self.league_key} ({exc}); resolving per event")
            return 0
        entries = []
        for sport_block in payload.get("sports") or []:
            for league_block in sport_block.get("leagues") or []:
                entries.extend(league_block.get("teams") or [])
        for entry in entries:
            team = entry.get("team") or {}
            if team.get("id"):
                self.teams[str(team["id"])] = team
        return len(self.teams)

    async def ensure_teams(self, context: dict) -> None:
        """Fill in the two teams of one fixture if the bulk list did not cover them."""
        for side in ("home", "away"):
            team_id = context.get(f"{side}TeamId")
            if not team_id or team_id in self.teams:
                continue
            ref = f"{self.core}/seasons/{context.get('seasonYear')}/teams/{team_id}"
            team = await self.client.resolve(ref)
            if team:
                self.teams[str(team_id)] = team

    async def list_event_refs(self, dates: str | None, cap: int) -> list[str]:
        """Fixture pointers for a date window. No ``dates`` means the current week only."""
        refs: list[str] = []
        page = 1
        while len(refs) < cap:
            url = f"{self.core}/events?limit={PAGE_LIMIT}&page={page}"
            if dates:
                url += f"&dates={dates}"
            payload = await self.client.get_json(url)
            items = payload.get("items") or []
            if not items:
                break
            refs.extend(normalize_ref(item.get("$ref")) for item in items if item.get("$ref"))
            if page >= int(payload.get("pageCount") or 1):
                break
            page += 1
        return [r for r in refs if r][:cap]

    async def fetch_fixture(self, ref: str) -> tuple[dict, dict]:
        """``(event payload, context)`` -- the one request every mode needs."""
        event = await self.client.get_json(ref)
        context = event_context(event, self.sport, self.league, self.league_key)
        await self.ensure_teams(context)
        return event, context

    def competition_base(self, context: dict) -> str:
        return (
            f"{self.core}/events/{context['eventId']}/competitions/"
            f"{context['competitionId'] or context['eventId']}"
        )


async def gather_fixtures(
    ctx: LeagueContext, input_data: dict, max_events: int, concurrency: int = 4
) -> list[tuple[dict, dict]]:
    """Event ids given explicitly, otherwise everything in the date window.

    The list endpoint hands back pointers, so each fixture costs one request on
    top of the list -- ``maxEvents`` is what stops a whole-season window from
    turning into hundreds of them.
    """
    explicit = [str(v).strip() for v in (input_data.get("eventIds") or []) if str(v).strip()]
    if input_data.get("eventId"):
        explicit.insert(0, str(input_data["eventId"]).strip())
    if explicit:
        refs = [f"{ctx.core}/events/{eid}" for eid in dict.fromkeys(explicit)][:max_events]
    else:
        refs = await ctx.list_event_refs(build_dates(input_data), max_events)

    sem = asyncio.Semaphore(concurrency)

    async def one(ref: str):
        async with sem:
            try:
                return await ctx.fetch_fixture(ref)
            except NotFound:
                log.warning(f"fixture not found: {ref}")
            except Blocked as exc:
                log.warning(f"fixture blocked: {ref} -- {exc}")
            return None

    fixtures = await asyncio.gather(*(one(ref) for ref in refs))
    return [f for f in fixtures if f]


# -- modes -----------------------------------------------------------------


async def run_odds(ctx: LeagueContext, input_data: dict, max_items: int, max_events: int, concurrency: int, push):
    fixtures = await gather_fixtures(ctx, input_data, max_events, concurrency)
    include_empty = bool(input_data.get("includeUnpricedEvents", True))
    sem = asyncio.Semaphore(concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(event: dict, context: dict):
        nonlocal pushed
        async with sem:
            try:
                payload = await ctx.client.get_json(f"{ctx.competition_base(context)}/odds?limit=50")
            except (NotFound, Blocked) as exc:
                await push([extract_error(context["eventId"] or "?", "odds_fetch_failed", repr(exc))])
                return
        items = payload.get("items") or []
        if not items:
            if include_empty:
                async with lock:
                    if pushed < max_items:
                        await push(
                            [
                                build_no_odds_record(
                                    context,
                                    ctx.teams,
                                    "HTTP 200 with an empty provider list -- books price this "
                                    "fixture closer to start time. Not a block.",
                                )
                            ]
                        )
                        pushed += 1
            return
        records = [build_odds_record(item, context, ctx.teams) for item in items]
        async with lock:
            room = max_items - pushed
            if room > 0:
                await push(records[:room])
                pushed += len(records[:room])

    await asyncio.gather(*(one(event, context) for event, context in fixtures))
    return pushed, len(fixtures)


def _prop_key(item: dict) -> tuple:
    """Identity of a prop market, used to drop the feed's exact repeats.

    One NFL game returned 659 rows of which 521 were distinct -- 138 were byte
    identical down to ``lastUpdated``. Counting rows would report 659 markets
    where the book offers 521.
    """
    return (
        (item.get("athlete") or {}).get("$ref", "").split("?")[0],
        (item.get("team") or {}).get("$ref", "").split("?")[0],
        str((item.get("type") or {}).get("id")),
        json.dumps(item.get("current"), sort_keys=True),
        json.dumps(item.get("open"), sort_keys=True),
        item.get("lastUpdated"),
    )


async def run_props(ctx: LeagueContext, input_data: dict, max_items: int, max_events: int, concurrency: int, push):
    fixtures = await gather_fixtures(ctx, input_data, max_events, concurrency)
    sem = asyncio.Semaphore(concurrency)
    pushed = 0
    duplicates = 0
    lock = asyncio.Lock()

    async def one(event: dict, context: dict):
        nonlocal pushed, duplicates
        base = ctx.competition_base(context)
        async with sem:
            try:
                odds = await ctx.client.get_json(f"{base}/odds?limit=50")
            except (NotFound, Blocked) as exc:
                await push([extract_error(context["eventId"] or "?", "odds_fetch_failed", repr(exc))])
                return
        providers = [
            str((item.get("provider") or {}).get("id"))
            for item in odds.get("items") or []
            if (item.get("provider") or {}).get("id") is not None
        ]
        if not providers:
            return
        for provider_id in dict.fromkeys(providers):
            async with sem:
                try:
                    payload = await ctx.client.get_json(
                        f"{base}/odds/{provider_id}/propBets?limit={PAGE_LIMIT}"
                    )
                except (NotFound, Blocked):
                    continue
            items = payload.get("items") or []
            seen: set[tuple] = set()
            records = []
            for item in items:
                # Stop resolving names once the run is full -- a budget spent on
                # rows that will be trimmed is a request nobody gets to keep.
                if len(records) >= max(0, max_items - pushed):
                    break
                key = _prop_key(item)
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                athlete = await ctx.client.resolve((item.get("athlete") or {}).get("$ref"))
                team_ref = (item.get("team") or {}).get("$ref")
                team = ctx.teams.get(ref_id(team_ref) or "") or (
                    await ctx.client.resolve(team_ref) if team_ref else {}
                )
                records.append(build_prop_record(item, context, athlete, team, ctx.teams))
            if duplicates:
                log.info(
                    f"{context['eventName']} / book {provider_id}: kept {len(records)} distinct "
                    f"prop market(s) out of {len(items)} row(s) returned"
                )
            async with lock:
                room = max_items - pushed
                if room > 0 and records:
                    await push(records[:room])
                    pushed += len(records[:room])

    await asyncio.gather(*(one(event, context) for event, context in fixtures))
    if duplicates:
        log.info(f"dropped {duplicates} exact duplicate prop row(s) published by the source")
    return pushed, len(fixtures)


async def run_futures(ctx: LeagueContext, input_data: dict, max_items: int, concurrency: int, push):
    season = int(input_data.get("season") or datetime.now(timezone.utc).year)
    payload = await ctx.client.get_json(f"{ctx.core}/seasons/{season}/futures?limit=100")
    markets = payload.get("items") or []
    pushed = 0
    sem = asyncio.Semaphore(concurrency)

    async def named(ref: str) -> tuple[str, dict]:
        async with sem:
            return ref, await ctx.client.resolve(ref)

    for market in markets:
        refs = {
            ((book.get("athlete") or book.get("team") or {}).get("$ref") or "").split("?")[0]
            for provider in market.get("futures") or []
            for book in provider.get("books") or []
        }
        names = dict(await asyncio.gather(*(named(r) for r in sorted(refs) if r)))
        rows = build_futures_records(
            market, ctx.sport, ctx.league, ctx.league_key, season, names
        )
        room = max_items - pushed
        if room <= 0:
            break
        await push(rows[:room])
        pushed += len(rows[:room])
    return pushed, len(markets)


async def run_events(ctx: LeagueContext, input_data: dict, max_items: int, max_events: int, concurrency: int, push):
    fixtures = await gather_fixtures(ctx, input_data, max_events, concurrency)
    sem = asyncio.Semaphore(concurrency)
    records: list[dict] = []
    lock = asyncio.Lock()

    async def one(event: dict, context: dict):
        status = {}
        async with sem:
            try:
                status = await ctx.client.get_json(
                    f"{ctx.competition_base(context)}/status", allow_404=True
                )
            except (NotFound, Blocked):
                status = {}
        async with lock:
            records.append(build_event_record(event, context, ctx.teams, status))

    await asyncio.gather(*(one(event, context) for event, context in fixtures))
    records.sort(key=lambda r: (r.get("eventDate") or ""))
    await push(records[:max_items])
    return len(records[:max_items]), len(fixtures)


async def run_predictor(ctx: LeagueContext, input_data: dict, max_items: int, max_events: int, concurrency: int, push):
    fixtures = await gather_fixtures(ctx, input_data, max_events, concurrency)
    sem = asyncio.Semaphore(concurrency)
    records: list[dict] = []
    lock = asyncio.Lock()

    async def one(event: dict, context: dict):
        async with sem:
            try:
                payload = await ctx.client.get_json(f"{ctx.competition_base(context)}/predictor")
            except (NotFound, Blocked):
                return
        if not payload:
            return
        async with lock:
            records.append(build_predictor_record(payload, context, ctx.teams))

    await asyncio.gather(*(one(event, context) for event, context in fixtures))
    await push(records[:max_items])
    return len(records[:max_items]), len(fixtures)


async def run_providers(ctx: LeagueContext, max_items: int, push):
    payload = await ctx.client.get_json(f"{ctx.core}/providers?limit=200")
    records = []
    for item in (payload.get("items") or [])[:max_items]:
        detail = await ctx.client.resolve(item.get("$ref"))
        if detail:
            records.append(
                build_provider_record(detail, ctx.sport, ctx.league, ctx.league_key)
            )
    await push(records)
    return len(records), int(payload.get("count") or 0)


async def run_reference(client: EspnClient) -> list[dict]:
    """Probe the source and re-test the assumptions this Actor's design rests on."""
    core = CORE_BASE.format(sport="football", league="nfl")
    sample: dict = {}
    try:
        catalogue = await client.get_json(CORE_SPORTS)
        sample["sportsInCatalogue"] = catalogue.get("count")
        soccer = await client.get_json(CORE_LEAGUES.format(sport="soccer"))
        sample["soccerCompetitions"] = soccer.get("count")

        season = await client.get_json(f"{core}/events?limit=1&dates={datetime.now(timezone.utc).year}")
        sample["nflEventsThisSeason"] = season.get("count")
        sample["expectedNflEventsInSeason"] = EXPECTED["nflEventsInSeason"]

        # Assumption 1: the CORE host still accepts a date range, and SITE still
        # does not. SITE answering 200-with-zero-events is the dangerous case.
        start = f"{datetime.now(timezone.utc).year}0901"
        end = f"{datetime.now(timezone.utc).year}1001"
        ranged = await client.get_json(f"{core}/events?limit=5&dates={start}-{end}")
        sample["coreAcceptsDateRange"] = bool(ranged.get("count"))
        sample["coreRangeCount"] = ranged.get("count")
        try:
            site = await client.get_json(
                SITE_BASE.format(sport="football", league="nfl") + f"/scoreboard?dates={start}-{end}"
            )
            sample["siteRangeEvents"] = len(site.get("events") or [])
            sample["siteRejectsDateRange"] = not site.get("events")
        except NotFound as exc:
            sample["siteRangeEvents"] = 0
            sample["siteRejectsDateRange"] = True
            sample["siteRangeError"] = str(exc)[:160]

        # Assumption 2: the scoreboard still withholds odds, so odds must come
        # from CORE. If this ever flips, one request replaces N.
        board = await client.get_json(
            SITE_BASE.format(sport="football", league="nfl") + "/scoreboard"
        )
        events = board.get("events") or []
        sample["scoreboardEvents"] = len(events)
        sample["scoreboardCarriesOdds"] = bool(
            events and (events[0].get("competitions") or [{}])[0].get("odds")
        )

        # Assumption 3: a priced fixture still yields providers and props, and
        # propBets still returns everything on one page at limit=1000.
        priced = None
        for event in events[:6]:
            competition = (event.get("competitions") or [{}])[0]
            odds = await client.get_json(
                f"{core}/events/{event['id']}/competitions/{competition.get('id', event['id'])}/odds?limit=50"
            )
            if odds.get("count"):
                priced = (event, competition, odds)
                break
        if priced:
            event, competition, odds = priced
            provider_id = (odds["items"][0].get("provider") or {}).get("id")
            sample["pricedFixture"] = event.get("name")
            sample["providersOnFixture"] = odds.get("count")
            sample["providerNames"] = [
                (item.get("provider") or {}).get("name") for item in odds["items"]
            ]
            props = await client.get_json(
                f"{core}/events/{event['id']}/competitions/{competition.get('id', event['id'])}"
                f"/odds/{provider_id}/propBets?limit={PAGE_LIMIT}"
            )
            sample["propsOnFixture"] = props.get("count")
            sample["propPagesAtLimit1000"] = props.get("pageCount")
            sample["propsAllOnOnePage"] = int(props.get("pageCount") or 0) <= 1
            sample["distinctPropAthletes"] = len(
                {
                    (item.get("athlete") or {}).get("$ref", "").split("?")[0]
                    for item in props.get("items") or []
                    if item.get("athlete")
                }
            )
            sample["expectedPropsPerNflGame"] = EXPECTED["nflPropsPerGame"]
        else:
            sample["pricedFixture"] = None
            sample["note"] = (
                "no fixture on today's scoreboard carries odds -- outside the season, or "
                "the books have not posted lines yet"
            )

        futures = await client.get_json(
            f"{core}/seasons/{datetime.now(timezone.utc).year}/futures?limit=100"
        )
        sample["futuresMarkets"] = futures.get("count")
        providers = await client.get_json(f"{core}/providers?limit=200")
        sample["providerCatalogue"] = providers.get("count")
        sample["requestsSpent"] = client.requests

        note = "payload parsed"
        if sample.get("scoreboardCarriesOdds"):
            note += (
                " -- NOTE: the scoreboard now carries odds inline, which it did not on "
                "2026-09-18. Odds mode could drop to one request per date instead of one "
                "per fixture."
            )
        if sample.get("siteRangeEvents"):
            note += (
                " -- NOTE: the SITE host now answers date ranges; it returned zero events "
                "for the same query on 2026-09-18."
            )
        return [wrap_reference(core, True, note, sample, client.winning_profile)]
    except Exception as exc:  # noqa: BLE001 -- a probe reports, it never raises
        return [wrap_reference(core, False, repr(exc), sample, client.winning_profile)]


# -- entrypoint ------------------------------------------------------------


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "odds")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 500))
        concurrency = int(input_data.get("maxConcurrency", 4))
        max_events = int(input_data.get("maxEvents", 60))
        ref_budget = int(input_data.get("maxNameLookups", DEFAULT_REF_BUDGET))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None

        client = EspnClient(
            proxy_url=proxy_url,
            profile=input_data.get("tlsProfile") or None,
            ref_budget=ref_budget,
        )

        async def push(records: list[dict]):
            if records:
                await Actor.push_data(
                    [envelope(r, str(input_data.get("league") or mode)) for r in records]
                )

        try:
            if mode == "reference":
                records = await run_reference(client)
                Actor.log.info(
                    f"mode=reference available={records[0].get('isAvailable')} "
                    f"tls={records[0].get('winningTlsProfile')} {records[0].get('sample')}"
                )
                await Actor.push_data([envelope(r, "reference") for r in records])
                return

            sport, league, league_key = resolve_league(input_data.get("league") or "nfl")
            ctx = LeagueContext(client, sport, league, league_key)
            if mode in ("odds", "props", "events", "predictor"):
                seeded = await ctx.prefill_teams()
                Actor.log.info(f"team cache: {seeded} team(s) for {league_key}")
            if mode in ("odds", "props") and league_key not in LEAGUES_WITH_ODDS_SEEN:
                Actor.log.info(
                    f"{league_key} was not carrying betting lines during recon. Coverage "
                    f"follows the season, so this may still work -- records with "
                    f"hasOdds=false mean the books have not priced the fixture."
                )

            if mode == "odds":
                pushed, fixtures = await run_odds(ctx, input_data, max_items, max_events, concurrency, push)
            elif mode == "props":
                pushed, fixtures = await run_props(ctx, input_data, max_items, max_events, concurrency, push)
            elif mode == "futures":
                pushed, fixtures = await run_futures(ctx, input_data, max_items, concurrency, push)
            elif mode == "events":
                pushed, fixtures = await run_events(ctx, input_data, max_items, max_events, concurrency, push)
            elif mode == "predictor":
                pushed, fixtures = await run_predictor(ctx, input_data, max_items, max_events, concurrency, push)
            else:
                pushed, fixtures = await run_providers(ctx, max_items, push)

            Actor.log.info(
                f"mode={mode} league={league_key} -> {pushed} record(s) from {fixtures} "
                f"fixture(s)/market(s); {client.requests} request(s), "
                f"{client.ref_lookups} name lookup(s), {client.ref_cache_hits} cache hit(s), "
                f"tls={client.winning_profile}"
            )
            if pushed == 0:
                Actor.log.warning(
                    "nothing was pushed. With no 'dates' the source returns the current week "
                    "only, and outside a season that can legitimately be empty -- run mode "
                    "'reference' to see what the source is serving right now."
                )
        finally:
            await client.close()
