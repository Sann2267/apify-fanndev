"""LinkedIn University Alumni Career Mapper -- Apify actor entry point.

Where did a university's graduates end up? This actor reads a school's alumni
and maps them: employer, role, location and graduation year, aggregated into the
talent-mobility picture a tracer study is trying to produce.

**A ``li_at`` session cookie is required, and this one is stricter than the
others in this portfolio.** LinkedIn blocks ``/school/`` pages outright for
logged-out visitors -- HTTP 999 on every path tried, including the ``/company/``
alias that redirects there, and it does not clear with delays the way the normal
rate gate does. Verified 2026-09-20 across repeated attempts with pauses. So
unlike the company and profile surfaces, there is not even a public school
record to fall back on: without a cookie this actor has nothing to read.

When no cookie is supplied the run still succeeds and writes a NOTICE row per
school saying exactly that, rather than failing or returning a silent empty
dataset.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter

from apify import Actor

from src import exporters
from src.linkedin import AuthRequired, LinkedInClient, LinkedInError, proxy_url_from
from src.parse import clean_url, collapse, company_slug
from src.runtime import (
    clamp,
    clamp_float,
    company_url,
    dedupe,
    envelope,
    error_record,
    notice_record,
    string_list,
)
from src.voyager import (
    QueryIdResolver,
    first_text,
    person_from_voyager,
    require_cookie,
    walk,
)
from src.input_errors import input_error

SOURCE_SCHOOL = "voyager-school"
SOURCE_ALUMNI = "voyager-search-clusters"

COLUMNS = [
    "fullName", "firstName", "lastName", "headline", "currentCompany",
    "currentTitle", "location", "graduationYear", "profileUrl", "schoolName",
    "schoolUrl", "recordType",
]

PAGE_SIZE = 10

# "Class of 2018", "Angkatan 2018", or a bare year in the headline.
_YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")

# A headline is usually "Title at Company"; splitting on the connector is the
# only way to separate them, and it has to cover the common localisations.
_AT = re.compile(r"\s+(?:at|@|di|chez|bei|en|presso|na)\s+", re.I)


def split_headline(headline: str | None) -> tuple[str | None, str | None]:
    """Split "Senior Engineer at Acme" into role and employer."""
    if not headline:
        return None, None
    parts = _AT.split(headline, maxsplit=1)
    if len(parts) == 2:
        return collapse(parts[0]) or None, collapse(parts[1]) or None
    return collapse(headline) or None, None


def graduation_year(person: dict) -> int | None:
    """Best-effort graduation year from whatever text LinkedIn attached."""
    haystack = " ".join(
        str(person.get(field) or "")
        for field in ("subtitle", "headline", "location", "summary")
    )
    years = [int(y) for y in _YEAR.findall(haystack)]
    return min(years) if years else None


async def read_school(client: LinkedInClient, url: str) -> dict:
    """The school's own record and the internal id the alumni search facets on."""
    slug = company_slug(url)
    payload = await client.voyager(
        f"organization/companies?q=universalName&universalName={slug}"
    )
    identifiers = [n for n in walk(payload, "entityUrn") if isinstance(n, str)]
    numeric = None
    for urn in identifiers:
        match = re.search(r":(\d{3,})$", urn)
        if match:
            numeric = match.group(1)
            break
    name = next((first_text(n) for n in walk(payload, "name") if first_text(n)), None)
    return {
        "schoolName": collapse(name) or slug,
        "schoolUrl": clean_url(url),
        "schoolSlug": slug,
        "schoolId": numeric,
    }


async def alumni_via_voyager(
    client: LinkedInClient,
    resolver: QueryIdResolver,
    school_id: str,
    keywords: str,
    wanted: int,
    log,
) -> list[dict]:
    """People search faceted to one school."""
    query_id = await resolver.get("searchClusters", "voyagerSearchDashClusters")
    collected: list[dict] = []
    start = 0
    while len(collected) < wanted and start < 1000:
        variables = (
            f"(start:{start},origin:FACETED_SEARCH,"
            f"query:(keywords:{keywords},flagshipSearchIntent:SEARCH_SRP,"
            f"queryParameters:List("
            f"(key:schoolFilter,value:List({school_id})),"
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

    seen: set[str] = set()
    unique = []
    for person in collected:
        key = (person.get("profileUrl") or "").lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(person)
    return unique[:wanted]


def summarise(school: dict, alumni: list[dict]) -> dict:
    """The aggregate a tracer study actually wants out of the individual rows."""
    employers = Counter(a["currentCompany"] for a in alumni if a.get("currentCompany"))
    locations = Counter(a["location"] for a in alumni if a.get("location"))
    roles = Counter(a["currentTitle"] for a in alumni if a.get("currentTitle"))
    years = [a["graduationYear"] for a in alumni if a.get("graduationYear")]
    return {
        **envelope(SOURCE_ALUMNI, school.get("schoolUrl") or "", "SUMMARY"),
        **school,
        "alumniAnalysed": len(alumni),
        "topEmployers": [
            {"employer": name, "alumni": count}
            for name, count in employers.most_common(25)
        ],
        "topLocations": [
            {"location": name, "alumni": count}
            for name, count in locations.most_common(25)
        ],
        "topRoles": [
            {"role": name, "alumni": count} for name, count in roles.most_common(25)
        ],
        "distinctEmployers": len(employers),
        "graduationYearRange": [min(years), max(years)] if years else None,
        "withEmployerPct": round(
            sum(1 for a in alumni if a.get("currentCompany")) / len(alumni) * 100, 1
        )
        if alumni
        else None,
    }


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        log = Actor.log

        schools = dedupe(
            [
                normalised
                for raw in string_list(actor_input.get("schoolUrls"))
                + string_list(actor_input.get("startUrls"))
                if (normalised := company_url(raw))
            ]
        )
        if not schools:
            raise input_error(
                "No usable school pages. Give a linkedin.com/school/... URL or "
                "a bare school slug in schoolUrls."
            )
        # A bare slug defaults to /company/; for this actor it means /school/.
        schools = [
            url.replace("/company/", "/school/") if "/company/" in url else url
            for url in schools
        ]

        keywords = collapse(actor_input.get("filterKeywords") or "")
        max_per_school = clamp(actor_input.get("maxAlumniPerSchool"), 1, 1000, 200)
        max_total = clamp(actor_input.get("maxAlumni"), 1, 10000, 1000)
        emit_summary = bool(actor_input.get("emitSummary", True))

        records: list[dict] = []

        try:
            cookie = require_cookie(actor_input, "The LinkedIn school and alumni surface")
        except AuthRequired as exc:
            detail = (
                f"{exc} LinkedIn is stricter here than elsewhere: /school/ pages "
                "answer HTTP 999 to logged-out visitors on every path, including "
                "the /company/ alias, and unlike the ordinary rate gate it does "
                "not clear with delays. There is no public school record to fall "
                "back on."
            )
            log.warning(detail)
            for url in schools:
                records.append(notice_record(url, "cookie_required", detail))
            await Actor.push_data(records)
            exporters.configure(preferred=COLUMNS, sheet="Alumni", stem="alumni")
            await exporters.write_exports(
                Actor, actor_input.get("exportFormats") or [], records
            )
            return

        proxy = await proxy_url_from(
            Actor,
            actor_input,
            required_reason=(
                "You supplied a session cookie but no proxy. LinkedIn weighs the "
                "exit IP against where your account normally signs in, and an "
                "Apify datacenter IP is exactly the mismatch that gets a session "
                "flagged. Enable a RESIDENTIAL proxy in your own country."
            ),
        )
        client = LinkedInClient(
            log,
            li_at=cookie,
            proxy_url=proxy,
            min_delay=clamp_float(actor_input.get("minDelaySeconds"), 0.0, 60.0, 3.0),
            max_delay=clamp_float(actor_input.get("maxDelaySeconds"), 0.0, 120.0, 8.0),
        )
        resolver = QueryIdResolver(client, log)

        emitted = 0
        for url in schools:
            try:
                school = await read_school(client, url)
            except LinkedInError as exc:
                code = (
                    "auth_required" if isinstance(exc, AuthRequired) else "fetch_failed"
                )
                records.append(error_record(url, code, str(exc)))
                log.warning(f"{url}: {exc}")
                continue

            if not school.get("schoolId"):
                records.append(
                    notice_record(
                        url,
                        "school_id_not_found",
                        "LinkedIn returned the school but no internal id, so the "
                        "alumni search cannot be faceted to it. Check that the "
                        "slug is a /school/ page and not a /company/ one.",
                    )
                )
                continue

            try:
                people = await alumni_via_voyager(
                    client, resolver, school["schoolId"], keywords, max_per_school, log
                )
            except LinkedInError as exc:
                records.append(error_record(url, "alumni_search_failed", str(exc)))
                log.warning(f"{url}: alumni search failed -- {exc}")
                continue

            enriched = []
            for person in people:
                role, employer = split_headline(person.get("headline"))
                person["currentTitle"] = role
                person["currentCompany"] = employer
                person["graduationYear"] = graduation_year(person)
                enriched.append(person)

            for person in enriched:
                if emitted >= max_total:
                    break
                records.append(
                    {
                        **envelope(SOURCE_ALUMNI, url, "ALUMNUS"),
                        **person,
                        "schoolName": school.get("schoolName"),
                        "schoolUrl": school.get("schoolUrl"),
                    }
                )
                emitted += 1

            if emit_summary and enriched:
                records.append(summarise(school, enriched))

            log.info(
                f"{school.get('schoolName')}: {len(enriched)} alumni read, "
                f"{len({a.get('currentCompany') for a in enriched if a.get('currentCompany')})} "
                "distinct employers."
            )

            if not enriched:
                records.append(
                    notice_record(
                        url,
                        "no_alumni_returned",
                        "LinkedIn resolved the school but returned no alumni. "
                        "Alumni search results depend on what your account is "
                        "allowed to see; a narrower filterKeywords or an account "
                        "with more network reach usually returns more.",
                    )
                )

        log.info(
            f"{emitted} alumni across {len(schools)} school(s). "
            f"HTTP: {client.stats['requests']} requests, "
            f"{client.stats['rateGateHits']} rate-gate retries."
        )

        await Actor.push_data(records)
        exporters.configure(preferred=COLUMNS, sheet="Alumni", stem="alumni")
        await exporters.write_exports(
            Actor, actor_input.get("exportFormats") or [], records
        )


if __name__ == "__main__":
    asyncio.run(main())
