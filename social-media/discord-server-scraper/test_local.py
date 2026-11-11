"""Local test harness: parser unit tests on fixtures, then every mode live.

    python test_local.py            # everything
    python test_local.py --offline  # fixtures only, no network
    python test_local.py --mode inviteLookup

The offline half is the regression net. It runs against the HTML and JSON in
tests/fixtures, so a change to the SSR parser or to a field mapping is caught
without touching Discord, and the fixtures double as a record of what the
payloads looked like on 2026-09-21.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import urllib.parse
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from src.client import DiscordClient  # noqa: E402
from src.constants import DISCOVERY_CATEGORIES  # noqa: E402
from src.modes import MODES, Budget, resolve_target  # noqa: E402
from src.parsers import (  # noqa: E402
    parse_bot_profile,
    record,
    parse_discovery_hit,
    parse_game_profile,
    parse_invite,
    parse_server_profile,
    parse_trending_game,
    parse_widget,
    snowflake_created_at,
)
from src.serialized import (  # noqa: E402
    SerializedParseError,
    find_loader,
    parse_router_payload,
)

FIXTURES = pathlib.Path(__file__).parent / "tests" / "fixtures"

PASS = FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# -- offline ---------------------------------------------------------------

def test_serialized() -> None:
    print("\n[serialized] the $R / !0 / void 0 JavaScript literal parser")

    from src.serialized import _Reader  # noqa: PLC0415 - internal by design

    def parse(src: str):
        r = _Reader(src)
        return r.value()

    check("booleans", parse("{a:!0,b:!1}") == {"a": True, "b": False})
    check("void 0 is null", parse("{a:void 0}") == {"a": None})
    check("numbers", parse("[1,-2,3.5,1e3,-1.5e-2]") == [1, -2, 3.5, 1000.0, -0.015])
    check("numeric keys", parse("{0:32,1:24579}") == {"0": 32, "1": 24579})
    check("$R assignment", parse("$R[3]={a:$R[4]=[1,2]}") == {"a": [1, 2]})
    check("$R back-reference", parse("[$R[9]={a:1},$R[9]]") == [{"a": 1}, {"a": 1}])
    check(
        "escaped quotes and braces in strings",
        parse(r'{n:"a \"big\" {id: community}, yes"}')
        == {"n": 'a "big" {id: community}, yes'},
    )
    # Written as an escaped escape so the fixture text really does contain the
    # six characters \u d 8 3 d, the way Discord's payload does. Server names
    # and reasons-to-join are full of emoji, and they arrive as surrogate
    # pairs that have to be recombined.
    surrogate = "{e:\"\\ud83d\\ude0a\"}"
    check("surrogate pair emoji", parse(surrogate) == {"e": "\U0001F60A"})
    check("array hole", parse("[1,,3]") == [1, None, 3])
    check("nested empty containers", parse("{a:[],b:{}}") == {"a": [], "b": {}})

    try:
        parse_router_payload("<html><body>no script here</body></html>")
        check("a page with no payload raises", False, "no exception")
    except SerializedParseError:
        check("a page with no payload raises", True)


def test_offline_parsers() -> None:
    print("\n[parsers] fixtures captured 2026-09-21")

    # -- discovery search
    loader = find_loader(fixture("discovery_search.html"), "searchResults")
    results = loader["searchResults"]
    hits = results["hits"]
    check("search returns a full page", len(hits) == 12, f"got {len(hits)}")
    check("search echoes the query", results.get("query") == "crypto")
    check(
        "search used query= not q=",
        "query=crypto" in (results.get("params") or ""),
        results.get("params", "")[:80],
    )
    check(
        "server-side page size is 12",
        results.get("length") == 12,
        f"length={results.get('length')}",
    )
    row = parse_discovery_hit(hits[0])
    check("hit has a guild id", bool(row["guildId"]))
    check("hit has counts", isinstance(row["memberCount"], int) and row["memberCount"] > 0)
    check(
        "engagement rate is a sane percentage",
        row["engagementRatePct"] is None or 0 <= row["engagementRatePct"] <= 100,
        str(row["engagementRatePct"]),
    )
    check("icon hash expanded to a URL", (row["iconUrl"] or "").startswith("https://cdn."))
    check("createdAt derived from the snowflake", bool(row["createdAt"]))
    check("feature booleans present", "isPartnered" in row and "isVerified" in row)

    from src.parsers import _feature_flags  # noqa: PLC0415 - internal by design

    check(
        "monetization matches any of Discord's several spellings",
        _feature_flags(["CREATOR_MONETIZABLE"])["isMonetizationEnabled"]
        and _feature_flags(["CREATOR_MONETIZABLE_PROVISIONAL"])["isMonetizationEnabled"]
        and _feature_flags(["ROLE_SUBSCRIPTIONS_ENABLED"])["isMonetizationEnabled"]
        and not _feature_flags(["COMMUNITY"])["isMonetizationEnabled"],
    )
    check(
        "30-locale name table dropped",
        all("name_localizations" not in c for c in row["categories"]),
    )

    # -- category listing
    loader = find_loader(fixture("discovery_category.html"), "category")
    check("category page names its category", loader.get("category") == "gaming")
    # Algolia's echoed params are URL-encoded, so `=` arrives as %3D.
    params = urllib.parse.unquote(loader["searchResults"].get("params") or "")
    check(
        "category filter is on category id 1",
        "primary_category_id=1" in params,
        params[-80:],
    )
    check(
        "category page filters on primary OR secondary category",
        "categories.id=1" in params,
        params[-80:],
    )

    # -- server profile
    loader = find_loader(fixture("server_profile.html"), "guild")
    prof = parse_server_profile(loader)
    check("profile guild id", prof["guildId"] == "267624335836053506")
    check("profile name", prof["name"] == "Python")
    check("profile about is the long text", len(prof["about"] or "") > 200)
    check("profile social links", len(prof["socialLinks"]) >= 3, str(prof["socialLinks"]))
    check("profile createdAt is published", (prof["createdAt"] or "").startswith("2017-"))
    check("profile reasons to join", len(prof["reasonsToJoin"]) >= 1)
    check("profile keywords", "python" in (prof["keywords"] or []))

    # -- invite
    payload = json.loads(fixture("invite.json"))
    inv = parse_invite(payload, "python")
    check("invite guild id", inv["guildId"] == "267624335836053506")
    check("invite member count", isinstance(inv["memberCount"], int) and inv["memberCount"] > 1000)
    check("invite is recognised as a vanity", inv["isVanityInvite"] is True)
    check("invite never expires", inv["expiresAt"] is None)
    check("invite verification level is named", inv["verificationLevel"] == "MEDIUM", str(inv["verificationLevel"]))
    check("invite boost tier", inv["boostTier"] == 3, str(inv["boostTier"]))
    check("invite landing channel", inv["landingChannelName"] == "welcome")
    check("invite surfaces the server tag", inv["serverTag"] == "snek", str(inv["serverTag"]))

    # -- widget
    payload = json.loads(fixture("widget.json"))
    wid = parse_widget(payload)
    check("widget online count", isinstance(wid["onlineCount"], int) and wid["onlineCount"] > 0)
    check("widget member list is capped at 100", wid["membersReturned"] == 100)
    check("widget truncation is flagged", wid["memberListTruncated"] is True)
    check(
        "widget members carry a position, not a user id",
        "positionInResponse" in wid["members"][0] and "id" not in wid["members"][0],
    )
    check("widget voice channels", len(wid["voiceChannels"]) > 0)

    # -- trending games
    loader = find_loader(fixture("trending_games.html"), "data")
    data = loader["data"]
    games = data.get("games") or []
    check("trending chart has games", len(games) > 0, f"got {len(games)}")
    check("trending chart names its week", bool(data.get("week_date")))
    check("trending chart links the previous week", bool(data.get("prev_week_date")))
    game = parse_trending_game(games[0], data.get("week_date"))
    check("trending game rank is 1", game["rank"] == 1, str(game["rank"]))
    check("trending game has week-on-week movement", game["totalPlayersPctChange"] is not None)
    check("trending game links its official server", bool(game["officialGuildId"]))
    check("trending game builds a game URL", (game["gameUrl"] or "").startswith("https://"))

    # -- game profile
    loader = find_loader(fixture("game_profile.html"), "data")
    gp = parse_game_profile(loader["data"])
    check("game name", gp["gameName"] == "Valheim")
    check("game developers", len(gp["developers"]) > 0)
    check("game official links", len(gp["links"]) > 3)
    check("game l30 rank", gp["last30DayRank"] is not None)

    # -- bot profile
    bot = parse_bot_profile(json.loads(fixture("app_rpc.json")))
    check("bot name", bot["name"] == "Midjourney Bot")
    check("bot verified flag", bot["isVerified"] is True)
    check("bot tags", len(bot["tags"]) > 0)
    check("bot invite URL built", "client_id=936929561302675456" in (bot["inviteUrl"] or ""))


def test_dataset_schema() -> None:
    """Check every record shape against .actor/output_schema.json.

    This exists because of a real failure. The first cloud run of
    serverSnapshot died with `InvalidRequestError: Schema validation failed`
    on push_data: the schema declared `id` as a plain string, and every
    diagnostic row carries `id: null`. Apify validates the WHOLE batch, so one
    error row takes the entire push down and the run exits 91 with zero
    records -- and the two modes that had run before it passed only because
    neither happened to produce a diagnostic row. Types are checked here, on
    a batch that deliberately includes an error row, so the next one is caught
    on this machine rather than in the cloud.
    """
    print("\n[dataset schema] record shapes against .actor/output_schema.json")
    schema = json.loads(
        (pathlib.Path(__file__).parent / ".actor" / "output_schema.json").read_text(
            encoding="utf-8"
        )
    )
    props = schema["fields"]["properties"]
    py_types = {
        "string": str, "object": dict, "array": list,
        "number": (int, float), "integer": int, "boolean": bool,
    }

    def validate(rec: dict, label: str) -> None:
        for field, spec in props.items():
            declared = spec["type"]
            declared = declared if isinstance(declared, list) else [declared]
            value = rec.get(field)
            if value is None:
                check(
                    f"{label}: null {field} is declared nullable",
                    "null" in declared,
                    f"schema says {declared}",
                )
                continue
            allowed = tuple(
                py_types[t] for t in declared if t in py_types
            )
            check(
                f"{label}: {field} is {declared}",
                isinstance(value, allowed),
                f"got {type(value).__name__}",
            )

    from src.parsers import error_record  # noqa: PLC0415

    loader = find_loader(fixture("discovery_search.html"), "searchResults")
    validate(
        record(
            "discovery_result", "267624335836053506",
            parse_discovery_hit(loader["searchResults"]["hits"][0]),
            mode="discoverySearch", source_url="https://discord.com/servers",
        ),
        "discovery_result",
    )
    # The row that broke the cloud run.
    validate(
        error_record("zzzqqxnotreal99", "not_found", "gone", mode="serverSnapshot"),
        "error row",
    )


def test_resolvers() -> None:
    print("\n[resolve_target] every shape a buyer might paste")
    cases = {
        "https://discord.gg/python": ("invite", "python"),
        "discord.gg/B9qbPSzX": ("invite", "B9qbPSzX"),
        "https://discord.com/invite/abc123": ("invite", "abc123"),
        "https://discord.com/servers/python-267624335836053506": ("guild", "267624335836053506"),
        "https://discord.com/servers/267624335836053506": ("guild", "267624335836053506"),
        "https://discord.com/servers/totally-wrong-slug-267624335836053506": ("guild", "267624335836053506"),
        "267624335836053506": ("guild", "267624335836053506"),
        "python": ("invite", "python"),
    }
    for raw, (kind, want) in cases.items():
        t = resolve_target(raw)
        got = t.guild_id if kind == "guild" else t.invite_code
        check(f"{raw[:52]:52s} -> {kind}", got == want, f"got {got!r}")

    for bad in ("https://example.com/servers/x", "https://discord.com/servers/no-id-here"):
        try:
            resolve_target(bad)
            check(f"{bad[:52]:52s} -> rejected", False, "no exception")
        except ValueError:
            check(f"{bad[:52]:52s} -> rejected", True)

    print("\n[snowflake] id -> creation time")
    check(
        "Python's guild id decodes to Jan 2017",
        (snowflake_created_at("267624335836053506") or "").startswith("2017-01-08"),
        str(snowflake_created_at("267624335836053506")),
    )
    check("garbage in, None out", snowflake_created_at("not-a-number") is None)
    check("None in, None out", snowflake_created_at(None) is None)

    print("\n[categories] only five have a browsable page")
    check("five categories", len(DISCOVERY_CATEGORIES) == 5, str(list(DISCOVERY_CATEGORIES)))


# -- live ------------------------------------------------------------------

LIVE_CASES: dict[str, dict] = {
    "discoverySearch": {"searchKeywords": ["crypto"], "maxPagesPerTarget": 2},
    "discoveryCategory": {"categories": ["science & tech"], "maxPagesPerTarget": 1},
    "serverProfile": {"serverTargets": ["https://discord.gg/python"]},
    "inviteLookup": {
        "inviteCodes": ["https://discord.gg/python", "zzzqqxnotreal99"],
    },
    "serverWidget": {
        "serverTargets": ["267624335836053506", "https://discord.gg/discord-developers"],
    },
    "serverSnapshot": {"serverTargets": ["https://discord.gg/python"]},
    "trendingGames": {"weeksOfHistory": 2},
    "gameProfile": {"gameTargets": ["https://discord.com/game/valheim-1124358970618953818"]},
    "botProfile": {"applicationIds": ["936929561302675456"]},
}

# What each live mode must actually produce for the run to count as passing.
LIVE_EXPECT: dict[str, tuple[str, int]] = {
    "discoverySearch": ("discovery_result", 12),
    "discoveryCategory": ("discovery_result", 10),
    "serverProfile": ("server_profile", 1),
    "inviteLookup": ("invite", 1),
    "serverWidget": ("widget", 1),
    "serverSnapshot": ("server_snapshot", 1),
    "trendingGames": ("trending_game", 10),
    "gameProfile": ("game_profile", 1),
    "botProfile": ("bot_profile", 1),
}


async def run_live(only: str | None) -> None:
    print("\n[live] every mode against discord.com")
    client = DiscordClient(request_delay=2.0)
    try:
        for mode, opts in LIVE_CASES.items():
            if only and mode != only:
                continue
            print(f"\n  -- {mode} --")
            options = {
                "searchKeywords": [], "categories": [], "serverTargets": [],
                "inviteCodes": [], "gameTargets": [], "applicationIds": [],
                **opts,
            }
            budget = Budget(30)
            rows: list[dict] = []
            try:
                async for rec in MODES[mode](client, options, budget):
                    rows.append(rec)
            except Exception as exc:  # noqa: BLE001 - a failing mode must not stop the sweep
                check(f"{mode} ran", False, f"{type(exc).__name__}: {exc}")
                continue

            want_type, want_n = LIVE_EXPECT[mode]
            good = [r for r in rows if r["item_type"] == want_type]
            errs = [r for r in rows if r["item_type"] == "error"]
            check(
                f"{mode}: >= {want_n} {want_type} rows",
                len(good) >= want_n,
                f"got {len(good)} ({[r['data'].get('_error') for r in errs]})",
            )
            if good:
                sample = good[0]
                check(f"{mode}: row has an id", bool(sample["id"]))
                check(f"{mode}: row has scrapedAt", bool(sample["metadata"].get("scrapedAt")))
                check(f"{mode}: row has sourceUrl", bool(sample["metadata"].get("sourceUrl")))
                preview = {
                    k: v for k, v in sample["data"].items()
                    if k in ("name", "gameName", "guildId", "memberCount", "onlineCount",
                             "engagementRatePct", "rank", "applicationId", "sources")
                }
                print(f"        {json.dumps(preview, ensure_ascii=False)[:200]}")

            # Mode-specific assertions on live data.
            if mode == "inviteLookup":
                check(
                    "a dead invite code yields a not_found row, not a crash",
                    any(r["data"].get("_error") == "not_found" for r in errs),
                    str([r["data"].get("_error") for r in errs]),
                )
            if mode == "serverWidget":
                check(
                    "a widget-disabled server is reported as such",
                    any(r["data"].get("_error") == "widget_disabled" for r in errs),
                    str([r["data"].get("_error") for r in errs]),
                )
            if mode == "discoverySearch":
                names = [r["data"]["name"].lower() for r in good if r["data"].get("name")]
                check(
                    "keyword actually filtered the results",
                    sum("crypto" in n for n in names) >= 3,
                    f"{sum('crypto' in n for n in names)}/{len(names)} names contain it",
                )
                ids = [r["id"] for r in good]
                check("no duplicate servers across pages", len(ids) == len(set(ids)))
            if mode == "trendingGames":
                weeks = {r["data"]["weekDate"] for r in good}
                check("two distinct weeks collected", len(weeks) == 2, str(weeks))
            if mode == "serverSnapshot":
                srcs = good[0]["data"].get("sources") if good else []
                check(
                    "snapshot combined at least two open surfaces",
                    len(srcs or []) >= 2, str(srcs),
                )
    finally:
        client.close()
    print(f"\n  ({client.request_count} HTTP requests, "
          f"{client.rate_limited_count} rate limited)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip the live sweep")
    ap.add_argument("--mode", help="run only this mode live")
    args = ap.parse_args()

    test_serialized()
    test_offline_parsers()
    test_dataset_schema()
    test_resolvers()
    if not args.offline:
        asyncio.run(run_live(args.mode))

    print(f"\n{'=' * 60}\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
