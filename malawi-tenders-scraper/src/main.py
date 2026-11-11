import asyncio

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, fetch_notice_page
from src.constants import NOTICE_TYPES
from src.extractor import UnexpectedShape, build_error_record, build_record, parse_notice_table

ALL_LABEL = "(all notices)"

DEFAULT_NOTICE_TYPES = ["tenders"]


def _matches(row: dict, keyword: str) -> bool:
    needle = keyword.strip().lower()
    haystack = " ".join(str(v) for v in row.values() if isinstance(v, str)).lower()
    return needle in haystack


async def fetch_notice_rows(notice_type: str, proxy_url: str | None) -> list[dict]:
    """Fetches one PPDA notice-board page and parses every row on it. Raises
    FetchFailed/RequestException/ConnectionError on a network/blocking
    problem, or UnexpectedShape (never silently swallowed -- fail loud on
    real schema drift, per project convention) if the page no longer looks
    like the table this actor was built against.
    """
    path = NOTICE_TYPES[notice_type]["path"]
    html_text = await fetch_notice_page(path, proxy_url=proxy_url)
    return parse_notice_table(html_text, notice_type)


def build_job_records(
    rows: list[dict], notice_type: str, label: str, only_open: bool, max_results: int
) -> list[dict]:
    filtered = [(i, r) for i, r in enumerate(rows) if label == ALL_LABEL or _matches(r, label)]
    records = [build_record(i, r, notice_type, label) for i, r in filtered]
    if only_open and notice_type == "tenders":
        records = [rec for rec in records if rec.get("isClosed") is not True]
    total = len(records)
    truncated = total > max_results
    records = records[:max_results]
    for rec in records:
        rec["_totalMatches"] = total
        rec["_truncated"] = truncated
    return records


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        notice_types = [
            nt for nt in (input_data.get("noticeTypes") or DEFAULT_NOTICE_TYPES) if nt in NOTICE_TYPES
        ] or DEFAULT_NOTICE_TYPES

        labels = [k for k in (input_data.get("keywords") or []) if isinstance(k, str) and k.strip()]
        if input_data.get("keyword"):
            labels.insert(0, input_data["keyword"])
        labels = [k.strip() for k in labels] or [ALL_LABEL]

        only_open = bool(input_data.get("onlyOpenTenders", False))
        max_results = int(input_data.get("maxResults", 100))
        max_results = max(1, min(max_results, 1000))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None

        Actor.log.info(
            f"Fetching PPDA notice board(s) {notice_types} (labels={labels}, "
            f"onlyOpenTenders={only_open}, maxResults={max_results})"
        )

        for notice_type in notice_types:
            try:
                rows = await fetch_notice_rows(notice_type, proxy_url)
            except (FetchFailed, RequestException, ConnectionError) as e:
                # NOTE: curl_cffi's own ConnectionError does NOT inherit from
                # Python's builtin ConnectionError -- both listed explicitly
                # per portfolio-wide convention.
                for label in labels:
                    await Actor.push_data(build_error_record(notice_type, label, "blocked_or_transient", repr(e)))
                continue
            except UnexpectedShape:
                # Fail loud on real schema drift -- must NOT be silently
                # swallowed into a generic error record, per project
                # convention.
                raise

            Actor.log.info(f"Parsed {len(rows)} '{notice_type}' notice(s) currently on the board")

            for label in labels:
                records = build_job_records(rows, notice_type, label, only_open, max_results)
                if not records:
                    await Actor.push_data(build_error_record(notice_type, label, "no_results"))
                    continue
                await Actor.push_data(records)
