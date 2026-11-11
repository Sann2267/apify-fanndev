"""Voyager helpers for the surfaces that no cookie-free path reaches.

Everything in this module needs the buyer's own ``li_at``. Anonymous callers get
HTTP 403 from ``/voyager/api/*`` -- verified 2026-09-20 -- and there is no guest
equivalent for event attendees, a company's employee list or a school's alumni.

The awkward part of Voyager is ``queryId``: every GraphQL call names a query by
a hash like ``voyagerSocialDashReactions.a1b2c3...`` and LinkedIn rotates those
hashes with each web release, so any hash hard-coded today stops resolving in
weeks. This module therefore harvests the current hashes out of LinkedIn's own
JavaScript bundles at run time and only falls back to pinned values if that
fails. The bundles are not served to logged-out visitors, which is why the
harvest runs inside the authenticated session rather than at build time.
"""

from __future__ import annotations

import re
from typing import Any

from src.linkedin import AuthRequired, LinkedInClient, LinkedInError
from src.parse import clean_url, collapse, split_name

# Last-known-good hashes. They are a cushion for the harvest, not a promise:
# when both the harvest and these fail, the actor says so rather than
# returning an empty dataset that looks like "no results".
PINNED_QUERY_IDS = {
    "reactions": "voyagerSocialDashReactions.b1b96ab5ab2b4bc48e0ee76ec2bcccc2",
    "comments": "voyagerSocialDashComments.0d0d4e4bbaee0c0bbdeb50e6e5b26af2",
    "eventAttendees": "voyagerEventsDashProfessionalEvents.b7b6e0e0b8f7e0a9c8a0c5f1e3d2b1a0",
    "searchClusters": "voyagerSearchDashClusters.b0928897b71bd00a5a7291755dcd64f0",
}

_BUNDLE = re.compile(r'https://static\.licdn\.com/[^"\'\s]+?\.js')
_QUERY_ID = re.compile(r'"(voyager[A-Za-z]+\.[0-9a-f]{16,})"')


class QueryIdResolver:
    """Finds and caches the current GraphQL query hashes for one run."""

    def __init__(self, client: LinkedInClient, log: Any) -> None:
        self.client = client
        self.log = log
        self._harvested: dict[str, str] = {}
        self._attempted = False

    async def _harvest(self) -> None:
        """Read the feed shell, then its JS bundles, collecting query hashes."""
        self._attempted = True
        try:
            shell = await self.client.fetch(
                "https://www.linkedin.com/feed/", allow_redirects=True
            )
        except LinkedInError as exc:
            self.log.warning(f"Could not load the app shell to read query ids: {exc}")
            return
        bundles = list(dict.fromkeys(_BUNDLE.findall(shell)))
        if not bundles:
            self.log.warning(
                "No JavaScript bundles in the app shell -- falling back to "
                "pinned query ids."
            )
            return
        # A handful is enough; the social and search queries cluster together.
        for url in bundles[:12]:
            try:
                body = await self.client.fetch(url)
            except LinkedInError:
                continue
            for query_id in _QUERY_ID.findall(body):
                prefix = query_id.split(".", 1)[0]
                self._harvested.setdefault(prefix, query_id)
        self.log.info(
            f"Harvested {len(self._harvested)} Voyager query ids from "
            f"{len(bundles[:12])} bundles."
        )

    async def get(self, name: str, prefix: str) -> str:
        if not self._attempted:
            await self._harvest()
        harvested = self._harvested.get(prefix)
        if harvested:
            return harvested
        pinned = PINNED_QUERY_IDS.get(name)
        if not pinned:
            raise LinkedInError(f"No query id available for {name}.")
        self.log.warning(
            f"Using the pinned query id for {name}; LinkedIn may have rotated it."
        )
        return pinned


# -- response walking -----------------------------------------------------


def walk(node: Any, key: str) -> list:
    """Every value stored under ``key`` anywhere in a nested structure.

    Voyager wraps results differently per endpoint and per release -- sometimes
    under ``elements``, sometimes under ``*Elements``, sometimes one level
    deeper inside ``data``. Searching by key is what keeps this working when
    LinkedIn moves the envelope but keeps the payload.
    """
    found: list = []
    if isinstance(node, dict):
        for name, value in node.items():
            if name == key:
                found.append(value)
            else:
                found.extend(walk(value, key))
    elif isinstance(node, list):
        for item in node:
            found.extend(walk(item, key))
    return found


def first_text(node: Any) -> str | None:
    """Voyager text is ``{"text": "..."}`` about as often as it is a string."""
    if isinstance(node, str):
        return collapse(node) or None
    if isinstance(node, dict):
        for key in ("text", "value", "name", "title"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return collapse(value)
            if isinstance(value, dict):
                nested = first_text(value)
                if nested:
                    return nested
    return None


def person_from_voyager(node: dict) -> dict | None:
    """Normalise whichever member shape an endpoint returned into one record."""
    if not isinstance(node, dict):
        return None
    name = (
        first_text(node.get("title"))
        or first_text(node.get("name"))
        or collapse(
            " ".join(
                part
                for part in (node.get("firstName"), node.get("lastName"))
                if isinstance(part, str)
            )
        )
        or None
    )
    if not name:
        return None
    url = (
        node.get("navigationUrl")
        or node.get("publicIdentifier")
        or first_text(node.get("navigationContext"))
    )
    if url and not str(url).startswith("http"):
        url = f"https://www.linkedin.com/in/{url}"
    url = clean_url(url) if url else None
    first, last = split_name(name)
    headline = (
        first_text(node.get("headline"))
        or first_text(node.get("primarySubtitle"))
        or first_text(node.get("occupation"))
    )
    return {
        "fullName": name,
        "firstName": first,
        "lastName": last,
        "headline": headline,
        "profileUrl": url,
        "location": first_text(node.get("secondarySubtitle"))
        or first_text(node.get("geoRegion")),
    }


def require_cookie(actor_input: dict, what: str) -> str:
    """Read ``sessionCookie`` from the input, or explain why the run cannot go on."""
    cookie = (actor_input.get("sessionCookie") or "").strip()
    if not cookie:
        raise AuthRequired(
            f"{what} has no logged-out equivalent on LinkedIn -- an anonymous "
            "request is answered with 403 or bounced to the login wall. Paste "
            "the li_at cookie from a browser where you are already signed in."
        )
    if cookie.lower().startswith("li_at="):
        cookie = cookie.split("=", 1)[1]
    return cookie.strip().strip('"')
