"""LinkedIn Company Employee Role Filter -- Apify actor entry point.

Find the decision makers inside a target account: scrape a company's people and
keep only the ones whose headline or title matches what you are looking for --
"CMO", "Marketing Director", "Head of HR".

**This actor needs your own ``li_at`` session cookie for the employee list.**
That is not a design choice. LinkedIn bounces ``/company/{slug}/people/`` to the
login wall for anonymous visitors and answers ``/voyager/api/*`` with HTTP 403,
so there is no logged-out surface carrying employees at all -- verified
2026-09-20.

Without a cookie the run still succeeds and still returns something useful: the
company's own public record (name, follower count, headcount band, website,
domain and LinkedIn's internal company id) plus a NOTICE row stating plainly why
no employees came back. An empty dataset with no explanation would be worse.
"""

from __future__ import annotations

import asyncio
import re

from apify import Actor

from src import exporters
from src.linkedin import AuthRequired, LinkedInClient, LinkedInError, proxy_url_from
from src.parse import parse_organization
from src.runtime import (
    clamp,
    clamp_float,
    company_domain,
    company_url,
    dedupe,
    envelope,
    error_record,
    notice_record,
    string_list,
)
from src.voyager import QueryIdResolver, person_from_voyager, walk
from src.input_errors import input_error

SOURCE_COMPANY = "guest-company-page"
SOURCE_SEARCH = "voyager-search-clusters"

COLUMNS = [
    "fullName", "firstName", "lastName", "headline", "matchedKeyword",
    "profileUrl", "location", "companyName", "companyUrl", "companyDomain",
    "followers", "employeeCount", "recordType",
]

PAGE_SIZE = 10


def matches(person: dict, include: list[str], exclude: list[str]) -> str | None:
    """Return the keyword that matched this person, or None.

    Matching is on whole words against the headline, so a search for "HR" does
    not drag in every "CHRIS" and "THREAD". Multi-word keywords like "Marketing
    Director" are matched as a phrase.
    """
    haystack = " ".join(
        str(person.get(field) or "")
        for field in ("headline", "fullName", "location")
    ).lower()
    if not haystack.strip():
        return None
    for term in exclude:
        if re.search(rf"(?<![\w]){re.escape(term.lower())}(?![\w])", haystack):
            return None
    if not include:
        return "*"
    for term in include:
        if re.search(rf"(?<![\w]){re.escape(term.lower())}(?![\w])", haystack):
            return term
    return None


async def read_company(client: LinkedInClient, url: str) -> dict:
    """The company's own public record, including LinkedIn's internal id.

    The numeric id is never rendered on the page, but it leaks in the "see all
    employees" call to action -- and it is the key the people search facets on.
    """
    page = await client.fetch(url)
    organisation = parse_organization(page)
    if not organisation:
        raise LinkedInError("No company data on the page.")
    organisation["companyDomain"] = company_domain(organisation.get("website"))
    return organisation


async def employees_via_voyager(
    client: LinkedInClient,
    resolver: QueryIdResolver,
    company_id: str,
    keywords: list[str],
    wanted: int,
    log,
) -> list[dict]:
    """People search faceted to one company.

    LinkedIn's own keyword box is used when a single keyword was given -- it
    narrows server-side, so fewer pages are fetched. With several keywords the
    search runs unfiltered and matching happens locally, because LinkedIn treats
    multiple terms as AND and would return almost nothing.
    """
    query_id = await resolver.get("searchClusters", "voyagerSearchDashClusters")
    server_keyword = keywords[0] if len(keywords) == 1 else ""
    collected: list[dict] = []
    start = 0
    while len(collected) < wanted and start < 1000:
        variables = (
            f"(start:{start},origin:FACETED_SEARCH,"
            f"query:(keywords:{server_keyword},flagshipSearchIntent:SEARCH_SRP,"
            f"queryParameters:List("
            f"(key:currentCompany,value:List({company_id})),"
            f"(key:resultType,value:List(PEOPLE))),"
            f"includeFiltersInResponse:false))"
        )
        payload = await client.graphql(query_id, variables)
        batch: list[dict] = []
        for group in walk(payload, "elements"):
            if not isinstance(group, list):
                continue
            for element in group:
                if not isinstance(element, dict):
                    continue
                person = person_from_voyager(element)
                if person and person.get("profileUrl"):
                    batch.append(person)
        if not batch:
            break
        collected.extend(batch)
        start += PAGE_SIZE
        if len(batch) < PAGE_SIZE:
            break
    # The same member can appear in more than one result cluster.
    seen: set[str] = set()
    unique = []
    for person in collected:
        key = (person.get("profileUrl") or "").lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(person)
    return unique


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        log = Actor.log

        companies = dedupe(
            [
                normalised
                for raw in string_list(actor_input.get("companyUrls"))
                + string_list(actor_input.get("startUrls"))
                if (normalised := company_url(raw))
            ]
        )
        if not companies:
            raise input_error(
                "No usable company pages. Give a /company/ URL or a bare slug "
                "in companyUrls."
            )

        include = [k.strip() for k in string_list(actor_input.get("roleKeywords")) if k.strip()]
        exclude = [k.strip() for k in string_list(actor_input.get("excludeKeywords")) if k.strip()]
        max_per_company = clamp(actor_input.get("maxEmployeesPerCompany"), 1, 1000, 100)
        max_total = clamp(actor_input.get("maxEmployees"), 1, 5000, 500)

        cookie = (actor_input.get("sessionCookie") or "").strip()
        if cookie.lower().startswith("li_at="):
            cookie = cookie.split("=", 1)[1].strip().strip('"')

        proxy = await proxy_url_from(
            Actor,
            actor_input,
            required_reason=(
                "You supplied a session cookie but no proxy. LinkedIn weighs the "
                "exit IP against where your account normally signs in, and an "
                "Apify datacenter IP is exactly the mismatch that gets a session "
                "flagged. Enable a RESIDENTIAL proxy in your own country."
                if cookie
                else None
            ),
        )
        client = LinkedInClient(
            log,
            li_at=cookie or None,
            proxy_url=proxy,
            min_delay=clamp_float(actor_input.get("minDelaySeconds"), 0.0, 60.0, 3.0),
            max_delay=clamp_float(actor_input.get("maxDelaySeconds"), 0.0, 120.0, 8.0),
        )
        resolver = QueryIdResolver(client, log)

        if not cookie:
            log.warning(
                "No li_at cookie supplied. LinkedIn's employee directory has no "
                "logged-out surface -- /company/{slug}/people/ redirects to the "
                "login wall and /voyager/api/* answers 403 -- so this run "
                "returns each company's public record and nothing else."
            )

        records: list[dict] = []
        emitted = 0

        for url in companies:
            try:
                organisation = await read_company(client, url)
            except LinkedInError as exc:
                code = (
                    "auth_required" if isinstance(exc, AuthRequired) else "fetch_failed"
                )
                records.append(error_record(url, code, str(exc)))
                log.warning(f"{url}: {exc}")
                continue

            records.append(
                {**envelope(SOURCE_COMPANY, url, "COMPANY"), **organisation}
            )
            log.info(
                f"{organisation.get('companyName')}: "
                f"{organisation.get('followers')} followers, "
                f"company id {organisation.get('companyId')}."
            )

            if not cookie:
                records.append(
                    notice_record(
                        url,
                        "cookie_required_for_employees",
                        "LinkedIn publishes no employee list to logged-out "
                        "visitors. Paste your own li_at session cookie into "
                        "sessionCookie to read the people at this company.",
                    )
                )
                continue

            if not organisation.get("companyId"):
                records.append(
                    notice_record(
                        url,
                        "company_id_not_found",
                        "LinkedIn's internal company id was not on the page, so "
                        "the people search cannot be faceted to this company. "
                        "This happens on some showcase and redirected pages.",
                    )
                )
                continue

            try:
                people = await employees_via_voyager(
                    client,
                    resolver,
                    organisation["companyId"],
                    include,
                    max_per_company,
                    log,
                )
            except LinkedInError as exc:
                records.append(error_record(url, "employee_search_failed", str(exc)))
                log.warning(f"{url}: employee search failed -- {exc}")
                continue

            matched = 0
            for person in people:
                if emitted >= max_total:
                    break
                keyword = matches(person, include, exclude)
                if not keyword:
                    continue
                records.append(
                    {
                        **envelope(SOURCE_SEARCH, url, "EMPLOYEE"),
                        **person,
                        "matchedKeyword": None if keyword == "*" else keyword,
                        "companyName": organisation.get("companyName"),
                        "companyUrl": organisation.get("companyUrl"),
                        "companyDomain": organisation.get("companyDomain"),
                    }
                )
                matched += 1
                emitted += 1

            log.info(
                f"{organisation.get('companyName')}: {matched} of "
                f"{len(people)} people matched the role filter."
            )
            if people and not matched:
                records.append(
                    notice_record(
                        url,
                        "no_role_matches",
                        f"{len(people)} people were read but none matched "
                        f"{include or 'the filter'}. Keywords are matched as "
                        "whole words against the headline - try a broader term.",
                    )
                )

        log.info(
            f"{emitted} employee(s) across {len(companies)} company page(s). "
            f"HTTP: {client.stats['requests']} requests, "
            f"{client.stats['rateGateHits']} rate-gate retries."
        )

        await Actor.push_data(records)
        exporters.configure(
            preferred=COLUMNS, sheet="Employees", stem="company-employees"
        )
        await exporters.write_exports(
            Actor, actor_input.get("exportFormats") or [], records
        )


if __name__ == "__main__":
    asyncio.run(main())
