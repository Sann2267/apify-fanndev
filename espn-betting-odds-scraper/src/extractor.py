"""Turning ESPN's pointer-shaped JSON into flat rows.

Three things happen here that are not obvious from the upstream payload.

1. **Ids are read out of the pointer, not fetched.** Every ``$ref`` ends in the
   object's id, so ``.../teams/2?lang=en`` gives team 2 without a request. Only
   the *name* costs a lookup, and the lookup is cached.

2. **Line movement is derived, because ESPN publishes the ends and not the
   difference.** Each provider block carries ``open``, ``close`` and
   ``current``; the number a bettor acts on -- how far the spread and the total
   have moved since the book opened -- is computed here.

3. **American prices are converted to implied probability.** ``+400`` and
   ``-245`` are not comparable by eye across a futures board; ``0.200`` and
   ``0.710`` are. The vig is left in, so a two-way market sums to slightly over
   1 -- that is the book's margin and removing it would be inventing data.
"""

import re
from datetime import datetime, timezone

REF_ID = re.compile(r"/(\d+)(?:\?|$)")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ref_id(ref: str | None) -> str | None:
    """The trailing id of a ``$ref`` -- free, no request."""
    if not ref:
        return None
    m = REF_ID.search(ref.split("#")[0])
    return m.group(1) if m else None


def _num(value):
    """A number if it is one, else None. ESPN mixes ints, floats and strings."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace("+", "")
    if not text:
        return None
    try:
        return float(text) if ("." in text or "e" in text.lower()) else int(text)
    except ValueError:
        return None


def _nz(value):
    """A number, with **zero read as absent**.

    The live-odds provider entry writes ``0`` and ``0.0`` where it has nothing
    to say: ``overUnder: 0.0``, ``overOdds: 0.0``, ``moneyLine: 0``, ``price:
    0.0`` -- all on a fixture whose point spread is populated and real. No
    sportsbook quotes a total of 0 or an American price of 0, so a consumer
    averaging totals across books would be dragged toward zero by a field that
    means "not set". Point spreads are deliberately **not** run through this:
    a spread of 0 is a real pick-em line.
    """
    number = _num(value)
    return None if number == 0 else number


def american_to_probability(value) -> float | None:
    """Implied probability of an American price, vig included.

    ``+400`` -> 0.2, ``-245`` -> 0.7101. Returns None for anything that is not
    a price (ESPN writes ``"EVEN"``, ``"OFF"`` and empty strings in this slot).
    """
    odds = _num(value)
    if odds is None or odds == 0:
        return None
    odds = float(odds)
    if odds > 0:
        return round(100.0 / (odds + 100.0), 4)
    return round(-odds / (-odds + 100.0), 4)


def _price(block: dict | None, key: str) -> dict:
    """Pull one price out of an ``open``/``close``/``current`` block."""
    node = (block or {}).get(key) or {}
    if not isinstance(node, dict):
        return {}
    return {
        "american": node.get("american"),
        "decimal": _num(node.get("decimal")),
        "fraction": node.get("fraction"),
        "value": _num(node.get("value")),
    }


def _side_snapshot(side: dict | None, phase: str) -> dict:
    """``awayTeamOdds.open`` etc. -- point spread and moneyline for one side."""
    block = (side or {}).get(phase) or {}
    spread_pt = block.get("pointSpread") or {}
    return {
        "pointSpread": _num(spread_pt.get("american") or spread_pt.get("alternateDisplayValue")),
        "spreadPrice": _price(block, "spread").get("american"),
        "moneyline": _nz((block.get("moneyLine") or {}).get("american")),
    }


def _total(block: dict | None) -> float | None:
    node = (block or {}).get("total") or {}
    return _nz(node.get("american") or node.get("alternateDisplayValue"))


def event_context(event: dict, sport: str, league: str, league_key: str) -> dict:
    """The fixture fields every record in this Actor repeats."""
    comp = (event.get("competitions") or [{}])[0]
    season = event.get("season") or {}
    week = event.get("week") or {}
    venues = event.get("venues") or []
    home_id = away_id = None
    for competitor in comp.get("competitors") or []:
        side = competitor.get("homeAway")
        team_ref = (competitor.get("team") or {}).get("$ref")
        if side == "home":
            home_id = competitor.get("id") or ref_id(team_ref)
        elif side == "away":
            away_id = competitor.get("id") or ref_id(team_ref)
    return {
        "sport": sport,
        "league": league,
        "leagueKey": league_key,
        "eventId": str(event.get("id")) if event.get("id") is not None else None,
        "competitionId": str(comp.get("id")) if comp.get("id") is not None else None,
        "eventName": event.get("name"),
        "eventShortName": event.get("shortName"),
        "eventDate": event.get("date"),
        "seasonYear": _num(season.get("year")),
        "seasonType": _num((event.get("seasonType") or {}).get("type")),
        "week": _num(week.get("number")),
        "venueId": ref_id((venues[0] or {}).get("$ref")) if venues else None,
        "neutralSite": comp.get("neutralSite"),
        "homeTeamId": home_id,
        "awayTeamId": away_id,
    }


def team_fields(context: dict, teams: dict) -> dict:
    """Attach names to the home/away ids from whatever the team cache holds."""
    out = {}
    for side in ("home", "away"):
        team = teams.get(context.get(f"{side}TeamId")) or {}
        out[f"{side}Team"] = team.get("displayName")
        out[f"{side}TeamAbbrev"] = team.get("abbreviation")
    return out


def build_event_record(event: dict, context: dict, teams: dict, status: dict | None) -> dict:
    record = dict(context)
    record.update(team_fields(context, teams))
    state = ((status or {}).get("type") or {})
    record.update(
        {
            "recordType": "EVENT",
            "_source": "espn-core-events",
            "statusState": state.get("state"),
            "statusDetail": state.get("detail"),
            "isCompleted": state.get("completed"),
            "espnUrl": next(
                (
                    link.get("href")
                    for link in (event.get("links") or [])
                    if "gamecast" in (link.get("rel") or [])
                ),
                None,
            ),
        }
    )
    return record


def build_odds_record(item: dict, context: dict, teams: dict) -> dict:
    """One row per (event, sportsbook), with the movement ESPN does not publish."""
    provider = item.get("provider") or {}
    away, home = item.get("awayTeamOdds") or {}, item.get("homeTeamOdds") or {}

    open_home = _side_snapshot(home, "open")
    open_away = _side_snapshot(away, "open")
    current_home = _side_snapshot(home, "current")
    current_away = _side_snapshot(away, "current")
    close_home = _side_snapshot(home, "close")

    open_total = _total(item.get("open"))
    current_total = _total(item.get("current"))

    current_spread = current_home["pointSpread"]
    if current_spread is None:
        current_spread = _num(item.get("spread"))
    open_spread = open_home["pointSpread"]

    record = dict(context)
    record.update(team_fields(context, teams))
    record.update(
        {
            "recordType": "ODDS",
            "_source": "espn-core-odds",
            "hasOdds": True,
            "providerId": str(provider.get("id")) if provider.get("id") is not None else None,
            "providerName": provider.get("name"),
            "providerPriority": _num(provider.get("priority")),
            "details": item.get("details"),
            "spread": _num(item.get("spread")),
            "overUnder": _nz(item.get("overUnder")),
            "overOdds": _nz(item.get("overOdds")),
            "underOdds": _nz(item.get("underOdds")),
            "homeMoneyline": _nz(home.get("moneyLine")),
            "awayMoneyline": _nz(away.get("moneyLine")),
            "homeSpreadOdds": _nz(home.get("spreadOdds")),
            "awaySpreadOdds": _nz(away.get("spreadOdds")),
            "homeIsFavorite": home.get("favorite"),
            "awayIsFavorite": away.get("favorite"),
            "homeImpliedProbability": american_to_probability(home.get("moneyLine")),
            "awayImpliedProbability": american_to_probability(away.get("moneyLine")),
            "openSpread": open_spread,
            "openTotal": open_total,
            "openHomeMoneyline": open_home["moneyline"],
            "openAwayMoneyline": open_away["moneyline"],
            "closeSpread": close_home["pointSpread"],
            "closeTotal": _total(item.get("close")),
            "currentSpread": current_spread,
            "currentTotal": current_total,
            "currentHomeMoneyline": current_home["moneyline"],
            "currentAwayMoneyline": current_away["moneyline"],
            "spreadMovement": (
                round(current_spread - open_spread, 2)
                if current_spread is not None and open_spread is not None
                else None
            ),
            "totalMovement": (
                round(current_total - open_total, 2)
                if current_total is not None and open_total is not None
                else None
            ),
            "favoriteFlippedSinceOpen": (
                bool(home.get("favorite")) != bool((home.get("open") or {}).get("favorite"))
                if isinstance(home.get("open"), dict) and "favorite" in (home.get("open") or {})
                else None
            ),
            "isLiveOddsFeed": "live" in str(provider.get("name") or "").lower(),
            "hasPlaceholderZeros": any(
                _num(v) == 0
                for v in (
                    item.get("overUnder"),
                    item.get("overOdds"),
                    item.get("underOdds"),
                    home.get("moneyLine"),
                    away.get("moneyLine"),
                )
            ),
            "moneylineWinner": item.get("moneylineWinner"),
            "spreadWinner": item.get("spreadWinner"),
            "sportsbookUrl": next(
                (link.get("href") for link in (item.get("links") or []) if link.get("href")), None
            ),
        }
    )
    return record


def build_no_odds_record(context: dict, teams: dict, note: str) -> dict:
    """Books have not priced this fixture yet -- say so instead of dropping it."""
    record = dict(context)
    record.update(team_fields(context, teams))
    record.update(
        {
            "recordType": "ODDS",
            "_source": "espn-core-odds",
            "hasOdds": False,
            "providerId": None,
            "providerName": None,
            "note": note,
        }
    )
    return record


def build_prop_record(
    item: dict, context: dict, athlete: dict, team: dict, teams: dict | None = None
) -> dict:
    prop_type = item.get("type") or {}
    current = ((item.get("current") or {}).get("target") or {})
    opened = ((item.get("open") or {}).get("target") or {})
    current_value, open_value = _num(current.get("value")), _num(opened.get("value"))
    position = athlete.get("position") or {}

    record = dict(context)
    record.update(team_fields(context, teams or {}))
    record.update(
        {
            "recordType": "PROP",
            "_source": "espn-core-propbets",
            "providerId": ref_id((item.get("provider") or {}).get("$ref")),
            "propTypeId": str(prop_type.get("id")) if prop_type.get("id") is not None else None,
            "propTypeName": prop_type.get("name"),
            "athleteId": ref_id((item.get("athlete") or {}).get("$ref")),
            "athleteName": athlete.get("displayName") or athlete.get("fullName"),
            "athletePosition": position.get("abbreviation"),
            "athleteJersey": athlete.get("jersey"),
            "propTeamId": ref_id((item.get("team") or {}).get("$ref")),
            "propTeamName": team.get("displayName"),
            "currentTarget": current_value,
            "currentTargetDisplay": current.get("displayValue"),
            "openTarget": open_value,
            "targetMovement": (
                round(current_value - open_value, 2)
                if current_value is not None and open_value is not None
                else None
            ),
            "lastUpdated": item.get("lastUpdated"),
        }
    )
    return record


def build_futures_records(
    market: dict, sport: str, league: str, league_key: str, season: int, names: dict
) -> list[dict]:
    """One row per (market, sportsbook, runner). ``names`` maps ref -> entity."""
    rows = []
    market_id = market.get("id")
    for provider_block in market.get("futures") or []:
        provider = provider_block.get("provider") or {}
        books = provider_block.get("books") or []
        for book in books:
            entity_ref = (book.get("athlete") or {}).get("$ref") or (
                book.get("team") or {}
            ).get("$ref")
            entity = names.get((entity_ref or "").split("?")[0], {})
            rows.append(
                {
                    "recordType": "FUTURE",
                    "_source": "espn-core-futures",
                    "sport": sport,
                    "league": league,
                    "leagueKey": league_key,
                    "seasonYear": season,
                    "marketId": str(market_id) if market_id is not None else None,
                    "marketName": market.get("name"),
                    "providerId": str(provider.get("id")) if provider.get("id") is not None else None,
                    "providerName": provider.get("name"),
                    "providerActive": provider.get("active"),
                    "entityType": "athlete" if book.get("athlete") else "team",
                    "entityId": ref_id(entity_ref),
                    "entityName": entity.get("displayName") or entity.get("fullName"),
                    "price": book.get("value"),
                    "impliedProbability": american_to_probability(book.get("value")),
                    "runnersInMarket": len(books),
                }
            )
    return rows


def build_predictor_record(payload: dict, context: dict, teams: dict) -> dict:
    def stat(side: str, name: str):
        for entry in ((payload.get(side) or {}).get("statistics") or []):
            if entry.get("name") == name:
                return _num(entry.get("value"))
        return None

    record = dict(context)
    record.update(team_fields(context, teams))
    record.update(
        {
            "recordType": "PREDICTOR",
            "_source": "espn-core-predictor",
            "homeWinProbability": stat("homeTeam", "gameProjection"),
            "awayWinProbability": stat("awayTeam", "gameProjection"),
            "homeTieProbability": stat("homeTeam", "teamChanceTie"),
            "homePredictedPointDiff": stat("homeTeam", "teamPredPtDiff"),
            "awayPredictedPointDiff": stat("awayTeam", "teamPredPtDiff"),
            "matchupQuality": stat("homeTeam", "matchupQuality"),
            "predictorLastModified": payload.get("lastModified"),
        }
    )
    return record


def build_provider_record(payload: dict, sport: str, league: str, league_key: str) -> dict:
    return {
        "recordType": "PROVIDER",
        "_source": "espn-core-providers",
        "sport": sport,
        "league": league,
        "leagueKey": league_key,
        "providerId": str(payload.get("id")) if payload.get("id") is not None else None,
        "providerName": payload.get("name"),
        "providerPriority": _num(payload.get("priority")),
        "providerActive": payload.get("active"),
    }


def extract_error(input_value: str, reason: str, detail: str) -> dict:
    return {
        "recordType": "ERROR",
        "_source": "error",
        "_input": input_value,
        "errorReason": reason,
        "errorDetail": detail[:900],
    }


def wrap_reference(
    url: str, available: bool, note: str, sample: dict | None = None, profile: str | None = None
) -> dict:
    return {
        "recordType": "SURFACE",
        "_source": "reference",
        "_input": "reference",
        "probedUrl": url,
        "isAvailable": available,
        "note": note,
        "sample": sample or {},
        "winningTlsProfile": profile,
    }
