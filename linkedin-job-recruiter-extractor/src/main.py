"""LinkedIn Smart Job Description & Recruiter Extractor -- Apify actor entry point.

This is the one LinkedIn surface that is genuinely open. The guest jobs API
(``/jobs-guest/jobs/api/...``) answers 200 to anonymous callers, paginates
cleanly and carries the full job description, the criteria grid and the
applicant count. No cookie is needed for any of that.

The single exception is the recruiter. LinkedIn does not render the "Meet the
hiring team" block to logged-out visitors -- checked across eight postings, none
carried it -- so the poster's profile is read through Voyager when, and only
when, the buyer supplies their own ``li_at``.

Two filter behaviours are worth knowing, both measured rather than assumed:

* ``f_TPR`` (date posted) really filters.
* ``f_WT`` (workplace), ``f_E`` (experience) and ``f_JT`` (job type) are
  **silently ignored** by the guest endpoint -- passing them returns results
  byte-identical to passing nothing. So those three are applied here as
  client-side filters against each job's own criteria, after the detail is
  fetched, which is the only way to make them mean anything.
"""

from __future__ import annotations

import asyncio
import re

from apify import Actor

from src import exporters
from src.linkedin import LinkedInClient, LinkedInError, proxy_url_from
from src.parse import (
    clean_url,
    collapse,
    company_slug,
    extract_certifications,
    extract_salary,
    extract_tech_stack,
    extract_workplace,
    html_to_text,
    parse_job_criteria,
)
from src.runtime import (
    clamp,
    clamp_float,
    company_domain,
    dedupe,
    envelope,
    error_record,
    job_id,
    notice_record,
    string_list,
)
from src.voyager import first_text, person_from_voyager, walk
from src.input_errors import input_error

SEARCH_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_API = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting"

SOURCE_SEARCH = "jobs-guest-search"
SOURCE_DETAIL = "jobs-guest-jobPosting"
SOURCE_RECRUITER = "voyager-jobPosting"

# LinkedIn's own codes. Only DATE_POSTED is honoured by the guest endpoint.
DATE_POSTED = {"past24Hours": "r86400", "pastWeek": "r604800", "pastMonth": "r2592000"}

# Each page of search results is exactly ten postings, and the endpoint stops
# returning anything past roughly 975 -- 1000 answers HTTP 400 outright.
PAGE_SIZE = 10
SEARCH_CEILING = 975

COLUMNS = [
    "jobTitle", "companyName", "companyUrl", "companyDomain", "location",
    "workplaceType", "employmentType", "seniorityLevel", "jobFunction",
    "industries", "techStack", "certifications", "salaryMin", "salaryMax",
    "salaryCurrency", "salaryPeriod", "applicants", "postedAgo", "jobUrl",
    "recruiterName", "recruiterHeadline", "recruiterProfileUrl", "recordType",
]

_CARD = re.compile(r'<li>(.*?)</li>', re.S)
_CARD_ID = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
_CARD_TITLE = re.compile(r'class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</h3>', re.S)
_CARD_COMPANY = re.compile(r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>(.*?)</h4>', re.S)
_CARD_COMPANY_URL = re.compile(r'href="(https://[a-z\.]*linkedin\.com/company/[^"?]+)')
_CARD_LOCATION = re.compile(r'class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</span>', re.S)
_CARD_DATE = re.compile(r'datetime="([\d\-]+)"')

_DESCRIPTION = re.compile(
    r'class="[^"]*show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', re.S
)
_APPLICANTS = re.compile(r'class="[^"]*num-applicants__caption[^"]*"[^>]*>(.*?)</span>', re.S)
_POSTED_AGO = re.compile(r'class="[^"]*posted-time-ago__text[^"]*"[^>]*>(.*?)</span>', re.S)
_SALARY_BLOCK = re.compile(r'class="[^"]*compensation__salary[^"]*"[^>]*>(.*?)</div>', re.S)


def _text(match: re.Match | None) -> str | None:
    return collapse(html_to_text(match.group(1))) if match else None


def parse_search_page(html: str) -> list[dict]:
    """The ten cards on one page of guest search results."""
    cards = []
    for block in _CARD.findall(html or ""):
        identifier = _CARD_ID.search(block)
        if not identifier:
            continue
        company_url = _CARD_COMPANY_URL.search(block)
        cards.append(
            {
                "jobId": identifier.group(1),
                "jobTitle": _text(_CARD_TITLE.search(block)),
                "companyName": _text(_CARD_COMPANY.search(block)),
                "companyUrl": clean_url(company_url.group(1)) if company_url else None,
                "location": _text(_CARD_LOCATION.search(block)),
                "postedDate": (
                    _CARD_DATE.search(block).group(1)
                    if _CARD_DATE.search(block)
                    else None
                ),
            }
        )
    return cards


def parse_detail(html: str, job_identifier: str) -> dict:
    """One posting's detail page: description, criteria, applicants, pay."""
    description_html = _DESCRIPTION.search(html)
    description = html_to_text(description_html.group(1)) if description_html else ""
    criteria = parse_job_criteria(html)

    applicants_text = _text(_APPLICANTS.search(html))
    applicants = None
    if applicants_text:
        digits = re.search(r"(\d[\d,]*)", applicants_text)
        applicants = int(digits.group(1).replace(",", "")) if digits else None

    # A structured pay range, when the employer provided one, is more reliable
    # than anything mined out of the prose -- so it wins when both exist.
    salary = extract_salary(description)
    structured = _text(_SALARY_BLOCK.search(html))
    if structured:
        from_block = extract_salary(structured)
        if from_block.get("salaryMin") is not None:
            salary = from_block
            salary["salarySource"] = "employer-provided"
    elif salary.get("salaryMin") is not None:
        salary["salarySource"] = "parsed-from-description"

    return {
        "jobId": job_identifier,
        "jobUrl": f"https://www.linkedin.com/jobs/view/{job_identifier}",
        "description": description or None,
        "descriptionLength": len(description),
        "techStack": extract_tech_stack(description),
        "certifications": extract_certifications(description),
        "workplaceType": extract_workplace(description),
        "applicants": applicants,
        "applicantsText": applicants_text,
        "postedAgo": _text(_POSTED_AGO.search(html)),
        **criteria,
        **salary,
    }


async def recruiter_via_voyager(
    client: LinkedInClient, job_identifier: str, log
) -> dict:
    """The poster behind a job, which the guest page never renders.

    Uses the decorated REST endpoint rather than GraphQL: it takes no rotating
    ``queryId``, so it survives LinkedIn's web releases better than a pinned
    query hash would.
    """
    payload = await client.voyager(
        f"jobs/jobPostings/{job_identifier}",
        "decorationId=com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65",
    )
    for container in walk(payload, "hiringTeam") + walk(payload, "poster"):
        entries = container if isinstance(container, list) else [container]
        for entry in entries:
            person = person_from_voyager(entry if isinstance(entry, dict) else {})
            if person and person.get("fullName"):
                return {
                    "recruiterName": person.get("fullName"),
                    "recruiterFirstName": person.get("firstName"),
                    "recruiterLastName": person.get("lastName"),
                    "recruiterHeadline": person.get("headline"),
                    "recruiterProfileUrl": person.get("profileUrl"),
                }
    apply_url = next(
        (
            first_text(node)
            for node in walk(payload, "companyApplyUrl")
            if first_text(node)
        ),
        None,
    )
    return {"applyUrl": apply_url} if apply_url else {}


async def resolve_domain(
    client: LinkedInClient, company_url: str, cache: dict[str, str | None], log
) -> str | None:
    """The employer's own web domain, read from their LinkedIn company page.

    Cached per company, because a 200-job run over 40 employers should cost 40
    extra requests, not 200. Returns the domain only -- no email address is
    invented from it, because a guessed address that bounces costs the sender
    their domain reputation.
    """
    if not company_url:
        return None
    if company_url in cache:
        return cache[company_url]
    try:
        page = await client.fetch(company_url)
        from src.parse import parse_organization

        organisation = parse_organization(page) or {}
        cache[company_url] = company_domain(organisation.get("website"))
    except LinkedInError as exc:
        log.warning(f"Could not resolve a domain for {company_url}: {exc}")
        cache[company_url] = None
    return cache[company_url]


def passes_client_filters(record: dict, wanted: dict) -> bool:
    """Apply the filters LinkedIn's guest endpoint accepts but ignores."""
    workplace = wanted.get("workplaceType")
    if workplace and record.get("workplaceType") != workplace:
        return False
    employment = wanted.get("employmentType")
    if employment and (record.get("employmentType") or "").lower() != employment.lower():
        return False
    seniority = wanted.get("seniorityLevel")
    if seniority and (record.get("seniorityLevel") or "").lower() != seniority.lower():
        return False
    required_tech = wanted.get("requiredTech") or []
    if required_tech:
        found = {t.lower() for t in record.get("techStack") or []}
        if not any(t.lower() in found for t in required_tech):
            return False
    if wanted.get("onlyWithSalary") and record.get("salaryMin") is None:
        return False
    return True


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        log = Actor.log

        queries = dedupe(string_list(actor_input.get("searchQueries")))
        direct_ids = dedupe(
            [
                found
                for raw in string_list(actor_input.get("jobUrls"))
                + string_list(actor_input.get("startUrls"))
                if (found := job_id(raw))
            ]
        )
        if not queries and not direct_ids:
            raise input_error(
                "Give at least one search query (searchQueries) or one job URL "
                "or id (jobUrls)."
            )

        location = collapse(actor_input.get("location") or "")
        date_posted = DATE_POSTED.get(actor_input.get("datePosted") or "")
        max_per_query = clamp(
            actor_input.get("maxJobsPerQuery"), 1, SEARCH_CEILING, 50
        )
        max_jobs = clamp(actor_input.get("maxJobs"), 1, 2000, 200)
        want_recruiter = bool(actor_input.get("includeRecruiter", False))
        emit_description = bool(actor_input.get("includeFullDescription", True))
        want_domain = bool(actor_input.get("resolveCompanyDomain", False))

        client_filters = {
            "workplaceType": actor_input.get("workplaceType") or None,
            "employmentType": actor_input.get("employmentType") or None,
            "seniorityLevel": actor_input.get("seniorityLevel") or None,
            "requiredTech": string_list(actor_input.get("requiredTech")),
            "onlyWithSalary": bool(actor_input.get("onlyWithSalary", False)),
        }

        cookie = (actor_input.get("sessionCookie") or "").strip()
        if cookie.lower().startswith("li_at="):
            cookie = cookie.split("=", 1)[1].strip().strip('"')
        if want_recruiter and not cookie:
            log.warning(
                "Recruiter details were requested but no li_at cookie was "
                "supplied. LinkedIn does not render the hiring team to "
                "logged-out visitors, so recruiter fields stay empty."
            )

        proxy = await proxy_url_from(
            Actor,
            actor_input,
            required_reason=(
                "You supplied a session cookie but no proxy. Running your own "
                "LinkedIn session through an Apify datacenter IP is what gets "
                "sessions flagged -- a RESIDENTIAL proxy is strongly advised."
                if cookie
                else None
            ),
        )
        client = LinkedInClient(
            log,
            li_at=cookie or None,
            proxy_url=proxy,
            min_delay=clamp_float(actor_input.get("minDelaySeconds"), 0.0, 60.0, 2.0),
            max_delay=clamp_float(actor_input.get("maxDelaySeconds"), 0.0, 120.0, 8.0),
        )

        # -- discovery ----------------------------------------------------
        discovered: dict[str, dict] = {}
        for identifier in direct_ids:
            discovered[identifier] = {"jobId": identifier, "_input": identifier}

        for query in queries:
            found_here = 0
            start = 0
            while found_here < max_per_query and start < SEARCH_CEILING:
                url = (
                    f"{SEARCH_API}?keywords={query.replace(' ', '%20')}"
                    f"&location={location.replace(' ', '%20')}&start={start}"
                )
                if date_posted:
                    url += f"&f_TPR={date_posted}"
                try:
                    page = await client.fetch(url)
                except LinkedInError as exc:
                    records_error = error_record(query, "search_failed", str(exc))
                    await Actor.push_data(records_error)
                    log.warning(f"Search '{query}' failed: {exc}")
                    break
                cards = parse_search_page(page)
                if not cards:
                    break
                for card in cards:
                    if card["jobId"] not in discovered:
                        discovered[card["jobId"]] = {**card, "_input": query}
                        found_here += 1
                    if found_here >= max_per_query:
                        break
                start += PAGE_SIZE
            log.info(f"Search '{query}': {found_here} new postings.")

        job_ids = list(discovered)[:max_jobs]
        log.info(f"{len(job_ids)} postings to read in detail.")

        # -- detail -------------------------------------------------------
        records: list[dict] = []
        domain_cache: dict[str, str | None] = {}
        kept = 0
        filtered_out = 0
        for identifier in job_ids:
            card = discovered[identifier]
            given_input = card.get("_input") or identifier
            try:
                detail_html = await client.fetch(f"{DETAIL_API}/{identifier}")
            except LinkedInError as exc:
                records.append(error_record(given_input, "detail_failed", str(exc)))
                continue
            detail = parse_detail(detail_html, identifier)

            record = {
                **envelope(SOURCE_DETAIL, given_input, "JOB"),
                "jobTitle": card.get("jobTitle") or detail.get("jobTitle"),
                "companyName": card.get("companyName"),
                "companyUrl": card.get("companyUrl"),
                "companySlug": company_slug(card.get("companyUrl")),
                "companyDomain": None,
                "location": card.get("location"),
                "postedDate": card.get("postedDate"),
                **detail,
            }
            if not emit_description:
                record.pop("description", None)

            if not passes_client_filters(record, client_filters):
                filtered_out += 1
                continue

            if want_domain and record.get("companyUrl"):
                record["companyDomain"] = await resolve_domain(
                    client, record["companyUrl"], domain_cache, log
                )

            if want_recruiter and cookie:
                try:
                    record.update(await recruiter_via_voyager(client, identifier, log))
                    record["_source"] = SOURCE_RECRUITER
                except LinkedInError as exc:
                    record["_recruiterError"] = str(exc)[:200]

            records.append(record)
            kept += 1

        if filtered_out:
            log.info(
                f"{filtered_out} posting(s) dropped by the client-side filters "
                "(LinkedIn's guest endpoint ignores these, so they are applied "
                "after each description is read)."
            )
        if not kept and job_ids:
            records.append(
                notice_record(
                    ", ".join(queries) or "job urls",
                    "all_filtered_out",
                    f"{len(job_ids)} postings were read but none matched the "
                    "workplace / employment / seniority / tech filters.",
                )
            )

        log.info(
            f"{kept} job(s) kept. HTTP: {client.stats['requests']} requests, "
            f"{client.stats['rateGateHits']} rate-gate retries."
        )

        await Actor.push_data(records)
        exporters.configure(
            preferred=COLUMNS,
            skip={"description"} if len(records) > 500 else set(),
            sheet="Jobs",
            stem="linkedin-jobs",
        )
        await exporters.write_exports(
            Actor, actor_input.get("exportFormats") or [], records
        )


if __name__ == "__main__":
    asyncio.run(main())
