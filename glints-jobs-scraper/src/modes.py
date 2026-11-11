"""One coroutine per actor mode. Each yields finished dataset records.

Every mode emits at least one row per input, including a diagnostic ERROR row
on failure, so a downstream consumer never has to tell "not found" apart from
"the actor crashed" by counting rows.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncIterator, Callable

from . import queries
from .client import (
    GlintsBlocked,
    GlintsClient,
    GlintsGraphQLError,
    GlintsLoginRequired,
    GlintsNotFound,
    sitemap_locs,
)
from .constants import (
    ANON_MAX_PAGE,
    COUNTRY_PATH,
    DEFAULT_COUNTRY,
    MAX_PAGE_SIZE,
    RECORD_COMPANY,
    RECORD_FILTERS,
    RECORD_JOB,
    RECORD_JOB_DETAIL,
    RECORD_SKILL,
    RECORD_SUGGESTION,
    ROBOTS_TXT,
    SITEMAP_INDEX,
)
from .parsers import (
    country_from_url,
    envelope,
    error_record,
    extract_uuid,
    flatten_company,
    flatten_job,
)

log = logging.getLogger("glints.modes")

SRC_SEARCH = "S1-gql-searchJobsV3"
SRC_DETAIL = "S1-gql-getJobById"
SRC_COMPANY = "S1-gql-getCompanyById"
SRC_SIMILAR = "S1-gql-getSimilarJobs"
SRC_FILTERS = "S1-gql-getJobSearchFiltersV2"
SRC_SUGGEST = "S1-gql-getJobTitleSuggestions"
SRC_SKILLS = "S1-gql-skills"
SRC_SITEMAP = "S2-sitemap"


def _referer(country: str) -> str:
    path = COUNTRY_PATH.get((country or "").upper(), COUNTRY_PATH[DEFAULT_COUNTRY])
    return f"https://glints.com/{path}/opportunities/jobs/explore"


def build_search_condition(inp: dict[str, Any], term: str | None) -> dict[str, Any]:
    """Assemble a JobSearchConditionInput from actor input.

    Only keys the user actually set are sent. Glints treats an explicitly null
    filter differently from an absent one in a few places, and an empty list is
    not the same as no list, so nothing is padded with defaults here.
    """
    country = (inp.get("countryCode") or DEFAULT_COUNTRY).upper()
    data: dict[str, Any] = {
        "CountryCode": [country],
        "page": 1,
        "pageSize": min(int(inp.get("pageSize") or MAX_PAGE_SIZE), MAX_PAGE_SIZE),
        "includeExternalJobs": bool(inp.get("includeExternalJobs", True)),
    }
    if term:
        data["SearchTerm"] = [term]
    if inp.get("jobTypes"):
        data["type"] = list(inp["jobTypes"])
    if inp.get("workArrangements"):
        data["workArrangementOptions"] = list(inp["workArrangements"])
    if inp.get("educationLevels"):
        data["educationLevels"] = list(inp["educationLevels"])
    if inp.get("lastUpdatedRange") and inp["lastUpdatedRange"] != "ANY_TIME":
        data["lastUpdatedAtRange"] = inp["lastUpdatedRange"]
    if inp.get("sortBy"):
        data["sortBy"] = inp["sortBy"]
    if inp.get("locationIds"):
        data["LocationIds"] = list(inp["locationIds"])
    if inp.get("companyIds"):
        data["CompanyId"] = list(inp["companyIds"])
    if inp.get("categoryIds"):
        data["HierarchicalJobCategoryIds"] = list(inp["categoryIds"])
    if inp.get("skillIds"):
        data["SkillIds"] = list(inp["skillIds"])
    if inp.get("minYearsOfExperience") is not None:
        data["minYearsOfExperience"] = int(inp["minYearsOfExperience"])
    if inp.get("maxYearsOfExperience") is not None:
        data["maxYearsOfExperience"] = int(inp["maxYearsOfExperience"])

    salary_min = inp.get("salaryMin")
    salary_max = inp.get("salaryMax")
    if salary_min is not None or salary_max is not None:
        salary: dict[str, Any] = {"currency": inp.get("salaryCurrency") or "IDR"}
        if salary_min is not None:
            salary["minimum"] = int(salary_min)
        if salary_max is not None:
            salary["maximum"] = int(salary_max)
        data["SalaryFilter"] = salary
    return data


# -- mode: search ----------------------------------------------------------


async def mode_search(
    client: GlintsClient, inp: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Run one search per term and stream deduplicated job cards.

    Anonymous callers get page 1 only -- page 2 answers 403 "please login for
    more information" -- so breadth comes from running many narrow queries
    rather than paging one broad one. Each term is a separate page-1 query and
    results are deduplicated by job id across the whole fan-out.
    """
    country = (inp.get("countryCode") or DEFAULT_COUNTRY).upper()
    terms: list[str | None] = [t.strip() for t in (inp.get("searchTerms") or []) if t and t.strip()]
    if not terms:
        # No keyword still returns the market's newest 50 postings.
        terms = [None]
    max_items = int(inp.get("maxItems") or 0)
    referer = _referer(country)
    seen: set[str] = set()
    emitted = 0

    for term in terms:
        if max_items and emitted >= max_items:
            break
        label = term or f"(all jobs in {country})"
        data = build_search_condition(inp, term)
        try:
            result = await client.graphql("searchJobsV3", queries.SEARCH_JOBS, {"data": data}, referer)
        except GlintsLoginRequired as exc:
            yield error_record(label, "login_required", str(exc))
            continue
        except (GlintsBlocked, GlintsGraphQLError) as exc:
            yield error_record(label, "search_failed", str(exc))
            continue

        page = result.get("searchJobsV3") or {}
        jobs = page.get("jobsInPage") or []
        if not jobs:
            yield error_record(label, "no_results", f"searchJobsV3 returned 0 jobs for {label}")
            continue

        new_for_term = 0
        for job in jobs:
            job_id = job.get("id")
            if not job_id or job_id in seen:
                continue
            seen.add(job_id)
            record = envelope(label, SRC_SEARCH, RECORD_JOB, flatten_job(job, country))
            record["searchTerm"] = term
            # hasMore is true on essentially every page-1 response because the
            # corpus is larger than 50; it says nothing a caller can act on
            # without an account, so it is reported rather than paged on.
            record["_warning"] = (
                "anon_page_1_only" if page.get("hasMore") else None
            )
            if record["_warning"] is None:
                record.pop("_warning")
            yield record
            emitted += 1
            new_for_term += 1
            if max_items and emitted >= max_items:
                break

        log.info(
            "search %r -> %d jobs (%d new, %d unique so far)",
            label, len(jobs), new_for_term, len(seen),
        )
        if len(jobs) >= MAX_PAGE_SIZE and page.get("hasMore"):
            log.info(
                "Term %r filled the anonymous page-1 ceiling of %d. "
                "Narrow it with filters or add more terms to reach deeper.",
                label, MAX_PAGE_SIZE,
            )


# -- mode: jobDetail -------------------------------------------------------


async def _fetch_job_detail(
    client: GlintsClient, raw_input: str, job_id: str, country: str
) -> dict[str, Any]:
    try:
        data = await client.graphql(
            "getJobById", queries.JOB_BY_ID, {"id": job_id}, _referer(country)
        )
    except GlintsNotFound as exc:
        return error_record(raw_input, "not_found", str(exc))
    except (GlintsBlocked, GlintsGraphQLError, GlintsLoginRequired) as exc:
        return error_record(raw_input, "detail_failed", str(exc))
    job = data.get("getJobById")
    if not job:
        return error_record(
            raw_input, "not_found", f"getJobById returned null for {job_id}"
        )
    return envelope(raw_input, SRC_DETAIL, RECORD_JOB_DETAIL, flatten_job(job, country))


async def _bounded_gather(
    items: list[Any],
    worker: Callable[[Any], Any],
    concurrency: int,
) -> AsyncIterator[dict[str, Any]]:
    """Run worker over items with bounded concurrency, yielding as they finish."""
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def guarded(item: Any) -> dict[str, Any]:
        async with semaphore:
            return await worker(item)

    tasks = [asyncio.create_task(guarded(i)) for i in items]
    try:
        for coro in asyncio.as_completed(tasks):
            yield await coro
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()


async def mode_job_detail(
    client: GlintsClient, inp: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    country = (inp.get("countryCode") or DEFAULT_COUNTRY).upper()
    raw_items = inp.get("jobUrlsOrIds") or []
    concurrency = int(inp.get("maxConcurrency") or 5)

    targets: list[tuple[str, str, str]] = []
    for raw in raw_items:
        raw = (raw or "").strip()
        if not raw:
            continue
        job_id = extract_uuid(raw)
        if not job_id:
            yield error_record(raw, "unparsable_input", "No Glints job id found in input")
            continue
        targets.append((raw, job_id, country_from_url(raw, country)))

    if not targets:
        return

    async def worker(item: tuple[str, str, str]) -> dict[str, Any]:
        raw, job_id, cc = item
        return await _fetch_job_detail(client, raw, job_id, cc)

    async for record in _bounded_gather(targets, worker, concurrency):
        yield record


# -- mode: company ---------------------------------------------------------


async def mode_company(
    client: GlintsClient, inp: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Emit a COMPANY row per employer, plus a JOB row per open posting.

    getCompanyById returns the company's full open-job list in one call and is
    not subject to the search login wall, so this is the cheapest route to
    every vacancy at a named employer.
    """
    country = (inp.get("countryCode") or DEFAULT_COUNTRY).upper()
    include_jobs = bool(inp.get("includeCompanyJobs", True))
    concurrency = int(inp.get("maxConcurrency") or 5)

    targets: list[tuple[str, str, str]] = []
    for raw in inp.get("companyUrlsOrIds") or []:
        raw = (raw or "").strip()
        if not raw:
            continue
        company_id = extract_uuid(raw)
        if not company_id:
            yield error_record(raw, "unparsable_input", "No Glints company id found in input")
            continue
        targets.append((raw, company_id, country_from_url(raw, country)))

    if not targets:
        return

    async def worker(item: tuple[str, str, str]) -> dict[str, Any]:
        raw, company_id, cc = item
        variables = {
            "id": company_id,
            "data": {"limit": 200, "status": "OPEN"},
        }
        try:
            data = await client.graphql(
                "getCompanyById", queries.COMPANY_BY_ID, variables, _referer(cc)
            )
        except GlintsNotFound as exc:
            return error_record(raw, "not_found", str(exc))
        except (GlintsBlocked, GlintsGraphQLError, GlintsLoginRequired) as exc:
            return error_record(raw, "company_failed", str(exc))
        company = data.get("getCompanyById")
        if not company:
            return error_record(
                raw, "not_found", f"getCompanyById returned null for {company_id}"
            )
        return {"_raw": raw, "_cc": cc, "company": company}

    async for result in _bounded_gather(targets, worker, concurrency):
        if "_error" in result:
            yield result
            continue
        raw, cc, company = result["_raw"], result["_cc"], result["company"]
        jobs = company.pop("jobs", None) or []
        yield envelope(raw, SRC_COMPANY, RECORD_COMPANY, flatten_company(company, cc))
        if include_jobs:
            for job in jobs:
                job.setdefault("company", {
                    "id": company.get("id"),
                    "name": company.get("name"),
                    "brandName": company.get("brandName"),
                    "logo": company.get("logo"),
                    "status": company.get("status"),
                    "isVIP": company.get("isVIP"),
                })
                yield envelope(raw, SRC_COMPANY, RECORD_JOB, flatten_job(job, cc))


# -- mode: similarJobs -----------------------------------------------------


async def mode_similar_jobs(
    client: GlintsClient, inp: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    country = (inp.get("countryCode") or DEFAULT_COUNTRY).upper()
    limit = int(inp.get("similarJobsLimit") or 20)
    for raw in inp.get("jobUrlsOrIds") or []:
        raw = (raw or "").strip()
        if not raw:
            continue
        job_id = extract_uuid(raw)
        if not job_id:
            yield error_record(raw, "unparsable_input", "No Glints job id found in input")
            continue
        cc = country_from_url(raw, country)
        try:
            data = await client.graphql(
                "getSimilarJobs",
                queries.SIMILAR_JOBS,
                {"data": {"jobId": job_id, "limit": limit}},
                _referer(cc),
            )
        except GlintsNotFound as exc:
            yield error_record(raw, "not_found", str(exc))
        except (GlintsBlocked, GlintsGraphQLError, GlintsLoginRequired) as exc:
            yield error_record(raw, "similar_failed", str(exc))
            continue
        jobs = (data.get("getSimilarJobs") or {}).get("list") or []
        if not jobs:
            yield error_record(
                raw, "no_results", "getSimilarJobs returned an empty list"
            )
            continue
        for job in jobs:
            record = envelope(raw, SRC_SIMILAR, RECORD_JOB, flatten_job(job, cc))
            record["similarToJobId"] = job_id
            yield record


# -- mode: sitemapCrawl ----------------------------------------------------


async def mode_sitemap_crawl(
    client: GlintsClient, inp: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Enumerate the corpus from sitemap_index.xml, then hydrate via getJobById.

    This is the route around the page-2 login wall. The sitemaps list every
    indexable posting per market, and getJobById is ungated, so the pair reaches
    the whole public corpus where search alone tops out at 50 rows per query.
    """
    country = (inp.get("countryCode") or DEFAULT_COUNTRY).upper()
    cc_path = COUNTRY_PATH.get(country, COUNTRY_PATH[DEFAULT_COUNTRY])
    max_items = int(inp.get("maxItems") or 100)
    concurrency = int(inp.get("maxConcurrency") or 5)
    include_sourced = bool(inp.get("includeExternalJobs", True))
    hydrate = bool(inp.get("sitemapFetchDetails", True))

    # Cloudflare scores glints.com's static paths separately from its JSON API:
    # the sitemap index can answer 403 to an address the API serves happily.
    # So try the index, then robots.txt, which advertises the same sitemaps and
    # is a different path with its own edge treatment.
    index_xml = ""
    index_error = ""
    for label, url in (("sitemap index", SITEMAP_INDEX), ("robots.txt", ROBOTS_TXT)):
        try:
            index_xml = await client.get_text(url)
        except Exception as exc:  # noqa: BLE001 - one row beats a silent crash
            index_error = f"{label}: {exc}"
            log.warning("Sitemap discovery via %s failed: %s", label, exc)
            continue
        if index_xml:
            log.info("Sitemap discovery succeeded via %s", label)
            break
        index_error = f"{label}: empty response"

    if not index_xml:
        yield error_record(
            f"sitemap:{country}",
            "sitemap_index_failed",
            f"{index_error}. Glints' edge refuses the sitemap paths from this IP "
            f"even though its API answers normally. Enable the proxy "
            f"(RESIDENTIAL) and re-run, or use the 'search' mode, which needs no "
            f"sitemap.",
        )
        return

    wanted = [f"sitemap_job_{cc_path}_"]
    if include_sourced:
        wanted.append(f"sitemap_sourced_job_{cc_path}_")
    # robots.txt advertises only the index, so follow it one level if that is
    # what came back rather than the index document itself.
    locs = sitemap_locs(index_xml) or re.findall(
        r"(?im)^\s*sitemap:\s*(\S+)\s*$", index_xml
    )
    if locs and not any(any(m in loc for m in wanted) for loc in locs):
        for nested in locs:
            if "sitemap_index" not in nested:
                continue
            try:
                nested_xml = await client.get_text(nested)
            except Exception as exc:  # noqa: BLE001
                log.warning("Nested sitemap %s failed: %s", nested, exc)
                continue
            if nested_xml:
                locs = sitemap_locs(nested_xml)
                break

    sitemaps = [loc for loc in locs if any(marker in loc for marker in wanted)]
    if not sitemaps:
        yield error_record(
            f"sitemap:{country}",
            "no_sitemaps",
            f"sitemap_index.xml lists no job sitemaps for market {country}",
        )
        return
    log.info("Market %s: %d job sitemaps in the index", country, len(sitemaps))

    # Collect ids until the cap, pulling one sitemap at a time so a small
    # maxItems does not download hundreds of files first.
    job_ids: list[str] = []
    seen: set[str] = set()
    for sitemap in sitemaps:
        if len(job_ids) >= max_items:
            break
        try:
            xml = await client.get_text(sitemap)
        except Exception as exc:  # noqa: BLE001
            log.warning("Sitemap %s failed: %s", sitemap, exc)
            continue
        for loc in sitemap_locs(xml):
            # Each posting appears twice, once per language prefix. Keep one.
            if "/en/" in loc:
                continue
            job_id = extract_uuid(loc)
            if job_id and job_id not in seen:
                seen.add(job_id)
                job_ids.append(job_id)
                if len(job_ids) >= max_items:
                    break
    log.info("Collected %d job ids from sitemaps", len(job_ids))

    if not job_ids:
        yield error_record(
            f"sitemap:{country}", "no_results", "No job ids found in the market sitemaps"
        )
        return

    if not hydrate:
        for job_id in job_ids:
            record = envelope(f"sitemap:{country}", SRC_SITEMAP, RECORD_JOB, {"id": job_id})
            record["jobUrl"] = f"https://glints.com/{cc_path}/opportunities/jobs/-/{job_id}"
            yield record
        return

    async def worker(job_id: str) -> dict[str, Any]:
        record = await _fetch_job_detail(client, f"sitemap:{country}", job_id, country)
        record.setdefault("_sitemapJobId", job_id)
        return record

    async for record in _bounded_gather(job_ids, worker, concurrency):
        if record.get("_source") == SRC_DETAIL:
            record["_source"] = f"{SRC_SITEMAP}+{SRC_DETAIL}"
        yield record


# -- mode: filters (market facets) ----------------------------------------


async def mode_filters(
    client: GlintsClient, inp: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Emit the facet rail for each search term: who is hiring, and where.

    This is one request per term and carries the top employers, cities,
    sub-districts and job roles that actually have postings for that keyword --
    market structure that would otherwise take dozens of search calls to infer.
    """
    country = (inp.get("countryCode") or DEFAULT_COUNTRY).upper()
    terms = [t.strip() for t in (inp.get("searchTerms") or []) if t and t.strip()] or [""]
    facet_limit = int(inp.get("facetLimit") or 20)

    for term in terms:
        condition: dict[str, Any] = {
            "searchCountryCode": country,
            "maxCompanyFilters": facet_limit,
            "maxCityFilters": facet_limit,
            "maxJobCategoryFilters": facet_limit,
            "maxSalaryCurrencyFilters": facet_limit,
        }
        if term:
            condition["searchTerms"] = [term]
        label = term or f"(all jobs in {country})"
        try:
            data = await client.graphql(
                "getJobSearchFilters",
                queries.SEARCH_FILTERS,
                {"filterCondition": condition},
                _referer(country),
            )
        except (GlintsBlocked, GlintsGraphQLError, GlintsLoginRequired) as exc:
            yield error_record(label, "filters_failed", str(exc))
            continue
        facets = data.get("getJobSearchFiltersV2")
        if not facets:
            yield error_record(label, "no_results", "getJobSearchFiltersV2 returned null")
            continue
        payload = dict(facets)
        payload["searchTerm"] = term or None
        payload["countryCode"] = country
        payload["topCompanyNames"] = [
            c.get("name") for c in (facets.get("companies") or []) if c.get("name")
        ]
        # The `cities` facet is always empty -- same decoy as
        # searchHierarchicalLocations. hierarchicalLocations is the live one.
        payload["topLocationNames"] = [
            loc.get("formattedName") or loc.get("name")
            for loc in (facets.get("hierarchicalLocations") or [])
            if loc.get("formattedName") or loc.get("name")
        ]
        payload["topJobRoleNames"] = [
            r.get("name") for r in (facets.get("jobRoles") or []) if r.get("name")
        ]
        yield envelope(label, SRC_FILTERS, RECORD_FILTERS, payload)


# -- mode: suggestions -----------------------------------------------------


async def mode_suggestions(
    client: GlintsClient, inp: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Autocomplete for a keyword: matching job titles and company names.

    Glints tags each suggestion 'job' or 'company', which makes this usable
    both for keyword research and for discovering employer names to feed into
    the company mode.
    """
    country = (inp.get("countryCode") or DEFAULT_COUNTRY).upper()
    limit = int(inp.get("suggestionLimit") or 20)
    keywords = [k.strip() for k in (inp.get("searchTerms") or []) if k and k.strip()]
    if not keywords:
        yield error_record(
            "(none)", "unparsable_input", "suggestions mode needs at least one search term"
        )
        return

    for keyword in keywords:
        try:
            data = await client.graphql(
                "getJobTitleSuggestions",
                queries.JOB_TITLE_SUGGESTIONS,
                {"keyword": keyword, "countryCode": country, "limit": limit},
                _referer(country),
            )
        except (GlintsBlocked, GlintsGraphQLError, GlintsLoginRequired) as exc:
            yield error_record(keyword, "suggestions_failed", str(exc))
            continue
        block = data.get("getJobTitleSuggestions") or {}
        items = block.get("jobTitleSuggestions") or []
        if not items:
            yield error_record(keyword, "no_results", "No suggestions for this keyword")
            continue
        for item in items:
            yield envelope(
                keyword,
                SRC_SUGGEST,
                RECORD_SUGGESTION,
                {
                    "keyword": keyword,
                    "countryCode": country,
                    "suggestion": item.get("title"),
                    "suggestionType": item.get("type"),
                    "totalSuggestions": block.get("count"),
                },
            )


# -- mode: skills ----------------------------------------------------------


async def mode_skills(
    client: GlintsClient, inp: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Glints' skill taxonomy -- the exact ids the search filter accepts.

    With no search term this walks the full catalogue by offset, which is how
    you get the SkillIds needed to run a precise skill-filtered search.

    Two quirks drive the loop below. Unlike searchJobsV3, `offset` genuinely
    works here, so the catalogue really can be walked. But `limit` caps at 50
    however much is asked for, and the reported `count` of 1000 is not the end
    of the data -- offset 1000 still returns rows while offset 1500 returns
    none. So the stop condition is an empty page, not the reported count.
    """
    terms = [t.strip() for t in (inp.get("searchTerms") or []) if t and t.strip()]
    max_items = int(inp.get("maxItems") or 500)
    page_size = MAX_PAGE_SIZE
    country = (inp.get("countryCode") or DEFAULT_COUNTRY).upper()
    referer = _referer(country)

    async def emit_for(term: str | None) -> AsyncIterator[dict[str, Any]]:
        label = term or "(all skills)"
        offset = 0
        emitted = 0
        seen_ids: set[str] = set()
        while emitted < max_items:
            payload: dict[str, Any] = {"limit": page_size, "offset": offset}
            if term:
                payload["searchTerm"] = term
            else:
                payload["includeAll"] = True
            try:
                data = await client.graphql(
                    "skills", queries.SKILLS, {"input": payload}, referer
                )
            except (GlintsBlocked, GlintsGraphQLError, GlintsLoginRequired) as exc:
                yield error_record(label, "skills_failed", str(exc))
                return
            block = data.get("skills") or {}
            rows = block.get("list") or []
            if not rows:
                if offset == 0:
                    yield error_record(label, "no_results", "skills returned an empty list")
                return
            fresh = [r for r in rows if r.get("id") and r["id"] not in seen_ids]
            if not fresh:
                # The catalogue started repeating: offset has run past its end.
                return
            for row in fresh:
                seen_ids.add(row["id"])
                yield envelope(
                    label,
                    SRC_SKILLS,
                    RECORD_SKILL,
                    {
                        "searchTerm": term,
                        "skillId": row.get("id"),
                        "skillName": row.get("name"),
                        "translationName": row.get("translationName"),
                        "relevanceScore": row.get("relevanceScore"),
                        "totalSkills": block.get("count"),
                    },
                )
                emitted += 1
                if emitted >= max_items:
                    return
            if len(rows) < page_size:
                return
            offset += page_size

    for term in terms or [None]:
        async for record in emit_for(term):
            yield record


MODES: dict[str, Callable[..., AsyncIterator[dict[str, Any]]]] = {
    "search": mode_search,
    "jobDetail": mode_job_detail,
    "company": mode_company,
    "similarJobs": mode_similar_jobs,
    "sitemapCrawl": mode_sitemap_crawl,
    "filters": mode_filters,
    "suggestions": mode_suggestions,
    "skills": mode_skills,
}
