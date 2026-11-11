"""Mode dispatch for the short-interest / short-volume / filings Actor."""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from apify import Actor

from src.client import (
    BlockedUpstream,
    MarketDataClient,
    NotPublished,
    UpstreamNotFound,
)
from src.constants import (
    FINRA_DAILY,
    FINRA_LOOKBACK_DAYS,
    FINRA_VENUES,
    MODES,
    MSG_NOT_NASDAQ,
    NASDAQ_INFO,
    NASDAQ_SHORT_INTEREST,
    SEC_FULLTEXT,
    SEC_FULLTEXT_MAX,
    SEC_FULLTEXT_PAGE,
    SEC_SUBMISSIONS,
    SEC_TICKER_MAP,
)
from src.extractor import (
    extract_error,
    parse_finra_file,
    wrap_company,
    wrap_company_info,
    wrap_filing,
    wrap_fulltext_hit,
    wrap_reference,
    wrap_short_interest,
    wrap_short_volume,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (BlockedUpstream, RuntimeError, ConnectionError)


def normalize_symbol(raw: str) -> str:
    return (raw or "").strip().upper().lstrip("$")


def iso_to_compact(value: str) -> str:
    return (value or "").replace("-", "").strip()


# --- ticker -> CIK --------------------------------------------------------

async def load_ticker_map(client: MarketDataClient) -> dict:
    """SEC's official ticker->CIK map (10,422 entries). Fetched once per run
    and reused; without it every ticker lookup would need a search request."""
    raw = await client.get_sec(SEC_TICKER_MAP)
    mapping = {}
    for entry in (raw or {}).values():
        ticker = (entry.get("ticker") or "").upper()
        if ticker:
            mapping[ticker] = str(entry.get("cik_str")).zfill(10)
    return mapping


def resolve_cik(identifier: str, ticker_map: dict) -> str | None:
    """Accepts a ticker ('AAPL'), a bare CIK ('320193') or a padded CIK."""
    value = (identifier or "").strip().upper().lstrip("$")
    if not value:
        return None
    if value.startswith("CIK"):
        value = value[3:]
    if value.isdigit():
        return value.zfill(10)
    return ticker_map.get(value)


# --- Nasdaq short interest ------------------------------------------------

async def run_short_interest(
    symbols: list[str], asset_class: str, max_items: int, include_info: bool, proxy_url: str | None
) -> list[dict]:
    client = MarketDataClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        for raw in symbols:
            symbol = normalize_symbol(raw)
            if not symbol:
                records.append(extract_error(raw, "invalid_symbol", "empty ticker"))
                continue
            try:
                info = None
                if include_info:
                    info_body = await client.get_nasdaq(
                        NASDAQ_INFO.format(symbol=symbol, asset_class=asset_class)
                    )
                    info = info_body.get("data") or None

                body = await client.get_nasdaq(
                    NASDAQ_SHORT_INTEREST.format(symbol=symbol, asset_class=asset_class)
                )
            except UpstreamNotFound:
                records.append(extract_error(symbol, "not_found", "Nasdaq has no such symbol"))
                continue
            except TRANSIENT as e:
                records.append(extract_error(symbol, "blocked_or_transient", repr(e)))
                continue

            status = (body.get("status") or {})
            if status.get("rCode") == 400:
                messages = status.get("bCodeMessage") or []
                detail = messages[0].get("errorMessage") if messages else "Nasdaq rejected the symbol"
                records.append(extract_error(symbol, "not_found", detail))
                continue

            data = body.get("data")
            if not data:
                message = body.get("message") or ""
                if message.startswith(MSG_NOT_NASDAQ):
                    # Documented, permanent limit of the source rather than a
                    # failure: Nasdaq only publishes short interest for its own
                    # listings. Point the user at the mode that does cover it.
                    records.append(
                        extract_error(
                            symbol,
                            "not_published",
                            f"{message.strip()} (exchange="
                            f"{(info or {}).get('exchange', 'unknown')}). Use mode "
                            f"'short-volume' for daily FINRA data, which covers every US symbol.",
                        )
                    )
                else:
                    records.append(extract_error(symbol, "empty_response", message or "Nasdaq returned no data"))
                continue

            rows = ((data.get("shortInterestTable") or {}).get("rows")) or []
            if not rows:
                records.append(extract_error(symbol, "empty_response", "Nasdaq returned an empty table"))
                continue
            for row in rows:
                records.append(wrap_short_interest(symbol, row, info))
                if len(records) >= max_items:
                    return records[:max_items]
        return records[:max_items]
    finally:
        await client.close()


async def run_company_info(symbols: list[str], asset_class: str, proxy_url: str | None) -> list[dict]:
    client = MarketDataClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        for raw in symbols:
            symbol = normalize_symbol(raw)
            try:
                body = await client.get_nasdaq(NASDAQ_INFO.format(symbol=symbol, asset_class=asset_class))
            except TRANSIENT as e:
                records.append(extract_error(symbol, "blocked_or_transient", repr(e)))
                continue
            data = body.get("data")
            if not data:
                records.append(extract_error(symbol, "not_found", body.get("message") or "no symbol info"))
                continue
            records.append(wrap_company_info(symbol, data))
        return records
    finally:
        await client.close()


# --- FINRA short volume ---------------------------------------------------

async def _latest_finra_date(client: MarketDataClient, venue_code: str) -> tuple[str, str] | tuple[None, None]:
    """Walk back day by day until a published file answers.

    FINRA publishes with a 1-2 day lag and never publishes on weekends or
    market holidays, so 'yesterday' is wrong often enough that guessing would
    make the default input fail most Mondays.
    """
    today = datetime.now(timezone.utc).date()
    for back in range(1, FINRA_LOOKBACK_DAYS + 1):
        day = today - timedelta(days=back)
        compact = day.strftime("%Y%m%d")
        try:
            text = await client.get_finra(FINRA_DAILY.format(venue=venue_code, date=compact))
        except NotPublished:
            continue
        return day.isoformat(), text
    return None, None


async def run_short_volume(
    dates: list[str],
    venue: str,
    symbols: list[str],
    max_items: int,
    proxy_url: str | None,
) -> list[dict]:
    venue_code = FINRA_VENUES.get(venue, FINRA_VENUES["consolidated"])
    wanted = {normalize_symbol(s) for s in symbols if normalize_symbol(s)}
    client = MarketDataClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        targets: list[tuple[str, str | None]] = []
        if dates:
            targets = [(d, None) for d in dates]
        else:
            iso, text = await _latest_finra_date(client, venue_code)
            if not iso:
                return [
                    extract_error(
                        venue,
                        "not_published",
                        f"no FINRA file found in the last {FINRA_LOOKBACK_DAYS} days for venue {venue}",
                    )
                ]
            targets = [(iso, text)]

        for date_iso, preloaded in targets:
            compact = iso_to_compact(date_iso)
            if len(compact) != 8 or not compact.isdigit():
                records.append(extract_error(date_iso, "invalid_date", "expected YYYY-MM-DD"))
                continue
            try:
                text = preloaded if preloaded is not None else await client.get_finra(
                    FINRA_DAILY.format(venue=venue_code, date=compact)
                )
            except NotPublished as e:
                records.append(extract_error(date_iso, "not_published", str(e)))
                continue
            except TRANSIENT as e:
                records.append(extract_error(date_iso, "blocked_or_transient", repr(e)))
                continue

            try:
                rows = parse_finra_file(text)
            except ValueError as e:
                records.append(extract_error(date_iso, "shape_changed", str(e)))
                continue

            for row in rows:
                symbol = (row.get("Symbol") or "").strip().upper()
                if wanted and symbol not in wanted:
                    continue
                records.append(wrap_short_volume(venue, date_iso, row))
                if len(records) >= max_items:
                    return records[:max_items]

            if wanted:
                missing = wanted - {(r.get("symbol") or "") for r in records}
                for symbol in sorted(missing):
                    records.append(
                        extract_error(
                            f"{symbol}:{date_iso}",
                            "not_in_file",
                            f"{symbol} did not trade on {date_iso} or is not an NMS symbol",
                        )
                    )
        return records[:max_items]
    finally:
        await client.close()


# --- SEC ------------------------------------------------------------------

async def run_filings(
    identifiers: list[str],
    forms: list[str],
    since: str | None,
    max_items: int,
    proxy_url: str | None,
) -> list[dict]:
    wanted_forms = {f.strip().upper() for f in forms if f and f.strip()}
    client = MarketDataClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        ticker_map = await load_ticker_map(client)
        for identifier in identifiers:
            cik10 = resolve_cik(identifier, ticker_map)
            if not cik10:
                records.append(
                    extract_error(identifier, "not_found", "no CIK for this ticker in SEC's official map")
                )
                continue
            try:
                company = await client.get_sec(SEC_SUBMISSIONS.format(cik10=cik10))
            except UpstreamNotFound:
                records.append(extract_error(identifier, "not_found", f"SEC has no submissions for CIK {cik10}"))
                continue
            except TRANSIENT as e:
                records.append(extract_error(identifier, "blocked_or_transient", repr(e)))
                continue

            recent = ((company.get("filings") or {}).get("recent")) or {}
            count = len(recent.get("accessionNumber") or [])
            emitted = 0
            for i in range(count):
                filing = {k: v[i] for k, v in recent.items() if isinstance(v, list) and i < len(v)}
                if wanted_forms and (filing.get("form") or "").upper() not in wanted_forms:
                    continue
                if since and (filing.get("filingDate") or "") < since:
                    continue
                records.append(wrap_filing(identifier, company, filing))
                emitted += 1
                if len(records) >= max_items:
                    return records[:max_items]
            if not emitted:
                records.append(
                    extract_error(
                        identifier,
                        "empty_section",
                        f"CIK {cik10} has {count} recent filings but none matched "
                        f"forms={sorted(wanted_forms) or 'any'} since={since or 'any'}",
                    )
                )
        return records[:max_items]
    finally:
        await client.close()


async def run_company_profiles(identifiers: list[str], proxy_url: str | None) -> list[dict]:
    client = MarketDataClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        ticker_map = await load_ticker_map(client)
        for identifier in identifiers:
            cik10 = resolve_cik(identifier, ticker_map)
            if not cik10:
                records.append(extract_error(identifier, "not_found", "no CIK for this ticker"))
                continue
            try:
                company = await client.get_sec(SEC_SUBMISSIONS.format(cik10=cik10))
            except UpstreamNotFound:
                records.append(extract_error(identifier, "not_found", f"SEC has no submissions for CIK {cik10}"))
                continue
            except TRANSIENT as e:
                records.append(extract_error(identifier, "blocked_or_transient", repr(e)))
                continue
            records.append(wrap_company(identifier, company))
        return records
    finally:
        await client.close()


async def run_filing_search(
    query: str,
    forms: list[str],
    start_date: str | None,
    end_date: str | None,
    max_items: int,
    proxy_url: str | None,
) -> list[dict]:
    """EDGAR full-text search. The API caps a result set at 10,000 and a page
    at 100; both caps are the API's, and are surfaced rather than hidden."""
    client = MarketDataClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        params = {"q": query}
        if forms:
            params["forms"] = ",".join(f.strip() for f in forms if f.strip())
        if start_date:
            params["startdt"] = start_date
        if end_date:
            params["enddt"] = end_date

        offset = 0
        total = None
        while len(records) < max_items and offset < SEC_FULLTEXT_MAX:
            page_params = dict(params)
            if offset:
                page_params["from"] = str(offset)
            try:
                body = await client.get_sec(SEC_FULLTEXT, params=page_params)
            except TRANSIENT as e:
                records.append(extract_error(query, "blocked_or_transient", repr(e)))
                break

            hits_block = body.get("hits") or {}
            if total is None:
                raw_total = hits_block.get("total")
                total = raw_total.get("value") if isinstance(raw_total, dict) else raw_total
                log.info(f"filing-search: {total} total matches for {query!r}")
            hits = hits_block.get("hits") or []
            if not hits:
                break
            for hit in hits:
                record = wrap_fulltext_hit(query, hit)
                record["totalMatches"] = total
                records.append(record)
                if len(records) >= max_items:
                    return records[:max_items]
            offset += SEC_FULLTEXT_PAGE

        if not records:
            records.append(extract_error(query, "no_matches", f"EDGAR full-text search found nothing for {query!r}"))
        return records[:max_items]
    finally:
        await client.close()


async def run_reference(proxy_url: str | None) -> list[dict]:
    """Probe all three sources live, including which FINRA date is the newest
    published one -- the single most useful fact for scheduling this Actor."""
    client = MarketDataClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        url = NASDAQ_SHORT_INTEREST.format(symbol="TSLA", asset_class="stocks")
        try:
            body = await client.get_nasdaq(url)
            rows = (((body.get("data") or {}).get("shortInterestTable") or {}).get("rows")) or []
            records.append(
                wrap_reference(
                    "nasdaq-short-interest", url, bool(rows), "payload parsed" if rows else "no rows",
                    {"symbol": "TSLA", "rows": len(rows),
                     "latestSettlementDate": rows[0].get("settlementDate") if rows else None,
                     "note": "Nasdaq-listed stocks only"},
                )
            )
        except Exception as e:  # noqa: BLE001 -- a probe reports failures, never raises
            records.append(wrap_reference("nasdaq-short-interest", url, False, repr(e)))

        for venue, code in FINRA_VENUES.items():
            try:
                iso, text = await _latest_finra_date(client, code)
                if iso:
                    rows = parse_finra_file(text)
                    records.append(
                        wrap_reference(
                            f"finra-{venue}", FINRA_DAILY.format(venue=code, date=iso_to_compact(iso)),
                            True, "latest published file found",
                            {"latestDate": iso, "rows": len(rows),
                             "sampleSymbol": rows[0].get("Symbol") if rows else None},
                        )
                    )
                else:
                    records.append(
                        wrap_reference(f"finra-{venue}", FINRA_DAILY.format(venue=code, date="YYYYMMDD"),
                                       False, f"nothing published in the last {FINRA_LOOKBACK_DAYS} days")
                    )
            except Exception as e:  # noqa: BLE001
                records.append(wrap_reference(f"finra-{venue}", code, False, repr(e)))

        try:
            company = await client.get_sec(SEC_SUBMISSIONS.format(cik10="0000320193"))
            recent = ((company.get("filings") or {}).get("recent")) or {}
            records.append(
                wrap_reference(
                    "sec-submissions", SEC_SUBMISSIONS.format(cik10="0000320193"), True, "payload parsed",
                    {"company": company.get("name"), "recentFilings": len(recent.get("form") or []),
                     "latestFilingDate": (recent.get("filingDate") or [None])[0]},
                )
            )
        except Exception as e:  # noqa: BLE001
            records.append(wrap_reference("sec-submissions", SEC_SUBMISSIONS.format(cik10="0000320193"), False, repr(e)))

        try:
            body = await client.get_sec(SEC_FULLTEXT, params={"q": '"short interest"', "forms": "8-K"})
            raw_total = (body.get("hits") or {}).get("total")
            total = raw_total.get("value") if isinstance(raw_total, dict) else raw_total
            records.append(
                wrap_reference("sec-fulltext", SEC_FULLTEXT, bool(total), "payload parsed",
                               {"sampleQuery": '"short interest" in 8-K', "totalMatches": total})
            )
        except Exception as e:  # noqa: BLE001
            records.append(wrap_reference("sec-fulltext", SEC_FULLTEXT, False, repr(e)))

        return records
    finally:
        await client.close()


def _clean_list(input_data: dict, plural: str, single: str) -> list[str]:
    values = list(input_data.get(plural) or [])
    if input_data.get(single):
        values.insert(0, input_data[single])
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "short-interest")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 500))
        asset_class = (input_data.get("assetClass") or "stocks").strip() or "stocks"

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None

        symbols = _clean_list(input_data, "symbols", "symbol")

        if mode == "reference":
            records = await run_reference(proxy_url)
            Actor.log.info(f"mode=reference: {len(records)} source(s) probed")
            await Actor.push_data(records)
            return

        if mode == "short-interest":
            if not symbols:
                raise input_error("Provide 'symbol' or 'symbols' for mode 'short-interest'.")
            records = await run_short_interest(
                symbols, asset_class, max_items, bool(input_data.get("includeSymbolInfo", True)), proxy_url
            )
            Actor.log.info(f"mode=short-interest symbols={len(symbols)} -> {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "company":
            if not symbols:
                raise input_error("Provide 'symbol' or 'symbols' for mode 'company'.")
            records = await run_company_profiles(symbols, proxy_url)
            Actor.log.info(f"mode=company symbols={len(symbols)} -> {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "short-volume":
            dates = _clean_list(input_data, "dates", "date")
            venue = (input_data.get("venue") or "consolidated").strip()
            if venue not in FINRA_VENUES:
                raise input_error(f"Invalid venue: {venue!r}. Must be one of {sorted(FINRA_VENUES)}.")
            records = await run_short_volume(dates, venue, symbols, max_items, proxy_url)
            Actor.log.info(
                f"mode=short-volume venue={venue} dates={dates or 'latest'} "
                f"symbols={len(symbols) or 'all'} -> {len(records)} record(s)"
            )
            await Actor.push_data(records)
            return

        if mode == "filings":
            if not symbols:
                raise input_error("Provide 'symbol' or 'symbols' (tickers or CIKs) for mode 'filings'.")
            forms = list(input_data.get("forms") or [])
            records = await run_filings(symbols, forms, (input_data.get("since") or "").strip() or None,
                                        max_items, proxy_url)
            Actor.log.info(f"mode=filings identifiers={len(symbols)} -> {len(records)} record(s)")
            await Actor.push_data(records)
            return

        # mode == "filing-search"
        query = (input_data.get("query") or "").strip()
        if not query:
            raise input_error("Provide 'query' for mode 'filing-search'.")
        records = await run_filing_search(
            query,
            list(input_data.get("forms") or []),
            (input_data.get("startDate") or "").strip() or None,
            (input_data.get("endDate") or "").strip() or None,
            max_items,
            proxy_url,
        )
        Actor.log.info(f"mode=filing-search query={query!r} -> {len(records)} record(s)")
        await Actor.push_data(records)
