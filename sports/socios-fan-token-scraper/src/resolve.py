"""Turn what a buyer types into the UUIDs this API insists on.

Every cross-reference in the Chiliz gateway is a bare UUID. Nobody knows that
AC Milan is ``403d8e06-fbf2-4a5e-a379-09edf90cb2a0``, so the partner filter
accepts a club name, a token symbol or a short code and resolves it against the
partner directory -- which is a single 231-row request, cheap enough to always
pay for when a filter is in play.
"""

from __future__ import annotations

import re

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def is_uuid(value: str) -> bool:
    return bool(UUID.match(value.strip()))


def _keys(partner: dict) -> set[str]:
    """Every string a buyer might plausibly type for this partner."""
    out = set()
    for field in ("name", "shortName", "tokenSymbol"):
        value = partner.get(field)
        if value:
            text = str(value).strip().casefold()
            out.add(text)
            out.add(text.lstrip("$"))
    return out


def resolve_partners(
    wanted: list[str], partners: list[dict]
) -> tuple[list[str], list[tuple[str, str]]]:
    """Map club names, symbols, short codes or ids to partner UUIDs.

    Exact matches win outright. Failing that, an input that is contained in
    exactly one club's name resolves to it, so ``Barcelona`` finds
    ``FC Barcelona`` and ``Sauber`` finds ``Stake F1 Team KICK Sauber``. An
    input that matches several -- ``Milan`` is both ``AC Milan`` and
    ``FC Internazionale Milano`` -- is deliberately *not* resolved: guessing
    which club the buyer meant would quietly scrape the wrong one.

    Returns the resolved ids plus ``(input, reason)`` for everything that did
    not resolve, so the caller can emit one ERROR row per miss rather than
    silently narrowing the run to whatever happened to match.
    """
    index: dict[str, str] = {}
    for partner in partners:
        identifier = partner.get("id")
        if not identifier:
            continue
        for key in _keys(partner):
            index.setdefault(key, identifier)

    known_ids = {p.get("id") for p in partners}
    resolved: list[str] = []
    unmatched: list[tuple[str, str]] = []

    for raw in wanted:
        text = raw.strip()
        if is_uuid(text):
            if text in known_ids:
                resolved.append(text)
            else:
                unmatched.append((raw, "no partner has this id"))
            continue

        folded = text.casefold()
        found = index.get(folded) or index.get(folded.lstrip("$"))
        if found:
            resolved.append(found)
            continue

        needle = folded.lstrip("$")
        candidates = [
            partner
            for partner in partners
            if partner.get("id") and needle in str(partner.get("name") or "").casefold()
        ]
        if len(candidates) == 1:
            resolved.append(candidates[0]["id"])
        elif candidates:
            names = ", ".join(sorted(str(c.get("name")) for c in candidates)[:6])
            unmatched.append(
                (raw, f"matches {len(candidates)} clubs ({names}) -- name one exactly")
            )
        else:
            unmatched.append((raw, "no partner matches this name, symbol or code"))

    return list(dict.fromkeys(resolved)), unmatched
