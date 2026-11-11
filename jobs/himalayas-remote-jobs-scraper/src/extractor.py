"""Normalisation, local filtering and company aggregation.

The upstream job shape is already clean JSON, so it is passed through verbatim
(`.ai/CLAUDE.md` rule 5 -- raw passthrough). Fields are only ever *added*
alongside the originals, never renamed or replaced:

* ``pubDateIso``/``expiryDateIso`` -- ISO 8601 next to the raw epoch seconds.
* ``salaryText`` -- one readable string instead of five salary fields.
* ``annualizedSalaryMin``/``Max``/``annualizedFrom`` -- yearly equivalents, so
  an hourly rate and an annual salary can be compared at all.
* ``jobUrl``/``companyUrl`` -- the public pages, built from the slugs.
* ``descriptionText`` -- the HTML description as plain text.

The filtering lives here because the upstream API ignores every filter
parameter it accepts (see constants.py), so it has to be done over records
already fetched or not at all.
"""

import re
from datetime import datetime, timezone

from src.constants import FILTER_FIELDS

HTML_TAG = re.compile(r"<[^>]+>")


def _iso(value) -> str | None:
    """Himalayas publishes epoch seconds; emit ISO 8601 next to them."""
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError):
        return None


# The feed mixes pay periods in the same numeric fields: of 400 jobs sampled,
# 352 were annual, 34 hourly, 11 monthly and 3 weekly. A caller filtering on
# "minSalary >= 150000" against a raw value of 55 would silently discard a
# $55/hour role worth about $114k a year, so periods are normalised to a year
# before any comparison. These multipliers are arithmetic, not estimates:
# 40h x 52w for hourly, 52 weeks, 12 months.
PERIOD_TO_ANNUAL = {
    "annual": 1,
    "yearly": 1,
    "monthly": 12,
    "weekly": 52,
    "daily": 260,
    "hourly": 2080,
}


def _annualize(value, period: str | None) -> float | None:
    """Scale a pay figure to a yearly equivalent, within its own currency.

    Currency is deliberately **not** converted: the feed carries USD, INR, EUR,
    CAD, PLN and PHP, and inventing exchange rates would put made-up numbers in
    a dataset. Callers who need comparability filter by ``currency``.
    """
    if value is None:
        return None
    multiplier = PERIOD_TO_ANNUAL.get((period or "annual").lower())
    if multiplier is None:
        return None
    try:
        return float(value) * multiplier
    except (TypeError, ValueError):
        return None


def _salary_text(job: dict) -> str | None:
    low, high = job.get("minSalary"), job.get("maxSalary")
    if low is None and high is None:
        return None
    currency = job.get("currency") or ""
    period = job.get("salaryPeriod") or ""
    if low is not None and high is not None and low != high:
        amount = f"{int(low):,} - {int(high):,}"
    else:
        amount = f"{int(low if low is not None else high):,}"
    return " ".join(part for part in (currency, amount, period) if part).strip()


def normalize_job(job: dict) -> dict:
    """Upstream job, passed through, plus the derived conveniences."""
    record = dict(job)
    # The feed's "guid" is itself the listing URL, not a bare id -- prefixing a
    # path onto it produced "himalayas.app/jobs/https://himalayas.app/..." until
    # this was caught.
    guid = job.get("guid") or ""
    if guid.startswith("http"):
        record["jobUrl"] = guid
    elif guid:
        record["jobUrl"] = f"https://himalayas.app/jobs/{guid}"
    else:
        record["jobUrl"] = None
    record["companyUrl"] = (
        f"https://himalayas.app/companies/{job['companySlug']}" if job.get("companySlug") else None
    )
    record["pubDateIso"] = _iso(job.get("pubDate"))
    record["expiryDateIso"] = _iso(job.get("expiryDate"))
    record["salaryText"] = _salary_text(job)
    period = job.get("salaryPeriod")
    record["annualizedSalaryMin"] = _annualize(job.get("minSalary"), period)
    record["annualizedSalaryMax"] = _annualize(job.get("maxSalary"), period)
    record["annualizedFrom"] = period if record["annualizedSalaryMin"] is not None or record["annualizedSalaryMax"] is not None else None
    record["descriptionText"] = (
        HTML_TAG.sub(" ", job["description"]).replace("&nbsp;", " ").strip()
        if job.get("description")
        else None
    )
    record["_source"] = "himalayas-jobs-api"
    return record


def matches(job: dict, filters: dict) -> bool:
    """Does this job satisfy every supplied filter?

    Filters are ANDed across fields and ORed within a field's list of accepted
    values, which is what someone means by "engineering or design roles, senior
    only".
    """
    for key, (field, kind) in FILTER_FIELDS.items():
        wanted = filters.get(key)
        if not wanted:
            continue
        value = job.get(field)

        if kind == "text":
            haystack = str(value or "").lower()
            if not any(str(w).lower() in haystack for w in _as_list(wanted)):
                return False
        elif kind == "list":
            have = [str(v).lower() for v in (value or [])]
            if not any(str(w).lower() in have for w in _as_list(wanted)):
                return False

    currencies = filters.get("currency")
    if currencies:
        have = str(job.get("currency") or "").upper()
        if have not in {str(c).upper() for c in _as_list(currencies)}:
            return False

    # Salary comparisons use the annualised figures, never the raw ones, so an
    # hourly rate is not judged against a yearly threshold.
    low = filters.get("minSalary")
    if low is not None:
        # A job with no published salary cannot be shown to clear a salary
        # floor, so it is excluded rather than assumed to qualify.
        top = job.get("annualizedSalaryMax") or job.get("annualizedSalaryMin")
        if top is None or top < low:
            return False

    high = filters.get("maxSalary")
    if high is not None:
        bottom = job.get("annualizedSalaryMin") or job.get("annualizedSalaryMax")
        if bottom is None or bottom > high:
            return False

    if filters.get("salariedOnly") and job.get("minSalary") is None and job.get("maxSalary") is None:
        return False

    return True


def _as_list(value) -> list:
    return value if isinstance(value, (list, tuple)) else [value]


def aggregate_companies(jobs: list[dict]) -> list[dict]:
    """Collapse jobs into one record per company -- a hiring-volume view.

    Built from the same fetched pages, so it costs no extra requests. Counting
    is done over whatever slice was fetched, and ``jobsSeen`` says so plainly
    rather than implying it is the company's total headcount of openings.
    """
    by_company: dict[str, dict] = {}

    for job in jobs:
        slug = job.get("companySlug") or job.get("companyName")
        if not slug:
            continue
        entry = by_company.setdefault(
            slug,
            {
                "companySlug": job.get("companySlug"),
                "companyName": job.get("companyName"),
                "companyLogo": job.get("companyLogo"),
                "companyUrl": job.get("companyUrl"),
                "jobsSeen": 0,
                "jobTitles": [],
                "categories": set(),
                "seniority": set(),
                "locationRestrictions": set(),
                "salaries": [],
                "newestPubDateIso": None,
                "_source": "himalayas-jobs-api",
            },
        )
        entry["jobsSeen"] += 1
        if job.get("title"):
            entry["jobTitles"].append(job["title"])
        entry["categories"].update(job.get("parentCategories") or [])
        entry["seniority"].update(job.get("seniority") or [])
        entry["locationRestrictions"].update(job.get("locationRestrictions") or [])
        for bound in (job.get("annualizedSalaryMin"), job.get("annualizedSalaryMax")):
            if bound is not None:
                entry["salaries"].append(bound)
        pub = job.get("pubDateIso")
        if pub and (entry["newestPubDateIso"] is None or pub > entry["newestPubDateIso"]):
            entry["newestPubDateIso"] = pub

    out = []
    for entry in by_company.values():
        salaries = entry.pop("salaries")
        entry["categories"] = sorted(entry["categories"])
        entry["seniority"] = sorted(entry["seniority"])
        entry["locationRestrictions"] = sorted(entry["locationRestrictions"])
        # Named "annualized" because the members are yearly equivalents, and
        # mixed-currency unless the run filtered by currency.
        entry["lowestAnnualizedSalarySeen"] = min(salaries) if salaries else None
        entry["highestAnnualizedSalarySeen"] = max(salaries) if salaries else None
        out.append(entry)

    return sorted(out, key=lambda e: e["jobsSeen"], reverse=True)


def extract_error(identifier: str, reason: str, detail: str) -> dict:
    return {
        "guid": identifier,
        "error": reason,
        "errorDetail": detail,
        "_source": "error",
    }


def wrap_reference(url: str, available: bool, note: str, sample: dict | None = None) -> dict:
    return {
        "probedUrl": url,
        "isAvailable": available,
        "note": note,
        "sample": sample or {},
        "_source": "reference",
    }
