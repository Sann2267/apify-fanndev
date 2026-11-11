"""Input coercion and the dataset envelope shared by the LinkedIn actors."""

from __future__ import annotations

import re
from typing import Any

from src.parse import clean_url, utc_now


def string_list(value: Any) -> list[str]:
    """Accept a list, a newline/comma-separated string, or requestListSources."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(",", "\n").splitlines()]
        return [p for p in parts if p]
    if isinstance(value, dict):
        value = [value]
    out: list[str] = []
    for item in value or []:
        if isinstance(item, dict):
            item = item.get("url") or item.get("value") or item.get("uri")
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def dedupe(values: list[str]) -> list[str]:
    """Order-preserving de-duplication, case-insensitive (LinkedIn slugs are)."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def clamp_float(value: Any, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


# -- input normalisation --------------------------------------------------


def _with_scheme(value: str) -> str:
    """Trim, and give a scheme-less LinkedIn link (``www.linkedin.com/in/x``,
    ``id.linkedin.com/pulse/...``) its ``https://`` so it is read as a URL rather
    than rejected as a malformed slug."""
    value = (value or "").strip()
    if not value.startswith("http") and re.match(r"(?:[\w-]+\.)?linkedin\.com/", value, re.I):
        value = "https://" + value
    return value


def profile_url(value: str) -> str | None:
    """Accept a full profile URL, a ``/in/slug`` path, or a bare slug."""
    value = _with_scheme(value)
    if not value:
        return None
    if value.startswith("http"):
        url = clean_url(value)
        return url if url and "/in/" in url else None
    value = value.strip("/")
    if value.startswith("in/"):
        value = value[3:]
    if re.fullmatch(r"[\w\-%\.]{3,100}", value):
        return f"https://www.linkedin.com/in/{value}"
    return None


def company_url(value: str) -> str | None:
    """Accept a company/school/showcase URL, a path, or a bare slug."""
    value = _with_scheme(value)
    if not value:
        return None
    if value.startswith("http"):
        url = clean_url(value)
        if not url:
            return None
        match = re.search(r"/(company|school|showcase)/([^/?#]+)", url)
        return (
            f"https://www.linkedin.com/{match.group(1)}/{match.group(2)}"
            if match
            else None
        )
    value = value.strip("/")
    match = re.match(r"(company|school|showcase)/(.+)", value)
    if match:
        return f"https://www.linkedin.com/{match.group(1)}/{match.group(2)}"
    if re.fullmatch(r"[\w\-%\.]{2,100}", value):
        return f"https://www.linkedin.com/company/{value}"
    return None


def post_url(value: str) -> str | None:
    """Accept a post permalink, a share URL, an ``urn:li:activity:`` or a bare id.

    Bare ids and urns are rebuilt as ``/feed/update/urn:li:activity:{id}``,
    which LinkedIn redirects to the real permalink.
    """
    value = _with_scheme(value)
    if not value:
        return None
    match = re.search(r"(?:activity[-:]|ugcPost[-:])(\d{10,})", value)
    if not match and re.fullmatch(r"\d{10,}", value):
        return f"https://www.linkedin.com/feed/update/urn:li:activity:{value}"
    if value.startswith("http"):
        url = clean_url(value)
        if url and ("/posts/" in url or "/feed/update/" in url or "/pulse/" in url):
            return url
        if match:
            return (
                "https://www.linkedin.com/feed/update/"
                f"urn:li:activity:{match.group(1)}"
            )
        return None
    if match:
        return (
            f"https://www.linkedin.com/feed/update/urn:li:activity:{match.group(1)}"
        )
    return None


def article_url(value: str) -> str | None:
    """A ``/pulse/`` article or newsletter issue link."""
    value = _with_scheme(value)
    if not value:
        return None
    if value.startswith("http"):
        url = clean_url(value)
        return url if url and ("/pulse/" in url or "/newsletters/" in url) else None
    if value.startswith("pulse/"):
        return f"https://www.linkedin.com/{value.strip('/')}"
    return None


def event_url(value: str) -> str | None:
    """An event permalink or a bare event id/slug."""
    value = _with_scheme(value)
    if not value:
        return None
    if value.startswith("http"):
        url = clean_url(value)
        match = re.search(r"/events/([^/?#]+)", url or "")
        return f"https://www.linkedin.com/events/{match.group(1)}" if match else None
    value = value.strip("/")
    if value.startswith("events/"):
        value = value[7:]
    if re.fullmatch(r"[\w\-%]{3,120}", value):
        return f"https://www.linkedin.com/events/{value}"
    return None


def job_id(value: str) -> str | None:
    """A numeric job id out of any LinkedIn job URL form, or a bare id."""
    value = _with_scheme(value)
    if re.fullmatch(r"\d{6,}", value):
        return value
    match = re.search(r"(?:currentJobId=|/view/(?:[^/?#]*?-)?)(\d{6,})", value)
    return match.group(1) if match else None


# -- dataset envelope -----------------------------------------------------


def envelope(source: str, given_input: str, record_type: str) -> dict:
    """The four fields every row in this portfolio carries."""
    return {
        "_input": given_input,
        "_source": source,
        "_scrapedAt": utc_now(),
        "recordType": record_type,
    }


def error_record(given_input: str, code: str, detail: str = "") -> dict:
    return {
        **envelope("none", given_input, "ERROR"),
        "_error": code,
        "_errorDetail": detail[:600],
    }


def notice_record(given_input: str, code: str, detail: str = "") -> dict:
    """A non-failure explanation row.

    Used when a run is correctly configured but the surface the buyer asked for
    needs a session cookie they did not supply. That is information, not a
    crash, so the run still succeeds and the dataset says why it is empty.
    """
    return {
        **envelope("none", given_input, "NOTICE"),
        "_notice": code,
        "_noticeDetail": detail[:600],
    }


# -- lead hygiene ---------------------------------------------------------

_FREE_MAIL = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "proton.me", "protonmail.com", "gmx.com", "mail.com", "qq.com",
}


def company_domain(website: str | None) -> str | None:
    """The bare domain of a company website, for mail-merge guesswork.

    This is the domain only. No email address is guessed or verified here: a
    fabricated address that bounces costs the sender their domain reputation,
    so the honest output is the domain plus the person's name, leaving the
    pattern to a verification tool that actually checks.
    """
    if not website:
        return None
    domain = re.sub(r"^https?://", "", website.strip().lower())
    domain = domain.split("/")[0].split("?")[0]
    domain = re.sub(r"^www\.", "", domain)
    if not re.fullmatch(r"[a-z0-9\-\.]+\.[a-z]{2,}", domain):
        return None
    if domain in _FREE_MAIL:
        return None
    return domain
