"""Query builders + email-extraction logic.

Extraction sources, in priority order (both are scanned, results
deduped -- a channel can list an email in either or both places):
  1. `user.description` -- the channel bio shown on the profile header.
  2. `panels[].description` where `__typename == "DefaultPanel"` -- the
     "About" panel section below the video player. `ExtensionPanel`
     entries (interactive third-party widgets) carry no text and are
     skipped.

Two regex passes are run against each text source:
  - A standard RFC-5322-ish email pattern.
  - A common "obfuscated" pattern (`name [at] domain [dot] com`,
    `name (at) domain (dot) com`, case-insensitive) -- a widespread,
    long-standing technique streamers use specifically to publish a
    real contact email while dodging naive spam-bot regexes. Detecting
    it is not a WAF bypass or account-security issue; it is unobfuscating
    text the account owner already chose to publish openly precisely so
    a human (or, now, a scraper) could read it.
"""

import re
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


CHANNEL_EMAIL_QUERY = """
query($login: String!) {
  user(login: $login) {
    id
    login
    displayName
    description
    panels {
      id
      __typename
      ... on DefaultPanel {
        title
        description
        linkURL
      }
    }
  }
}
"""

GAME_STREAMS_DISCOVERY_QUERY = """
query($name: String!, $first: Int!) {
  game(name: $name) {
    id
    name
    streams(first: $first, options: {sort: VIEWER_COUNT}) {
      edges {
        node {
          viewersCount
          broadcaster {
            login
            displayName
          }
        }
      }
    }
  }
}
"""

STANDARD_EMAIL_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._%+\-]*@[a-zA-Z0-9][a-zA-Z0-9.\-]*\.[a-zA-Z]{2,}")

# "name (at) domain (dot) com" / "name [AT] domain [DOT] com" / "name AT domain DOT com"
OBFUSCATED_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9][a-zA-Z0-9._%+\-]*\s*[\(\[]?\s*(?:at|@)\s*[\)\]]?\s*"
    r"[a-zA-Z0-9][a-zA-Z0-9\-]*\s*[\(\[]?\s*(?:dot|\.)\s*[\)\]]?\s*[a-zA-Z]{2,}",
    re.IGNORECASE,
)


def _normalize_obfuscated(match: str) -> str:
    text = re.sub(r"\s*[\(\[]?\s*(?:at)\s*[\)\]]?\s*", "@", match, flags=re.IGNORECASE)
    text = re.sub(r"\s*[\(\[]?\s*(?:dot)\s*[\)\]]?\s*", ".", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", "", text)


def find_emails(text: str | None) -> list[str]:
    if not text:
        return []
    found = set()
    for m in STANDARD_EMAIL_RE.finditer(text):
        found.add(m.group(0).lower())
    for m in OBFUSCATED_EMAIL_RE.finditer(text):
        normalized = _normalize_obfuscated(m.group(0)).lower()
        if STANDARD_EMAIL_RE.fullmatch(normalized):
            found.add(normalized)
    return sorted(found)


def extract_channel_emails(data: dict, login: str) -> dict:
    user = data.get("user")
    if user is None:
        return extract_error(login, "channel_not_found")

    description = user.get("description")
    panels = user.get("panels") or []

    sources = []
    description_emails = find_emails(description)
    if description_emails:
        sources.append({"field": "description", "emails": description_emails})

    panel_emails: list[str] = []
    for panel in panels:
        if panel.get("__typename") != "DefaultPanel":
            continue
        for field in ("title", "description"):
            text = panel.get(field)
            emails = find_emails(text)
            if emails:
                sources.append({"field": f"panel:{field}", "panelId": panel.get("id"), "emails": emails})
                panel_emails.extend(emails)

    all_emails = sorted(set(description_emails) | set(panel_emails))

    return {
        "_input": login,
        "_source": "S1-gql",
        "_scrapedAt": utc_now_iso(),
        "login": user.get("login"),
        "displayName": user.get("displayName"),
        "emails": all_emails or None,
        "emailFound": bool(all_emails),
        "emailSources": sources or None,
        "description": description,
    }


def extract_error(login: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": login,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
