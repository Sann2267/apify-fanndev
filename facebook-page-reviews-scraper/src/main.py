"""Facebook Page Review & Rating Scraper -- Apify actor entry point."""

from __future__ import annotations

from datetime import datetime, timezone

from apify import Actor

from src.exporters import BUILDERS
from src.fbcore import BlockedError, FacebookSession
from src.parser import matches_filters, page_ref, summarise
from src.reviews import PageUnavailable, fetch_reviews, fetch_reviews_tab
from src.runtime import envelope, error_record, resolve_proxy, write_exports
from src.input_errors import input_error

SOURCE = "page-reviews-tab"


def read_pages(actor_input: dict) -> list[str]:
    refs: list[str] = []
    for key in ("pages", "startUrls"):
        for item in actor_input.get(key) or []:
            value = item.get("url") if isinstance(item, dict) else item
            ref = page_ref(str(value or ""))
            if ref:
                refs.append(ref)
    return list(dict.fromkeys(refs))


def epoch_from_date(value: str | None) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(f"postedAfter must be YYYY-MM-DD, got {value!r}")
    return int(parsed.timestamp())


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        refs = read_pages(actor_input)
        if not refs:
            raise input_error(
                "Nothing to scrape. Supply pages as slugs (['dominos']) or "
                "Facebook page URLs."
            )

        max_reviews = max(1, min(int(actor_input.get("maxReviewsPerPage", 50)), 2000))
        filters = {
            "onlyRecommended": bool(actor_input.get("onlyRecommended")),
            "onlyNotRecommended": bool(actor_input.get("onlyNotRecommended")),
            "onlyWithText": bool(actor_input.get("onlyWithText")),
            "textContains": actor_input.get("textContains"),
            "postedAfterEpoch": epoch_from_date(actor_input.get("postedAfter")),
        }
        if filters["onlyRecommended"] and filters["onlyNotRecommended"]:
            raise input_error(
                "onlyRecommended and onlyNotRecommended exclude each other -- "
                "enabling both can only ever return an empty dataset."
            )
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        proxy_url = await resolve_proxy(actor_input)

        Actor.log.info(f"{len(refs)} page(s), up to {max_reviews} review(s) each.")

        records: list[dict] = []
        kept: list[dict] = []
        failures = 0

        async with FacebookSession(proxy_url=proxy_url, log=Actor.log) as session:
            for slug in refs:
                try:
                    html, summary = await fetch_reviews_tab(session, slug)
                except (PageUnavailable, BlockedError) as exc:
                    failures += 1
                    record = error_record(SOURCE, slug, "page_unavailable", str(exc))
                    records.append(record)
                    await Actor.push_data(record)
                    continue
                except Exception as exc:
                    failures += 1
                    record = error_record(
                        SOURCE, slug, "unexpected_error", f"{type(exc).__name__}: {exc}"
                    )
                    records.append(record)
                    await Actor.push_data(record)
                    continue

                reviews, meta = await fetch_reviews(
                    session, html, summary["reviewsUrl"], max_reviews, log=Actor.log
                )

                if not summary["reviewsEnabled"]:
                    Actor.log.warning(
                        f"{slug}: no recommendation summary on this page. Facebook "
                        "shows the reviews tab only for pages that have reviews "
                        "switched on, so there may be nothing to collect here."
                    )
                if meta.get("paginationUnavailable"):
                    Actor.log.warning(
                        f"{slug}: kept the {len(reviews)} review(s) already fetched; "
                        "Facebook's pagination query could not be read from the page "
                        "bundles this run."
                    )

                selected = [r for r in reviews if matches_filters(r, filters)]
                Actor.log.info(
                    f"{slug}: {summary.get('ratingSummaryText') or 'no rating summary'} | "
                    f"{len(selected)} review(s) kept of {len(reviews)} fetched "
                    f"in {meta['requestsMade']} request(s)"
                )

                rating_record = {
                    **envelope(SOURCE, slug, "PAGE_RATING"),
                    **summary,
                    "reviewsCollected": len(selected),
                    **{f"sample{k[0].upper()}{k[1:]}": v
                       for k, v in summarise(selected).items()
                       if k in ("recommended", "notRecommended", "reviewsWithText")},
                }
                records.append(rating_record)
                await Actor.push_data(rating_record)

                for review in selected:
                    record = {
                        **envelope(SOURCE, slug, "REVIEW"),
                        "slug": slug,
                        "pageName": summary.get("pageName"),
                        "pageUrl": summary.get("pageUrl"),
                        "ratingSummaryText": summary.get("ratingSummaryText"),
                        "recommendPercent": summary.get("recommendPercent"),
                        "reviewCount": summary.get("reviewCount"),
                        **review,
                    }
                    records.append(record)
                    kept.append(review)
                    await Actor.push_data(record)

        if emit_summary and kept:
            run_summary = {
                **envelope(SOURCE, f"{len(refs)} page(s)", "RUN_SUMMARY"),
                **summarise(kept),
                "pagesRequested": len(refs),
                "pagesFailed": failures,
            }
            records.append(run_summary)
            await Actor.push_data(run_summary)
            Actor.log.info(
                f"Summary: {run_summary['reviewsCollected']} review(s), "
                f"{run_summary['recommended']} recommend, "
                f"{run_summary['notRecommended']} do not, "
                f"{run_summary['reviewsWithText']} with written text"
            )

        await write_exports(records, export_formats, BUILDERS)

        Actor.log.info(f"Finished: {len(kept)} review(s) | {failures} page(s) failed")
        if failures and not kept:
            raise RuntimeError(
                "No page could be read and nothing was collected -- see the ERROR records."
            )
