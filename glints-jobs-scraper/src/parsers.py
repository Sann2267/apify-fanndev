"""Shaping Glints payloads into dataset records.

The raw-passthrough rule applies: upstream field names survive verbatim and
unknown fields flow through untouched. Everything this module adds is either an
envelope field (underscore-prefixed) or a derived convenience that sits beside
the raw value rather than replacing it -- descriptionText next to
descriptionJsonString, jobUrl next to id.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .constants import COUNTRY_PATH, DEFAULT_COUNTRY

UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(
    input_value: str,
    source: str,
    record_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }
    if payload:
        rec.update(payload)
    return rec


def error_record(
    input_value: str, error: str, detail: str = "", record_type: str = "ERROR"
) -> dict[str, Any]:
    rec = envelope(input_value, "none", record_type)
    rec["_error"] = error
    if detail:
        rec["_errorDetail"] = detail[:1000]
    return rec


# -- identifiers -----------------------------------------------------------


def extract_uuid(value: str) -> str | None:
    """Pull a Glints entity id out of a bare id or any public URL.

    Handles every public shape seen in the sitemaps:
      /id/opportunities/jobs/<slug>/<uuid>
      /id/en/opportunities/jobs/<slug>/<uuid>
      /id/opportunities/s/<slug>/<uuid>          (sourced postings)
      /id/companies/<slug>/<uuid>
      /id/company/<slug>/<uuid>
    """
    if not value:
        return None
    matches = UUID_RE.findall(value.strip())
    # The last UUID wins: company URLs under a job path would otherwise
    # resolve to the wrong entity.
    return matches[-1].lower() if matches else None


def country_from_url(url: str, fallback: str = DEFAULT_COUNTRY) -> str:
    """Read the market prefix off a Glints URL (/id/..., /sg/..., /vn/...)."""
    m = re.search(r"glints\.com/([a-z]{2})(?:/|$)", url or "", re.I)
    if m:
        code = m.group(1).upper()
        if code in COUNTRY_PATH:
            return code
    return fallback


def job_url(job: dict[str, Any], country: str = DEFAULT_COUNTRY) -> str | None:
    job_id = job.get("id")
    if not job_id:
        return None
    country_code = ((job.get("country") or {}).get("code") or country or "").upper()
    path = COUNTRY_PATH.get(country_code, COUNTRY_PATH[DEFAULT_COUNTRY])
    slug = slugify(job.get("title") or "job")
    # Sourced postings live under /opportunities/s/ rather than /jobs/.
    segment = "s" if (job.get("jobSource") or "").upper() == "SOURCED" else "jobs"
    return f"https://glints.com/{path}/opportunities/{segment}/{slug}/{job_id}"


def company_url(company: dict[str, Any], country: str = DEFAULT_COUNTRY) -> str | None:
    company_id = company.get("id")
    if not company_id:
        return None
    path = COUNTRY_PATH.get((country or "").upper(), COUNTRY_PATH[DEFAULT_COUNTRY])
    slug = slugify(company.get("name") or "company")
    return f"https://glints.com/{path}/companies/{slug}/{company_id}"


def slugify(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return out[:80] or "item"


def logo_url(logo: str | None) -> str | None:
    """Turn the bare storage key Glints returns into a fetchable image URL."""
    if not logo:
        return None
    if logo.startswith("http"):
        return logo
    return f"https://images.glints.com/unsafe/glints-dashboard/{logo}"


# -- Draft.js --------------------------------------------------------------


def draftjs_to_text(raw: str | None) -> str | None:
    """Flatten a Draft.js document into newline-separated plain text.

    Glints stores job descriptions, company descriptions, culture blurbs and
    interview processes as Draft.js JSON. Anything that does not parse as a
    Draft.js document is returned as-is rather than dropped, so a format change
    degrades to raw text instead of a silent empty field.
    """
    if not raw:
        return None
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        return raw if isinstance(raw, str) else None
    if not isinstance(doc, dict):
        return raw
    blocks = doc.get("blocks")
    if not isinstance(blocks, list):
        return raw

    lines: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = (block.get("text") or "").strip()
        btype = block.get("type") or "unstyled"
        depth = block.get("depth") or 0
        if not text:
            lines.append("")
            continue
        if btype in ("unordered-list-item", "ordered-list-item"):
            text = f"{'  ' * depth}- {text}"
        lines.append(text)

    # Collapse runs of blank lines that Draft.js uses for spacing.
    cleaned: list[str] = []
    for line in lines:
        if not line and cleaned and not cleaned[-1]:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip() or None


def json_field(raw: str | None) -> Any:
    """Decode one of Glints' embedded JSON-string columns, or return None."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


# -- record builders -------------------------------------------------------


def salary_summary(salaries: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Collapse the salary array into flat min/max/currency for spreadsheets.

    Glints attaches several salary rows per job (BASIC, ALLOWANCE, ...). The
    BASIC row is the headline figure; if it is absent the widest row wins.
    Returns empty values rather than guessing when the job hides its salary.
    """
    rows = [s for s in (salaries or []) if isinstance(s, dict)]
    if not rows:
        return {"salaryMin": None, "salaryMax": None, "salaryCurrency": None, "salaryMode": None}
    basic = [s for s in rows if (s.get("salaryType") or "").upper() == "BASIC"]
    row = basic[0] if basic else rows[0]
    return {
        "salaryMin": row.get("minAmount"),
        "salaryMax": row.get("maxAmount"),
        "salaryCurrency": row.get("CurrencyCode"),
        "salaryMode": row.get("salaryMode"),
    }


def flatten_job(job: dict[str, Any], country: str = DEFAULT_COUNTRY) -> dict[str, Any]:
    """Add derived convenience fields to a job without disturbing the raw shape."""
    out = dict(job)
    company = job.get("company") or {}
    location = job.get("location") or {}
    category = job.get("hierarchicalJobCategory") or {}
    category_parents = category.get("parents") or []

    out["jobUrl"] = job_url(job, country)
    out["companyName"] = company.get("brandName") or company.get("name")
    out["companyUrl"] = company_url(company, (job.get("country") or {}).get("code") or country)
    out["companyLogoUrl"] = logo_url(company.get("logo"))
    out["companyIsVerified"] = (company.get("status") or "").upper() == "VERIFIED"
    out["locationName"] = location.get("formattedName") or location.get("name")
    out["countryCode"] = (job.get("country") or {}).get("code")
    out["categoryName"] = category.get("name")
    out["categoryPath"] = " > ".join(
        [p.get("name") for p in category_parents if p.get("name")]
        + ([category.get("name")] if category.get("name") else [])
    ) or None
    out["skillNames"] = [
        (s.get("skill") or {}).get("name")
        for s in (job.get("skills") or [])
        if (s.get("skill") or {}).get("name")
    ]
    out.update(salary_summary(job.get("salaries")))

    if "descriptionJsonString" in job:
        out["descriptionText"] = draftjs_to_text(job.get("descriptionJsonString"))
    if "interviewProcessJsonString" in job:
        out["interviewProcessText"] = draftjs_to_text(job.get("interviewProcessJsonString"))
    if "benefits" in job:
        out["benefitTitles"] = [
            b.get("title") for b in (job.get("benefits") or []) if b.get("title")
        ]
    return out


def flatten_company(company: dict[str, Any], country: str = DEFAULT_COUNTRY) -> dict[str, Any]:
    out = dict(company)
    out["companyUrl"] = company_url(company, country)
    out["companyLogoUrl"] = logo_url(company.get("logo"))
    out["isVerified"] = (company.get("status") or "").upper() == "VERIFIED"
    out["descriptionText"] = draftjs_to_text(company.get("descriptionJsonString"))
    out["cultureText"] = draftjs_to_text(company.get("cultureJsonString"))
    out["socialMediaSites"] = json_field(company.get("socialMediaSitesJsonString"))
    out["photos"] = json_field(company.get("photosJsonString"))
    location = company.get("hierarchicalLocation") or {}
    out["locationName"] = location.get("formattedName") or location.get("name")
    return out
