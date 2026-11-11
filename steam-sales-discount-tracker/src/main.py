"""Steam Sales & Discount Tracker - Apify Actor entrypoint."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import Blocked, NotFound, SteamClient
from .constants import CATEGORY1, DEFAULT_MAX_RETRIES, ISO_COUNTRIES, SNAPSHOT_STORE, SORT_BY
from .modes import MODES, TRACKED_MODES, Options
from .parsers import UnexpectedShape, envelope, error_record, utc_now_iso

log = logging.getLogger("steam")

PUSH_BATCH = 100


def _configure_logging() -> None:
    """The SDK only wires the 'apify' logger; route ours into the run log too."""
    root = logging.getLogger("steam")
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False


async def _proxy_configuration(actor_input: dict[str, Any]) -> Any:
    """Apify Proxy (Residential by default) or direct.

    Steam has no WAF; the proxy exists for the per-IP 429 on store search: with
    a proxy a 429 rotates the exit IP instead of waiting out a ~20 s lockout.
    Setup failures (e.g. a local run without a token) continue direct.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        log.info("No Apify Proxy requested - requests go out direct (search 429s are waited out).")
        return None
    try:
        pc = await Actor.create_proxy_configuration(actor_proxy_input=cfg)
    except Exception as exc:  # noqa: BLE001 - proxy is optional for this target
        log.warning("Apify Proxy could not be set up (%s: %s). Continuing WITHOUT a proxy.", type(exc).__name__, exc)
        return None
    if pc is None:
        log.warning("Apify Proxy returned no configuration. Continuing without a proxy.")
    return pc


class ChangeTracker:
    """Compares each priced record with the same item's previous observation.

    Snapshots live in a NAMED key-value store so they survive between scheduled
    runs. The key includes a hash of the filters: two tasks watching different
    countries or tags never overwrite each other, and "absent" is only judged
    against the same query.
    """

    def __init__(self, key: str, alert_drop_pct: float) -> None:
        self.key = key
        self.alert_drop_pct = alert_drop_pct
        self.store: Any = None
        self.prev: dict[str, Any] = {}
        self.next: dict[str, Any] = {}
        self.seen: set[str] = set()
        self.had_snapshot = False

    async def load(self) -> None:
        self.store = await Actor.open_key_value_store(name=SNAPSHOT_STORE)
        snap = await self.store.get_value(self.key) or {}
        self.prev = snap.get("entries") or {}
        self.had_snapshot = bool(snap)
        self.next = dict(self.prev)
        log.info("Change detection: %d items in previous snapshot '%s'", len(self.prev), self.key)

    def apply(self, rec: dict[str, Any]) -> None:
        if rec.get("recordType") not in ("DEAL", "FREEBIE", "APP_PRICE", "SALE_ITEM") or not rec.get("itemKey"):
            return
        key = f"{rec.get('country')}:{rec['itemKey']}"
        self.seen.add(key)
        final = rec.get("finalPriceCents")
        pct = rec.get("discountPct") or 0
        now = rec["_scrapedAt"]
        old = self.prev.get(key)
        lowest, lowest_at = (old or {}).get("lowest"), (old or {}).get("lowestAt")
        if final is not None and (lowest is None or final < lowest):
            lowest, lowest_at = final, now
        if old is None or not old.get("active", True):
            rec.update(previousFinalPriceCents=(old or {}).get("final"), priceChangeCents=None, previousDiscountPct=(old or {}).get("pct"),
                       isNewDeal=self.had_snapshot if pct > 0 else False, firstSeenAt=now)
        else:
            change = (final - old["final"]) if final is not None and old.get("final") is not None else None
            rec.update(previousFinalPriceCents=old.get("final"), priceChangeCents=change, previousDiscountPct=old.get("pct"),
                       isNewDeal=pct > 0 and not (old.get("pct") or 0), firstSeenAt=old.get("firstSeen"))
        rec.update(lowestPriceSeenCents=lowest, lowestPriceSeenAt=lowest_at,
                   isLowestPriceSeen=final is not None and lowest is not None and final <= lowest and self.had_snapshot)
        drop = (rec.get("priceChangeCents") or 0) < 0 and (old or {}).get("final")
        drop_pct = round(-rec["priceChangeCents"] / old["final"] * 100, 1) if drop else 0
        rec["priceDropPct"] = drop_pct or None
        rec["alert"] = bool(rec.get("isNewDeal")) or (drop_pct > 0 and drop_pct >= self.alert_drop_pct)
        self.next[key] = {"final": final, "orig": rec.get("originalPriceCents"), "pct": pct, "name": rec.get("name"),
                          "url": rec.get("storeUrl"), "lowest": lowest, "lowestAt": lowest_at,
                          "firstSeen": rec.get("firstSeenAt") or now, "at": now, "active": True}

    def ended(self, label: str) -> list[dict[str, Any]]:
        """Items active last run but absent from this COMPLETE run -> the discount ended."""
        out = []
        for key, old in self.prev.items():
            if key in self.seen or not old.get("active", True):
                continue
            country, _, item_key = key.partition(":")
            out.append(envelope(label, "S1-snapshot-diff", "DEAL_ENDED", country=country, itemKey=item_key,
                                name=old.get("name"), storeUrl=old.get("url"), lastFinalPriceCents=old.get("final"),
                                lastOriginalPriceCents=old.get("orig"), lastDiscountPct=old.get("pct"),
                                lastSeenAt=old.get("at"), firstSeenAt=old.get("firstSeen"),
                                lowestPriceSeenCents=old.get("lowest")))
            self.next[key] = {**old, "active": False}
        return out

    async def save(self) -> None:
        if self.store is not None:
            await self.store.set_value(self.key, {"savedAt": utc_now_iso(), "entries": self.next})


def _snapshot_key(mode: str, opt: Options) -> str:
    q = {"country": opt.country, "countries": opt.countries, "apps": sorted(opt.apps), "sales": sorted(opt.sales),
         "category": opt.category, "tags": sorted(map(str, opt.tags)), "term": opt.search_term,
         "maxPrice": opt.max_price, "minDiscount": opt.min_discount, "hideF2P": opt.hide_free_to_play}
    return f"snapshot-{mode}-{hashlib.sha1(json.dumps(q, sort_keys=True).encode()).hexdigest()[:12]}"


def _country(value: Any) -> str | None:
    cc = str(value or "").strip().upper()
    return cc if cc in ISO_COUNTRIES else None


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = actor_input.get("mode") or "deals"
        if mode not in MODES:
            await Actor.fail(status_message=f"Unknown mode {mode!r}. Use one of: {', '.join(MODES)}")
            return

        # Steam silently falls back to USD (appdetails) or returns 0 rows (search)
        # for an unknown country code, so reject it up front.
        country = _country(actor_input.get("country") or "US")
        # `countries` is only read by appPrices; other modes ignore it entirely.
        raw_countries = (actor_input.get("countries") or ["US"]) if mode == "appPrices" else ["US"]
        countries = [c for c in (_country(x) for x in raw_countries) if c]
        bad = [str(x) for x in ([actor_input.get("country")] if not country else []) + [x for x in raw_countries if not _country(x)] if x]
        if not country or bad:
            await Actor.fail(status_message=f"Invalid country code(s): {', '.join(bad) or actor_input.get('country')}. Use ISO 3166 two-letter codes (US, GB, DE, ID ...).")
            return
        category = actor_input.get("category") or "all"
        sort_by = actor_input.get("sortBy") or "relevance"
        if category not in CATEGORY1 or sort_by not in SORT_BY:
            await Actor.fail(status_message=f"Invalid category/sortBy. category: {', '.join(CATEGORY1)}; sortBy: {', '.join(SORT_BY)}")
            return

        apps = [str(a).strip() for a in actor_input.get("apps") or [] if str(a).strip()]
        sales = [str(a).strip() for a in actor_input.get("saleUrls") or [] if str(a).strip()]
        if mode == "appPrices" and not apps:
            await Actor.fail(status_message="Mode 'appPrices' needs at least one entry in 'apps' (appid, Steam URL or game name).")
            return
        if mode == "salePage" and not sales:
            await Actor.fail(status_message="Mode 'salePage' needs at least one entry in 'saleUrls' (store.steampowered.com/sale/<name> URL or the name).")
            return

        max_price = actor_input.get("maxPrice")
        opt = Options(
            country=country,
            countries=list(dict.fromkeys(countries)),
            apps=list(dict.fromkeys(apps)),
            sales=list(dict.fromkeys(sales)),
            category=category,
            tags=[str(t).strip() for t in actor_input.get("tags") or [] if str(t).strip()],
            search_term=str(actor_input.get("searchTerm") or "").strip(),
            max_price=float(max_price) if max_price not in (None, "") else None,
            # Default 1: ~2% of Steam's specials list is listed at 0% (edition upgrades,
            # DLC whose BUNDLE is discounted). 0 keeps them.
            min_discount=max(0, min(100, int(actor_input["minDiscount"] if actor_input.get("minDiscount") is not None else 1))),
            sort_by=sort_by,
            hide_free_to_play=bool(actor_input.get("hideFreeToPlay", False)),
            max_items=max(1, int(actor_input.get("maxItems") or 500)),
            include_discount_details=bool(actor_input.get("includeDiscountDetails", True)),
            include_usd=bool(actor_input.get("includeUsdPrices", True)),
            include_past_events=bool(actor_input.get("includePastEvents", False)),
            concurrency=max(1, min(10, int(actor_input.get("maxConcurrency") or 4))),
        )
        max_retries = max(1, int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES))
        client = SteamClient(await _proxy_configuration(actor_input), max_retries=max_retries)

        tracker = None
        if mode in TRACKED_MODES and actor_input.get("compareWithPrevious", True):
            tracker = ChangeTracker(_snapshot_key(mode, opt), float(actor_input.get("alertPriceDropPct") or 0))
            await tracker.load()

        log.info("Mode=%s country=%s countries=%s apps=%d sales=%d maxItems=%d minDiscount=%d tags=%s",
                 mode, opt.country, opt.countries, len(opt.apps), len(opt.sales), opt.max_items, opt.min_discount, opt.tags)

        stats = {"records": 0, "errors": 0, "hard_errors": 0}
        batch: list[dict[str, Any]] = []

        async def flush() -> None:
            nonlocal batch
            if batch:
                await Actor.push_data(batch)
                stats["records"] += len(batch)
                errs = [r for r in batch if r.get("_error")]
                stats["errors"] += len(errs)
                stats["hard_errors"] += sum(1 for r in errs if r["_error"] != "no_results")
                batch = []

        completed = False
        try:
            async for rec in MODES[mode](client, opt):
                if tracker and not rec.get("_error"):
                    tracker.apply(rec)
                batch.append(rec)
                if len(batch) >= PUSH_BATCH:
                    await flush()
                    await Actor.set_status_message(f"{mode}: {stats['records']} records so far")
            completed = True
        except (Blocked, NotFound) as exc:
            log.error("%s: upstream failure - %s", mode, exc)
            batch.append(error_record(mode, "blocked" if isinstance(exc, Blocked) else "not_found", str(exc)))
        except UnexpectedShape as exc:
            log.error("%s: upstream layout changed - %s", mode, exc)
            batch.append(error_record(mode, "unexpected_shape", str(exc)))
        finally:
            await flush()
            await client.close()

        if tracker:
            # Ended deals are only knowable when the whole result set was read
            # (deals) or the input list is fixed (appPrices / salePage).
            full = completed and (opt.crawl_complete if mode in ("deals", "freebies") else True)
            if full and tracker.had_snapshot and mode != "appPrices":
                ended = tracker.ended(f"{mode}:{opt.country}")
                if ended:
                    log.info("%d deals ended since the previous run", len(ended))
                    batch.extend(ended)
                    await flush()
            elif not full and mode in ("deals", "freebies"):
                log.info("Result set was truncated (maxItems or an error) - ended-deal detection skipped this run.")
            if completed:
                await tracker.save()

        ok = stats["records"] - stats["errors"]
        summary = (f"Done. mode={mode} records={ok} errors={stats['errors']} requests={client.request_count} "
                   f"rate_limited={client.rate_limited}")
        log.info(summary)
        if ok == 0 and stats["hard_errors"]:
            await Actor.fail(status_message=summary + " - every input failed, see the dataset for reasons.")
            return
        await Actor.set_status_message(summary, is_terminal=True)
