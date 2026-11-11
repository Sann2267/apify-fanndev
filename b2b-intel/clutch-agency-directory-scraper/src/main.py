"""Mode dispatch for the Clutch.co agency-directory Actor.

Five modes, one source:

* ``directory``  -- a category listing, one record per agency, with the lead
                    attributes the vein is actually bought for (min project size,
                    hourly rate, headcount, location, service mix, website) and
                    with paid placement labelled rather than blended into the rank.
* ``profile``    -- one agency in full, from the page's JSON-LD plus the summary
                    strip and focus charts that JSON-LD does not carry.
* ``reviews``    -- one record per client review: four sub-ratings, project size,
                    project length, reviewer role and company.
* ``categories`` -- the directory URLs themselves, from the sitemap, so a user can
                    find valid inputs instead of guessing slugs.
* ``reference``  -- probes the source and re-tests the assumptions this Actor
                    rests on: the TLS matrix, the ``?page=1`` alias, and how many
                    rows on a page are pinned blocks rather than ranked results.
"""

import asyncio
import logging
import urllib.parse as up

from apify import Actor

from src.client import Blocked, ClutchClient, NotFound
from src.constants import (
    BASE,
    DEFAULT_MAX_PAGES,
    DEFAULT_REVIEW_PAGES,
    EXPECTED,
    MODES,
    ROBOTS_DISALLOWED_PARAMS,
    ROBOTS_DISALLOWED_PREFIXES,
    SAMPLE_CATEGORIES,
    SITEMAP_INDEX,
    TLS_CHALLENGED,
    TLS_LADDER,
)
from src.extractor import (
    category_record,
    now_iso,
    parse_directory,
    parse_profile,
    parse_reviews,
    parse_sitemap,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


# -- input helpers ---------------------------------------------------------


def strip_disallowed(url: str) -> tuple[str, list[str]]:
    """Remove the query parameters clutch.co/robots.txt disallows.

    Returns the cleaned URL and the names that were dropped, so the run says out
    loud that it narrowed the request rather than silently sending it anyway.
    """
    parsed = up.urlparse(url)
    if not parsed.query:
        return url, []
    kept, dropped = [], []
    for key, value in up.parse_qsl(parsed.query, keep_blank_values=True):
        if key in ROBOTS_DISALLOWED_PARAMS:
            dropped.append(key)
        else:
            kept.append((key, value))
    cleaned = up.urlunparse(parsed._replace(query=up.urlencode(kept)))
    return cleaned, dropped


def normalize_category(raw: str) -> str:
    """'web-developers', '/seo-firms', 'id/web-developers' or a full URL -> URL."""
    value = (raw or "").strip()
    if not value:
        raise ValueError("Empty category. Use a slug such as 'web-developers' or a full clutch.co URL.")
    if value.startswith("http"):
        parsed = up.urlparse(value)
        if "clutch.co" not in parsed.netloc:
            raise ValueError(f"{value!r} is not a clutch.co URL.")
        url = value
    else:
        url = f"{BASE}/{value.lstrip('/')}"
    path = up.urlparse(url).path
    for prefix in ROBOTS_DISALLOWED_PREFIXES:
        if path.startswith(prefix):
            raise ValueError(f"{path} is disallowed by clutch.co/robots.txt and will not be fetched.")
    cleaned, dropped = strip_disallowed(url)
    if dropped:
        Actor.log.warning(f"dropped robots-disallowed parameters {dropped} from {url}")
    return cleaned


def normalize_profile(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise ValueError("Empty profile. Use a slug such as 'imaginovation' or a full profile URL.")
    if value.startswith("http"):
        parsed = up.urlparse(value)
        if "clutch.co" not in parsed.netloc:
            raise ValueError(f"{value!r} is not a clutch.co URL.")
        path = parsed.path
    else:
        path = value if value.startswith("/") else f"/profile/{value}"
    if not path.startswith("/profile/"):
        raise ValueError(f"{value!r} is not a profile URL -- expected /profile/<slug>.")
    url, _ = strip_disallowed(f"{BASE}{path}")
    return url.rstrip("/")


def page_url(base_url: str, page: int) -> str:
    """Page 1 is the bare URL.

    ``?page=1`` does not return page 1 -- it returns page 2, byte-for-byte
    identical to ``?page=2`` (measured on /web-developers, 2026-09-18). A naive
    ``for p in 1..N`` loop therefore skips page 1 and emits page 2 twice.
    """
    if page <= 1:
        return base_url
    joiner = "&" if "?" in base_url else "?"
    return f"{base_url}{joiner}page={page}"


def as_list(value, fallback: list[str]) -> list[str]:
    if value is None:
        return list(fallback)
    if isinstance(value, str):
        items = [v.strip() for v in value.replace("\n", ",").split(",")]
    elif isinstance(value, list):
        items = []
        for entry in value:
            if isinstance(entry, dict):
                items.append(str(entry.get("url") or entry.get("value") or ""))
            else:
                items.append(str(entry))
    else:
        return list(fallback)
    items = [i.strip() for i in items if i and i.strip()]
    return items or list(fallback)


# -- output ----------------------------------------------------------------


class Sink:
    """Push with a run-wide cap and a run-wide dedupe key."""

    def __init__(self, max_items: int):
        self.max_items = max_items or 0
        self.pushed = 0
        self.skipped_duplicates = 0
        self._seen: set[str] = set()

    @property
    def full(self) -> bool:
        return bool(self.max_items) and self.pushed >= self.max_items

    async def push(self, record: dict, input_value: str, source: str, dedupe_key: str | None = None) -> bool:
        if self.full:
            return False
        if dedupe_key is not None:
            if dedupe_key in self._seen:
                self.skipped_duplicates += 1
                return False
            self._seen.add(dedupe_key)
        record.setdefault("recordType", "PROVIDER")
        record["_input"] = input_value
        record["_source"] = source
        record["_scrapedAt"] = now_iso()
        await Actor.push_data(record)
        self.pushed += 1
        return True

    async def error(self, input_value: str, message: str, where: str) -> None:
        await Actor.push_data(
            {
                "recordType": "ERROR",
                "_input": input_value,
                "_source": "error",
                "_scrapedAt": now_iso(),
                "error": message[:600],
                "where": where,
            }
        )


# -- modes -----------------------------------------------------------------


async def run_directory(client: ClutchClient, sink: Sink, params: dict) -> None:
    categories = params["categories"]
    max_pages = params["maxPages"]
    include_pinned = params["includePinnedRows"]
    include_paid = params["includePaidPlacements"]

    for raw in categories:
        if sink.full:
            break
        try:
            base_url = normalize_category(raw)
        except ValueError as exc:
            await sink.error(str(raw), str(exc), "normalize_category")
            continue

        for page in range(1, max_pages + 1):
            if sink.full:
                break
            url = page_url(base_url, page)
            try:
                html = await client.get_text(url)
            except (Blocked, NotFound) as exc:
                await sink.error(raw, f"{type(exc).__name__}: {exc}", url)
                break

            parsed = parse_directory(html, base_url, page)
            rows = parsed["records"]
            if not rows:
                # A page past the end answers 200 with a title and no rows --
                # the end of the list is silence, not a 404.
                Actor.log.info(f"{url} returned 0 rows -- end of the list")
                break

            # Ranked results are emitted before paid and pinned rows. Page 1 of a
            # busy category is 49 sponsors to 7 ranked rows, so a run with a
            # maxItems cap would otherwise fill up entirely with advertising and
            # never reach the ranking the user asked for. Every row keeps its own
            # rowType and positionOnPage, so nothing about the page is lost.
            rows.sort(key=lambda r: (not r["isRankedResult"], r["isPinnedBlock"]))

            emitted = 0
            for record in rows:
                if sink.full:
                    break
                if record["isPinnedBlock"] and not include_pinned:
                    continue
                if record["isPaidPlacement"] and not include_paid:
                    continue
                record["totalCompaniesClaim"] = parsed["totalCompaniesClaim"]
                record["lastPageInPager"] = parsed["lastPageInPager"]
                # Pinned rows (Leaders Matrix, featured) are identical on every
                # page of a category, so the provider id is the dedupe key.
                if await sink.push(record, raw, "clutch-directory", dedupe_key=f"{base_url}|{record['providerId']}"):
                    emitted += 1

            Actor.log.info(
                f"{url}: {parsed['rowCount']} rows "
                f"({parsed['rankedCount']} ranked, {parsed['pinnedCount']} pinned, "
                f"{parsed['paidCount']} paid) -> {emitted} new"
            )
            if parsed["rankedCount"] == 0 and page > 1:
                Actor.log.info("no ranked rows on this page -- stopping this category")
                break


async def run_profile(client: ClutchClient, sink: Sink, params: dict) -> None:
    for raw in params["profiles"]:
        if sink.full:
            break
        try:
            url = normalize_profile(raw)
        except ValueError as exc:
            await sink.error(str(raw), str(exc), "normalize_profile")
            continue
        try:
            html = await client.get_text(url)
        except (Blocked, NotFound) as exc:
            await sink.error(raw, f"{type(exc).__name__}: {exc}", url)
            continue
        record = parse_profile(html, url)
        if not record["hasLdJson"] and not record["name"]:
            await sink.error(raw, "profile page carried neither JSON-LD nor a name", url)
            continue
        await sink.push(record, raw, "clutch-profile-ldjson", dedupe_key=f"profile|{url}")


async def run_reviews(client: ClutchClient, sink: Sink, params: dict) -> None:
    max_pages = params["maxReviewPages"]
    for raw in params["profiles"]:
        if sink.full:
            break
        try:
            url = normalize_profile(raw)
        except ValueError as exc:
            await sink.error(str(raw), str(exc), "normalize_profile")
            continue

        expected_total = None
        seen_for_profile = 0
        for page in range(1, max_pages + 1):
            if sink.full:
                break
            target = page_url(url, page)
            try:
                html = await client.get_text(target)
            except (Blocked, NotFound) as exc:
                await sink.error(raw, f"{type(exc).__name__}: {exc}", target)
                break

            if expected_total is None:
                expected_total = parse_profile(html, url).get("reviewCount")

            reviews = parse_reviews(html, url, page)
            if not reviews:
                Actor.log.info(f"{target}: no review blocks -- end of this profile's reviews")
                break
            new = 0
            for record in reviews:
                if sink.full:
                    break
                record["providerReviewCount"] = expected_total
                key = record["reviewId"] or f"{url}|{page}|{record['title']}|{record['datePublished']}"
                if await sink.push(record, raw, "clutch-profile-reviews", dedupe_key=f"review|{key}"):
                    new += 1
                    seen_for_profile += 1
            Actor.log.info(f"{target}: {len(reviews)} review blocks -> {new} new (profile claims {expected_total})")
            if new == 0:
                break
            # The count is per profile, not per run: a run over several profiles
            # would otherwise stop the second profile early on the first one's total.
            if expected_total and seen_for_profile >= expected_total:
                Actor.log.info(f"collected all {expected_total} reviews this profile claims")
                break


async def run_categories(client: ClutchClient, sink: Sink, params: dict) -> None:
    prefix = (params["categoryFilter"] or "").strip().lower()
    max_shards = params["maxSitemapShards"]

    try:
        index = await client.get_text(SITEMAP_INDEX)
    except (Blocked, NotFound) as exc:
        await sink.error("sitemap", f"{type(exc).__name__}: {exc}", SITEMAP_INDEX)
        return
    shards = [u for u in parse_sitemap(index) if "sitemap-directory" in u]
    Actor.log.info(f"sitemap index lists {len(shards)} directory shards")

    for shard in shards[:max_shards]:
        if sink.full:
            break
        try:
            xml = await client.get_text(shard)
        except (Blocked, NotFound) as exc:
            await sink.error("sitemap", f"{type(exc).__name__}: {exc}", shard)
            continue
        urls = parse_sitemap(xml)
        Actor.log.info(f"{shard}: {len(urls)} category URLs")
        for url in urls:
            if sink.full:
                break
            if prefix and prefix not in url.lower():
                continue
            record = category_record(url)
            record["sitemapShard"] = shard
            await sink.push(record, prefix or "all", "clutch-sitemap", dedupe_key=f"cat|{url}")


async def run_reference(client: ClutchClient, sink: Sink, params: dict) -> None:
    """Probe the source and re-test the design assumptions, per the portfolio
    convention that every Actor can prove its own source is still shaped the way
    it was built for."""
    category = normalize_category((params["categories"] or list(SAMPLE_CATEGORIES))[0])

    # 1. TLS matrix, re-measured rather than quoted from the recon notes.
    matrix = []
    for profile in (*TLS_LADDER, *TLS_CHALLENGED):
        matrix.append(await client.probe(category, profile))
    await sink.push(
        {
            "recordType": "SURFACE",
            "check": "tls-matrix",
            "url": category,
            "tlsMatrix": matrix,
            "profilesAnswering": [m["profile"] for m in matrix if m.get("status") == 200 and not m.get("challenged")],
            "profilesChallenged": [m["profile"] for m in matrix if m.get("challenged") or m.get("status") == 403],
            "expectedAnswering": list(TLS_LADDER),
            "note": "Cloudflare gates on the TLS fingerprint. Three of six profiles were challenged during recon.",
        },
        category,
        "reference",
    )

    # 2. Page composition: how much of a page is a ranked result at all.
    page1 = parse_directory(await client.get_text(category), category, 1)
    page3 = parse_directory(await client.get_text(page_url(category, 3)), category, 3)
    page4 = parse_directory(await client.get_text(page_url(category, 4)), category, 4)
    ids3 = {r["providerId"] for r in page3["records"] if r["isPinnedBlock"]}
    ids4 = {r["providerId"] for r in page4["records"] if r["isPinnedBlock"]}
    ranked3 = {r["providerId"] for r in page3["records"] if r["isRankedResult"]}
    ranked4 = {r["providerId"] for r in page4["records"] if r["isRankedResult"]}
    await sink.push(
        {
            "recordType": "SURFACE",
            "check": "page-composition",
            "url": category,
            "page1": {k: page1[k] for k in ("rowCount", "rankedCount", "pinnedCount", "paidCount")},
            "page3": {k: page3[k] for k in ("rowCount", "rankedCount", "pinnedCount", "paidCount")},
            "pinnedRepeatedAcrossPages": len(ids3 & ids4),
            "rankedOverlapAcrossPages": len(ranked3 & ranked4),
            "totalCompaniesClaim": page1["totalCompaniesClaim"],
            "lastPageInPager": page1["lastPageInPager"],
            "expected": EXPECTED,
            "note": (
                "pinnedRepeatedAcrossPages is the count of rows that are identical on "
                "consecutive pages; rankedOverlapAcrossPages should be 0. If it is not, "
                "pagination has changed and the dedupe key matters more than it did."
            ),
        },
        category,
        "reference",
    )

    # 3. The ?page=1 alias -- the trap this Actor is built around.
    bare = parse_directory(await client.get_text(category), category, 1)
    p1 = parse_directory(await client.get_text(f"{category}?page=1"), category, 1)
    p2 = parse_directory(await client.get_text(f"{category}?page=2"), category, 2)
    bare_ids = {r["providerId"] for r in bare["records"] if r["isRankedResult"]}
    p1_ids = {r["providerId"] for r in p1["records"] if r["isRankedResult"]}
    p2_ids = {r["providerId"] for r in p2["records"] if r["isRankedResult"]}
    await sink.push(
        {
            "recordType": "SURFACE",
            "check": "page-1-alias",
            "url": category,
            "bareUrlTitle": bare["pageTitle"],
            "page1Title": p1["pageTitle"],
            "page2Title": p2["pageTitle"],
            "page1EqualsPage2": p1_ids == p2_ids and bool(p1_ids),
            "page1EqualsBareUrl": p1_ids == bare_ids and bool(p1_ids),
            "note": (
                "Measured 2026-09-18: ?page=1 returns page 2, not page 1. Page 1 is the "
                "bare URL. If page1EqualsBareUrl ever becomes true, the alias was fixed "
                "upstream and page_url() can be simplified."
            ),
        },
        category,
        "reference",
    )

    # 4. Profile surface: does JSON-LD still carry the money fields.
    profile_url = None
    for record in bare["records"]:
        if record.get("profileUrl"):
            profile_url = record["profileUrl"]
            break
    if profile_url:
        profile = parse_profile(await client.get_text(profile_url), profile_url)
        reviews = parse_reviews(await client.get_text(profile_url), profile_url, 1)
        await sink.push(
            {
                "recordType": "SURFACE",
                "check": "profile-surface",
                "url": profile_url,
                "hasLdJson": profile["hasLdJson"],
                "ldJsonFieldsPresent": sorted(
                    k
                    for k in ("website", "telephone", "foundingDate", "priceRange", "rating", "streetAddress")
                    if profile.get(k)
                ),
                "summaryStripFieldsPresent": sorted(
                    k for k in ("minProjectSize", "hourlyRate", "employees", "yearFounded") if profile.get(k)
                ),
                "chartsPresent": sorted(
                    k for k in ("serviceLines", "focusAreas", "industries") if profile.get(k)
                ),
                "reviewBlocksOnPage": len(reviews),
                "reviewsWithId": sum(1 for r in reviews if r["reviewId"]),
                "profileClaimsReviewCount": profile["reviewCount"],
                "note": (
                    "The JSON-LD review array is not the page's review list -- it answered "
                    "16, 12 and 6 entries on three pages of the same profile, so reviews are "
                    "read from the HTML blocks instead."
                ),
            },
            profile_url,
            "reference",
        )

    await sink.push(
        {
            "recordType": "SURFACE",
            "check": "run-summary",
            "url": category,
            "winningTlsProfile": client.winning_profile,
            "requestsMade": client.requests,
            "challengesSeen": client.challenges,
            "proxyUsed": bool(params.get("proxyUsed")),
        },
        category,
        "reference",
    )


# -- entrypoint ------------------------------------------------------------


async def main() -> None:
    async with Actor:
        raw_input = await Actor.get_input() or {}
        mode = (raw_input.get("mode") or "directory").strip().lower()
        if mode not in MODES:
            raise input_error(f"Unknown mode {mode!r}. Use one of {', '.join(MODES)}.")

        # `create_proxy_configuration` is only called when the input actually
        # asks for a proxy. Calling it unconditionally raises on a run that
        # wanted no proxy at all -- it goes looking for a proxy password and
        # fails the whole Actor before a single request is made.
        proxy_url = None
        proxy_factory = None
        proxy_input = raw_input.get("proxyConfiguration") or {}
        wants_proxy = bool(proxy_input.get("useApifyProxy") or proxy_input.get("proxyUrls"))
        if wants_proxy:
            proxy_config = await Actor.create_proxy_configuration(actor_proxy_input=proxy_input)
            if proxy_config:
                # Pre-mint sessions: new_url() is async, the client rotates from
                # sync code when it opens a fresh session after a challenge.
                pool = [await proxy_config.new_url(f"clutch{i}") for i in range(12)]
                proxy_url = pool[0]
                cursor = {"i": 0}

                def proxy_factory():
                    cursor["i"] = (cursor["i"] + 1) % len(pool)
                    return pool[cursor["i"]]

                Actor.log.info("using Apify Proxy")
        if not proxy_url:
            Actor.log.warning(
                "no proxy configured -- since 2026-10 Cloudflare challenges every "
                "request from Apify's datacenter IPs; enable the Residential proxy")

        max_pages = int(raw_input.get("maxPages") or DEFAULT_MAX_PAGES)
        params = {
            "categories": as_list(raw_input.get("categories"), [SAMPLE_CATEGORIES[0]]),
            "profiles": as_list(raw_input.get("profileUrls"), []),
            "maxPages": max(1, max_pages),
            "maxReviewPages": max(1, int(raw_input.get("maxReviewPages") or DEFAULT_REVIEW_PAGES)),
            "includePinnedRows": bool(raw_input.get("includePinnedRows", False)),
            "includePaidPlacements": bool(raw_input.get("includePaidPlacements", True)),
            "categoryFilter": raw_input.get("categoryFilter") or "",
            "maxSitemapShards": max(1, int(raw_input.get("maxSitemapShards") or 1)),
            "proxyUsed": bool(proxy_url),
        }

        if mode in ("profile", "reviews") and not params["profiles"]:
            raise input_error(
                f"Mode {mode!r} needs at least one profile: pass profileUrls, e.g. "
                "'imaginovation' or 'https://clutch.co/profile/imaginovation'."
            )

        sink = Sink(int(raw_input.get("maxItems") or 0))
        client = ClutchClient(proxy_url=proxy_url, profile=raw_input.get("tlsProfile") or None,
                              proxy_factory=proxy_factory)
        runner = {
            "directory": run_directory,
            "profile": run_profile,
            "reviews": run_reviews,
            "categories": run_categories,
            "reference": run_reference,
        }[mode]

        try:
            await runner(client, sink, params)
        finally:
            await client.close()

        Actor.log.info(
            f"mode={mode} pushed={sink.pushed} duplicates_skipped={sink.skipped_duplicates} "
            f"requests={client.requests} challenges={client.challenges} tls={client.winning_profile}"
        )
        if sink.pushed == 0:
            # Fail loud: an empty dataset that exits 0 is indistinguishable from
            # a category that genuinely has no agencies.
            raise RuntimeError(
                f"mode={mode} produced 0 records after {client.requests} requests "
                f"({client.challenges} challenges). Check the input, or run mode=reference."
            )


def run() -> None:
    asyncio.run(main())
