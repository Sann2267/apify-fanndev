"""Address parsing, RFC-shaped syntax checks, normalisation and typo repair.

Everything in here is free: no network, no rate limit, no failure mode. An
address that dies at this layer never costs a DNS lookup or an SMTP session,
which is what keeps a 100k-row list cheap to clean.
"""

from __future__ import annotations

import re

from src.data import DISPOSABLE_DOMAINS, FREE_PROVIDERS, ROLE_PREFIXES, TYPO_TARGETS

# Deliberately stricter than RFC 5322 in one direction (no quoted local parts,
# no comments, no IP-literal domains) because mailbox providers reject those in
# practice, and looser in another (any TLD of 2+ letters) so new gTLDs pass.
LOCAL_PART = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
ADDRESS = re.compile(
    rf"^(?P<local>{LOCAL_PART})@(?P<domain>{DOMAIN_LABEL}(?:\.{DOMAIN_LABEL})*\.[A-Za-z]{{2,}})$"
)

# Providers that ignore dots and everything after a plus in the local part.
# Two addresses that normalise to the same mailbox are one send, not two.
DOT_INSENSITIVE = {"gmail.com", "googlemail.com"}
PLUS_ALIASING = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "icloud.com", "me.com", "proton.me", "protonmail.com", "fastmail.com",
    "yandex.ru", "zoho.com",
}

MAX_LOCAL = 64      # RFC 5321 section 4.5.3.1.1
MAX_TOTAL = 254     # the practical ceiling every MTA enforces


def levenshtein(a: str, b: str, cutoff: int = 2) -> int:
    """Edit distance, abandoned early once it cannot land within `cutoff`."""
    if abs(len(a) - len(b)) > cutoff:
        return cutoff + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (ca != cb),
            ))
        if min(current) > cutoff:
            return cutoff + 1
        previous = current
    return previous[-1]


def suggest_domain(domain: str) -> str | None:
    """Nearest well-known provider within the allowed edit distance, or None.

    Only fires for domains that are *not* already valid targets, so
    'gmail.com' never gets 'corrected' to 'googlemail.com'.

    The budget scales with length: two edits on a nine-character domain is a
    typo, two edits on a six-character one is a different company. Without
    that guard 'acme.com' gets 'corrected' to 'me.com', which is worse than
    saying nothing at all.
    """
    if domain in TYPO_TARGETS or domain in FREE_PROVIDERS:
        return None
    best: tuple[int, str] | None = None
    for candidate in TYPO_TARGETS:
        budget = 1 if min(len(domain), len(candidate)) <= 8 else 2
        distance = levenshtein(domain, candidate, cutoff=budget)
        if distance <= budget and (best is None or distance < best[0]):
            best = (distance, candidate)
    return best[1] if best else None


def parse(raw: str) -> dict:
    """Split, validate and classify one address without touching the network."""
    value = (raw or "").strip()
    # Tolerate the shapes that turn up in exported lists.
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()
    if "<" in value and value.endswith(">"):
        value = value[value.rindex("<") + 1:-1].strip()
    value = value.strip(" \t\r\n,;")

    result: dict = {
        "email": value,
        "localPart": None,
        "domain": None,
        "normalizedEmail": None,
        "syntaxValid": False,
        "syntaxError": None,
        "isRoleAccount": False,
        "isFreeProvider": False,
        "isDisposable": False,
        "isAlias": False,
        "hasTypo": False,
        "suggestedEmail": None,
    }

    if not value:
        result["syntaxError"] = "empty"
        return result
    if value.count("@") != 1:
        result["syntaxError"] = "missing_or_multiple_at"
        return result
    if len(value) > MAX_TOTAL:
        result["syntaxError"] = "too_long"
        return result

    match = ADDRESS.match(value)
    if not match:
        local_raw, _, domain_raw = value.partition("@")
        if not local_raw:
            result["syntaxError"] = "empty_local_part"
        elif not domain_raw:
            result["syntaxError"] = "empty_domain"
        elif ".." in value:
            result["syntaxError"] = "consecutive_dots"
        elif " " in value:
            result["syntaxError"] = "contains_space"
        elif "." not in domain_raw:
            result["syntaxError"] = "domain_has_no_tld"
        else:
            result["syntaxError"] = "invalid_characters"
        result["domain"] = domain_raw.lower() or None
        result["localPart"] = local_raw or None
        return result

    local = match.group("local")
    domain = match.group("domain").lower().rstrip(".")
    if len(local) > MAX_LOCAL:
        result.update({"domain": domain, "localPart": local, "syntaxError": "local_part_too_long"})
        return result

    canonical_local = local
    if domain in PLUS_ALIASING and "+" in canonical_local:
        canonical_local = canonical_local.split("+", 1)[0]
        result["isAlias"] = True
    if domain in DOT_INSENSITIVE:
        stripped = canonical_local.replace(".", "")
        if stripped != canonical_local:
            result["isAlias"] = True
            canonical_local = stripped

    suggestion = suggest_domain(domain)

    result.update({
        "localPart": local,
        "domain": domain,
        "normalizedEmail": f"{canonical_local.lower()}@{domain}",
        "syntaxValid": True,
        "isRoleAccount": local.split("+", 1)[0].lower() in ROLE_PREFIXES,
        "isFreeProvider": domain in FREE_PROVIDERS,
        "isDisposable": domain in DISPOSABLE_DOMAINS,
        "hasTypo": suggestion is not None,
        "suggestedEmail": f"{local}@{suggestion}" if suggestion else None,
    })
    return result
