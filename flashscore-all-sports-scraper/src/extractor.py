"""Feed decoding + record shaping.

Flashscore's feed is a delimited format, not JSON:

    SA÷1¬~ZA÷ARGENTINA: Liga Profesional¬ZEE÷naYhNOaA¬ZY÷Argentina¬~AA÷WSSid6OM¬AD÷1788818400¬AE÷Barracas Central¬...

Records are split on "~", fields on "¬", key/value on "÷". Per
.ai/conventions/dataset-envelope.md the decoded key/value pairs are passed
through **verbatim** and the friendly names are *added alongside* them, never
substituted -- the upstream key set is undocumented and changes without
notice, so dropping unknown keys would silently lose data.

Two upstream quirks the parser has to absorb, both observed during recon:

* Tournament context lives in a *separate, preceding* record (`ZA` header),
  not on the match rows. The parser carries the last header forward.
* Score keys (`AG`/`AH`) are simply absent before kick-off rather than 0 --
  so "no score" and "0-0" are different states and must not be collapsed.
"""

import re
from datetime import datetime, timezone

from src.constants import (
    MATCH_FIELDS,
    MATCH_URL,
    SPORTS,
    STATUS_BY_AB,
    TOURNAMENT_FIELDS,
    WINNER_BY_AS,
)

# Flashscore match ids are 8-char base62-ish tokens (e.g. "WSSid6OM"). Accept a
# bare id or any flashscore URL containing one.
_ID_RE = re.compile(r"(?:match/(?:[a-z-]+/)?)?([A-Za-z0-9]{8})(?:/|$|#|\?)")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_to_iso(value) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


def extract_match_id(raw: str) -> str:
    """Accepts 'WSSid6OM', 'https://www.flashscore.com/match/WSSid6OM/' or the
    '/match/football/<id>/' variant, and returns the bare id."""
    raw = (raw or "").strip()
    if re.fullmatch(r"[A-Za-z0-9]{8}", raw):
        return raw
    m = _ID_RE.search(raw)
    return m.group(1) if m else ""


def parse_feed(body: str) -> list[dict]:
    """Decode a raw feed body into a list of key/value dicts, one per record."""
    out: list[dict] = []
    for chunk in (body or "").split("~"):
        rec: dict[str, str] = {}
        for field in chunk.split("¬"):
            if "÷" in field:
                key, value = field.split("÷", 1)
                rec[key] = value
        if rec:
            out.append(rec)
    return out


def split_matches(body: str) -> list[tuple[dict, dict]]:
    """Return (match_record, tournament_header) pairs, resolving the
    header-carries-forward layout described in the module docstring."""
    pairs: list[tuple[dict, dict]] = []
    header: dict = {}
    for rec in parse_feed(body):
        if "ZA" in rec:
            header = rec
        elif "AA" in rec:
            pairs.append((rec, header))
    return pairs


def wrap_match(raw: dict, header: dict, sport_id: int, input_value: str) -> dict:
    record = {
        "_input": input_value,
        "_source": "S1-feed",
        "_scrapedAt": utc_now_iso(),
        "recordType": "MATCH",
        "sportId": sport_id,
        "sportName": SPORTS.get(sport_id, f"sport-{sport_id}"),
    }
    for key, name in TOURNAMENT_FIELDS.items():
        if key in header:
            record[name] = header[key]
    for key, name in MATCH_FIELDS.items():
        if key in raw:
            record[name] = raw[key]

    record["status"] = STATUS_BY_AB.get(raw.get("AB", ""), "UNKNOWN")
    if "AS" in raw:
        record["winner"] = WINNER_BY_AS.get(raw["AS"], raw["AS"])
    if "AD" in raw:
        record["startTime"] = ts_to_iso(raw["AD"])
    if "AO" in raw:
        record["finishedAt"] = ts_to_iso(raw["AO"])
    if raw.get("AA"):
        record["matchUrl"] = MATCH_URL.format(match=raw["AA"])
    if "AG" in raw and "AH" in raw:
        record["score"] = f"{raw['AG']}-{raw['AH']}"

    record["_raw"] = raw
    return record


def parse_stats(body: str) -> list[dict]:
    """Statistics feed: SE=period label, SD=stat id, SG=stat name,
    SH=home value, SI=away value. Verified live -- includes expected goals
    (xG) and possession for football."""
    stats: list[dict] = []
    period = None
    for rec in parse_feed(body):
        if "SE" in rec:
            period = rec["SE"]
        if "SG" in rec:
            stats.append(
                {
                    "period": period,
                    "statId": rec.get("SD"),
                    "name": rec.get("SG"),
                    "home": rec.get("SH"),
                    "away": rec.get("SI"),
                }
            )
    return stats


def parse_incidents(body: str) -> list[dict]:
    """Summary feed: IB=minute, IF=player, IE=side (1 home / 2 away),
    IA=incident type id, IK=note. Type ids are NOT documented upstream and
    were not exhaustively observed, so the raw id ships alongside."""
    out: list[dict] = []
    stage = None
    for rec in parse_feed(body):
        if "AC" in rec and "IG" in rec:
            stage = rec.get("AC")
        if "IB" in rec or "IF" in rec:
            out.append(
                {
                    "stage": stage,
                    "minute": rec.get("IB"),
                    "player": rec.get("IF"),
                    "side": {"1": "HOME", "2": "AWAY"}.get(rec.get("IE", ""), rec.get("IE")),
                    "incidentTypeId": rec.get("IA"),
                    "note": rec.get("IK") or rec.get("IJ"),
                    "_raw": rec,
                }
            )
    return out


def wrap_detail(match_id: str, sport_id: int, parts: dict) -> dict:
    return {
        "_input": match_id,
        "_source": "S1-feed",
        "_scrapedAt": utc_now_iso(),
        "recordType": "MATCH_DETAIL",
        "matchId": match_id,
        "sportId": sport_id,
        "sportName": SPORTS.get(sport_id, f"sport-{sport_id}"),
        "matchUrl": MATCH_URL.format(match=match_id),
        **parts,
    }


def wrap_sport(sport_id: int, matches_today: int, sample_tournament: str) -> dict:
    return {
        "_input": "reference",
        "_source": "S1-feed",
        "_scrapedAt": utc_now_iso(),
        "recordType": "SPORT",
        "sportId": sport_id,
        "sportName": SPORTS.get(sport_id, f"sport-{sport_id}"),
        "isNamed": sport_id in SPORTS,
        "matchesToday": matches_today,
        "sampleTournament": sample_tournament,
    }


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
