"""Parsing and record shaping for Nasdaq / FINRA / SEC payloads.

Numbers arrive formatted for humans in two of the three sources -- Nasdaq sends
``"74,230,933"`` and FINRA sends ``"403792.045672"`` (fractional share volume is
real: it comes from odd-lot and fractional executions). Both are parsed into
numeric fields *alongside* the original string, per
.ai/conventions/dataset-envelope.md, so a consumer can compute on the number and
still audit what was published.

Dates are normalised to ISO ``YYYY-MM-DD``. Nasdaq publishes ``MM/DD/YYYY`` and
FINRA publishes ``YYYYMMDD``; leaving both raw would make the two sources
un-joinable, which is the whole point of putting them in one Actor.
"""

from datetime import datetime, timezone

from src.constants import FINRA_COLUMNS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_number(value):
    """'74,230,933' -> 74230933, '2.037993' -> 2.037993, '' -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text in ("-", "N/A", "n/a"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return None


def us_date_to_iso(value):
    """Nasdaq's MM/DD/YYYY -> YYYY-MM-DD."""
    try:
        return datetime.strptime(str(value).strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def compact_date_to_iso(value):
    """FINRA's YYYYMMDD -> YYYY-MM-DD."""
    text = str(value or "").strip()
    if len(text) != 8 or not text.isdigit():
        return None
    return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"


def _envelope(input_value: str, source: str, record_type: str) -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }


# --- Nasdaq ---------------------------------------------------------------

def wrap_short_interest(symbol: str, row: dict, info: dict | None) -> dict:
    """One settlement-date row of Nasdaq's short interest table.

    ``daysToCover`` is Nasdaq's own arithmetic (interest / average daily
    volume); it is passed through rather than recomputed, so the dataset
    matches what Nasdaq publishes even when its inputs are rounded.
    """
    record = _envelope(symbol, "S1-nasdaq", "SHORT_INTEREST")
    record.update(
        {
            "symbol": symbol,
            "settlementDate": us_date_to_iso(row.get("settlementDate")),
            "settlementDateRaw": row.get("settlementDate"),
            "shortInterest": to_number(row.get("interest")),
            "avgDailyShareVolume": to_number(row.get("avgDailyShareVolume")),
            "daysToCover": to_number(row.get("daysToCover")),
            "companyName": (info or {}).get("companyName"),
            "exchange": (info or {}).get("exchange"),
            "isNasdaqListed": (info or {}).get("isNasdaqListed"),
            "stockType": (info or {}).get("stockType"),
            "_raw": row,
        }
    )
    return record


def wrap_company_info(symbol: str, info: dict) -> dict:
    record = _envelope(symbol, "S1-nasdaq", "SYMBOL_INFO")
    primary = info.get("primaryData") or {}
    record.update(
        {
            "symbol": info.get("symbol") or symbol,
            "companyName": info.get("companyName"),
            "exchange": info.get("exchange"),
            "isNasdaqListed": info.get("isNasdaqListed"),
            "isNasdaq100": info.get("isNasdaq100"),
            "stockType": info.get("stockType"),
            "lastSalePrice": to_number(primary.get("lastSalePrice")),
            "netChange": to_number(primary.get("netChange")),
            "percentageChange": primary.get("percentageChange"),
            "_raw": info,
        }
    )
    return record


# --- FINRA ----------------------------------------------------------------

def parse_finra_file(text: str) -> list[dict]:
    """Decode FINRA's pipe-delimited daily file.

    The last line is a footer (``Date|Symbol|...`` style trailer starting with
    a record count) on some days, so rows are validated by column count rather
    than by position -- a footer that changes shape is skipped instead of
    poisoning the dataset with a half-parsed row.
    """
    rows: list[dict] = []
    lines = (text or "").splitlines()
    if not lines:
        return rows
    header = [h.strip() for h in lines[0].split("|")]
    if header[: len(FINRA_COLUMNS)] != list(FINRA_COLUMNS):
        raise ValueError(
            f"FINRA column layout changed: expected {FINRA_COLUMNS}, got {header}"
        )
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) != len(header):
            continue  # footer / trailer line
        rows.append(dict(zip(header, parts)))
    return rows


def wrap_short_volume(venue: str, date_iso: str, row: dict) -> dict:
    short_vol = to_number(row.get("ShortVolume"))
    total_vol = to_number(row.get("TotalVolume"))
    ratio = None
    if isinstance(short_vol, (int, float)) and isinstance(total_vol, (int, float)) and total_vol:
        ratio = round(short_vol / total_vol, 6)

    record = _envelope(f"{venue}:{date_iso}", "S1-finra", "SHORT_VOLUME")
    record.update(
        {
            "symbol": (row.get("Symbol") or "").strip() or None,
            "date": compact_date_to_iso(row.get("Date")) or date_iso,
            "venue": venue,
            "shortVolume": short_vol,
            "shortExemptVolume": to_number(row.get("ShortExemptVolume")),
            "totalVolume": total_vol,
            # The ratio is the number desks actually watch, and computing it
            # here means every consumer gets the same definition.
            "shortVolumeRatio": ratio,
            "market": (row.get("Market") or "").strip() or None,
            "_raw": row,
        }
    )
    return record


# --- SEC ------------------------------------------------------------------

def wrap_filing(identifier: str, company: dict, filing: dict) -> dict:
    cik = str(company.get("cik") or "").lstrip("0")
    accession = filing.get("accessionNumber") or ""
    nodash = accession.replace("-", "")
    doc = filing.get("primaryDocument") or ""
    record = _envelope(identifier, "S1-sec", "FILING")
    record.update(
        {
            "cik": company.get("cik"),
            "companyName": company.get("name"),
            "tickers": company.get("tickers") or [],
            "exchanges": company.get("exchanges") or [],
            "sic": company.get("sic"),
            "sicDescription": company.get("sicDescription"),
            "form": filing.get("form"),
            "accessionNumber": accession,
            "filingDate": filing.get("filingDate"),
            "reportDate": filing.get("reportDate") or None,
            "acceptanceDateTime": filing.get("acceptanceDateTime"),
            "items": filing.get("items") or None,
            "primaryDocument": doc or None,
            "primaryDocDescription": filing.get("primaryDocDescription") or None,
            "sizeBytes": to_number(filing.get("size")),
            "isXBRL": bool(filing.get("isXBRL")),
            "isInlineXBRL": bool(filing.get("isInlineXBRL")),
            "filingUrl": (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/{doc}"
                if cik and nodash and doc
                else None
            ),
            "filingIndexUrl": (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/{accession}-index.htm"
                if cik and nodash and accession
                else None
            ),
            "_raw": filing,
        }
    )
    return record


def wrap_company(identifier: str, company: dict) -> dict:
    addresses = company.get("addresses") or {}
    business = addresses.get("business") or {}
    recent = ((company.get("filings") or {}).get("recent") or {})
    forms = recent.get("form") or []
    record = _envelope(identifier, "S1-sec", "COMPANY")
    record.update(
        {
            "cik": company.get("cik"),
            "companyName": company.get("name"),
            "tickers": company.get("tickers") or [],
            "exchanges": company.get("exchanges") or [],
            "entityType": company.get("entityType"),
            "sic": company.get("sic"),
            "sicDescription": company.get("sicDescription"),
            "category": company.get("category"),
            "stateOfIncorporation": company.get("stateOfIncorporation"),
            "fiscalYearEnd": company.get("fiscalYearEnd"),
            "ein": company.get("ein") or None,
            "website": company.get("website") or None,
            "phone": company.get("phone") or None,
            "businessAddress": ", ".join(
                p for p in [
                    business.get("street1"), business.get("street2"), business.get("city"),
                    business.get("stateOrCountry"), business.get("zipCode"),
                ] if p
            ) or None,
            "filingCount": len(forms),
            "latestFilingDate": (recent.get("filingDate") or [None])[0],
            "latestFilingForm": forms[0] if forms else None,
            "formerNames": [f.get("name") for f in company.get("formerNames") or []],
            # filings.recent is up to 1,000 rows; older history lives in the
            # files[] shards, which this Actor does not fetch. Exposed so the
            # consumer can tell a complete history from a truncated one.
            "hasOlderFilingShards": bool((company.get("filings") or {}).get("files")),
        }
    )
    return record


def wrap_fulltext_hit(query: str, hit: dict) -> dict:
    src = hit.get("_source") or {}
    adsh = src.get("adsh") or ""
    nodash = adsh.replace("-", "")
    cik = (src.get("ciks") or [""])[0].lstrip("0")
    doc_id = hit.get("_id") or ""
    doc = doc_id.split(":", 1)[1] if ":" in doc_id else ""
    display = (src.get("display_names") or [None])[0]

    record = _envelope(query, "S1-sec-fulltext", "FILING_MATCH")
    record.update(
        {
            "companyDisplayName": display,
            "cik": (src.get("ciks") or [None])[0],
            "form": src.get("form"),
            "rootForms": src.get("root_forms") or [],
            "accessionNumber": adsh,
            "fileDate": src.get("file_date"),
            "periodEnding": src.get("period_ending"),
            "items": src.get("items") or [],
            "fileType": src.get("file_type"),
            "fileDescription": src.get("file_description"),
            "documentId": doc_id,
            "sic": (src.get("sics") or [None])[0],
            "businessState": (src.get("biz_states") or [None])[0],
            "incorporationState": (src.get("inc_states") or [None])[0],
            "relevanceScore": hit.get("_score"),
            "documentUrl": (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/{doc}"
                if cik and nodash and doc
                else None
            ),
            "_raw": hit,
        }
    )
    return record


def wrap_reference(source: str, url: str, ok: bool, detail: str, sample: dict | None = None) -> dict:
    record = _envelope("reference", "S1-probe" if ok else "none", "SOURCE")
    record.update(
        {
            "source": source,
            "url": url,
            "isAvailable": ok,
            "detail": detail,
            "sample": sample or {},
        }
    )
    return record


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    record = _envelope(input_value, "none", "ERROR")
    record.update({"_error": error_kind, "_errorDetail": detail})
    return record
