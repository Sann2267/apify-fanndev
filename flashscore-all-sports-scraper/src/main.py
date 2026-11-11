import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FeedUnauthorized, FlashscoreClient
from src.constants import (
    EP_DAY,
    EP_DETAIL,
    EP_H2H,
    EP_LINEUPS,
    EP_LIVE,
    EP_STATS,
    EP_SUMMARY,
    MAX_DAY_OFFSET,
    MODES,
    PROBE_SPORT_IDS,
    SPORTS,
)
from src.extractor import (
    extract_error,
    extract_match_id,
    parse_feed,
    parse_incidents,
    parse_stats,
    split_matches,
    wrap_detail,
    wrap_match,
    wrap_sport,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (RuntimeError, ConnectionError, RequestException)


async def run_fixtures(
    sport_ids: list[int], day_offsets: list[int], max_items: int, proxy_url: str | None
) -> list[dict]:
    client = FlashscoreClient(proxy_url=proxy_url)
    records: list[dict] = []
    # Budget per (sport, day) combination rather than one global cap. With a
    # single global cap the first sport eats it whole -- football alone returns
    # ~275 rows for one day -- and a run asking for 3 sports silently comes
    # back with only the first one. Verified in local testing before this fix.
    combos = max(1, len(sport_ids) * len(day_offsets))
    per_combo = max(1, max_items // combos)
    try:
        for sport in sport_ids:
            for day in day_offsets:
                label = f"fixtures:sport={sport}:day={day}"
                taken = 0
                try:
                    body = await client.get_feed(EP_DAY.format(sport=sport, day=day))
                except FeedUnauthorized as e:
                    return records + [extract_error(label, "unauthorized", repr(e))]
                except TRANSIENT as e:
                    records.append(extract_error(label, "blocked_or_transient", repr(e)))
                    continue
                if not body:
                    # Normal upstream answer for a sport with no fixtures that
                    # day -- reported, not treated as a failure.
                    log.info(f"{label}: empty feed (no fixtures)")
                    continue
                for raw, header in split_matches(body):
                    records.append(wrap_match(raw, header, sport, label))
                    taken += 1
                    if len(records) >= max_items:
                        return records[:max_items]
                    if taken >= per_combo:
                        break
        return records[:max_items]
    finally:
        await client.close()


async def run_live(sport_ids: list[int], max_items: int, proxy_url: str | None) -> list[dict]:
    client = FlashscoreClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        for sport in sport_ids:
            label = f"live:sport={sport}"
            try:
                body = await client.get_feed(EP_LIVE.format(sport=sport))
            except FeedUnauthorized as e:
                return records + [extract_error(label, "unauthorized", repr(e))]
            except TRANSIENT as e:
                records.append(extract_error(label, "blocked_or_transient", repr(e)))
                continue
            for raw, header in split_matches(body):
                # The "live" feed also carries the day's finished/scheduled rows;
                # AB=2 is the only positively-identified in-play marker.
                if raw.get("AB") != "2":
                    continue
                records.append(wrap_match(raw, header, sport, label))
                if len(records) >= max_items:
                    return records[:max_items]
        return records[:max_items]
    finally:
        await client.close()


async def run_match(
    raw_input: str,
    sport_id: int,
    include: dict,
    proxy_url: str | None,
) -> dict:
    match_id = extract_match_id(raw_input)
    if not match_id:
        return extract_error(raw_input, "invalid_match_id", "expected an 8-character Flashscore match id or URL")

    client = FlashscoreClient(proxy_url=proxy_url)
    try:
        parts: dict = {}
        meta_body = await client.get_feed(EP_DETAIL.format(sport=sport_id, match=match_id))
        if not meta_body:
            # The sport segment in detail feeds is ignored upstream (verified:
            # sport 1/2/3/99 return byte-identical bodies), so an empty body
            # means the match id itself is unknown or has been purged.
            return extract_error(
                raw_input,
                "not_found",
                f"empty detail feed for match id {match_id} -- unknown or expired id "
                f"(Flashscore drops old matches from the feed host)",
            )
        meta = parse_feed(meta_body)
        parts["meta"] = meta[0] if meta else {}

        if include.get("summary"):
            parts["incidents"] = parse_incidents(await client.get_feed(EP_SUMMARY.format(sport=sport_id, match=match_id)))
        if include.get("statistics"):
            parts["statistics"] = parse_stats(await client.get_feed(EP_STATS.format(sport=sport_id, match=match_id)))
        if include.get("lineups"):
            parts["lineups"] = parse_feed(await client.get_feed(EP_LINEUPS.format(sport=sport_id, match=match_id)))
        if include.get("headToHead"):
            parts["headToHead"] = parse_feed(await client.get_feed(EP_H2H.format(sport=sport_id, match=match_id)))

        return wrap_detail(match_id, sport_id, parts)
    except FeedUnauthorized as e:
        return extract_error(raw_input, "unauthorized", repr(e))
    except TRANSIENT as e:
        return extract_error(raw_input, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_reference(proxy_url: str | None) -> list[dict]:
    """Probe every sport id live instead of trusting the static table --
    Flashscore serves 200 + empty body for ids that carry nothing, so what
    is actually available changes by day."""
    client = FlashscoreClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        for sport in PROBE_SPORT_IDS:
            try:
                body = await client.get_feed(EP_DAY.format(sport=sport, day=0))
            except FeedUnauthorized as e:
                return records + [extract_error("reference", "unauthorized", repr(e))]
            except TRANSIENT as e:
                records.append(extract_error(f"reference:sport={sport}", "blocked_or_transient", repr(e)))
                continue
            pairs = split_matches(body)
            sample = next((h.get("ZA", "") for _, h in pairs if h.get("ZA")), "")
            if pairs or sport in SPORTS:
                records.append(wrap_sport(sport, len(pairs), sample))
        return records
    finally:
        await client.close()


def _clean_ids(values, fallback: list[int]) -> list[int]:
    out: list[int] = []
    for v in values or []:
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n not in out:
            out.append(n)
    return out or fallback


def _clean_days(values) -> list[int]:
    out: list[int] = []
    for v in values if values is not None else [0]:
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if abs(n) > MAX_DAY_OFFSET or n in out:
            continue
        out.append(n)
    return out or [0]


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "fixtures")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 200))
        sport_ids = _clean_ids(input_data.get("sportIds"), [1])

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "reference":
            records = await run_reference(await new_proxy_url())
            Actor.log.info(f"mode=reference: {len(records)} sport(s)")
            await Actor.push_data(records)
            return

        if mode == "fixtures":
            days = _clean_days(input_data.get("dayOffsets"))
            records = await run_fixtures(sport_ids, days, max_items, await new_proxy_url())
            Actor.log.info(f"mode=fixtures sports={sport_ids} days={days} -> {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "live":
            records = await run_live(sport_ids, max_items, await new_proxy_url())
            Actor.log.info(f"mode=live sports={sport_ids} -> {len(records)} record(s)")
            await Actor.push_data(records)
            return

        # mode == "match"
        ids = list(input_data.get("matchIds") or [])
        if input_data.get("matchId"):
            ids.insert(0, input_data["matchId"])
        if not ids:
            raise input_error("Provide 'matchId' or 'matchIds' when mode is 'match'.")
        seen = set()
        ids = [i for i in ids if not (i in seen or seen.add(i))]

        include = {
            "summary": bool(input_data.get("includeSummary", True)),
            "statistics": bool(input_data.get("includeStatistics", True)),
            "lineups": bool(input_data.get("includeLineups", False)),
            "headToHead": bool(input_data.get("includeHeadToHead", False)),
        }
        sport_id = int(sport_ids[0])
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)
        Actor.log.info(f"mode=match: {len(ids)} match(es) at sportId={sport_id}, include={include}")

        async def _bounded(raw: str):
            async with sem:
                record = await run_match(raw, sport_id, include, await new_proxy_url())
                await Actor.push_data(record)

        await asyncio.gather(*(_bounded(i) for i in ids))
