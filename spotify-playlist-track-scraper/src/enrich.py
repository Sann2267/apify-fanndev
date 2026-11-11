"""Optional ISRC and popularity enrichment, and why it is optional.

ISRC (the recording's global identifier, what royalty and radio systems key on)
and Spotify's 0-100 popularity score exist on exactly one surface an anonymous
client can reach: ``api.spotify.com/v1/search``. They are absent from every
GraphQL payload the web player uses, so there is no way to get them alongside
the playlist -- each track costs its own search request.

That endpoint is also the only rate-limited surface in this actor. Measured on
2026-09-20: an anonymous token gets a few dozen searches before the endpoint
starts answering ``429 QUOTA_EXCEEDED`` with ``Retry-After: 73444`` -- roughly
twenty hours -- and the ban follows the *IP*, not the token, so refreshing
credentials does not clear it. That is why enrichment is off by default, why it
is worth pointing at a proxy, and why the first 429 stops enrichment for the
whole run instead of retrying into a longer ban. Tracks already enriched keep
their data; the rest are marked and the run finishes normally.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from src.constants import REQUEST_DELAY
from src.spotify import SpotifyClient, SpotifyError

# Featured-artist suffixes vary between the playlist title and the search title
# for the same recording, so they are ignored when comparing. Version suffixes
# like " - 2022 Remaster" are deliberately *not* stripped: those are genuinely
# different recordings with different ISRCs, and collapsing them would attach
# one recording's identifier to another. Matching never rewrites trackName.
FEATURING = re.compile(r"\s*[-(\[]\s*(?:feat\.?|ft\.?|with)\b.*$", re.I)
NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def normalise(text: str | None) -> str:
    if not text:
        return ""
    stripped = FEATURING.sub("", text)
    return " ".join(NON_WORD.sub(" ", stripped).lower().split())


def quote(text: str) -> str:
    """Spotify's search syntax has no escape for a double quote -- drop them."""
    return text.replace('"', " ").strip()


class QuotaExhausted(RuntimeError):
    """The search endpoint has started refusing this IP for the day."""


class Enricher:
    """Adds ISRC and popularity to track rows, one search request at a time."""

    def __init__(self, client: SpotifyClient, market: str, log: Any = None) -> None:
        self.client = client
        self.market = market
        self.log = log
        self.exhausted = False
        self.enriched = 0
        self.exact = 0
        self.attempted = 0

    async def enrich(self, rows: list[dict], budget: int) -> None:
        """Enrich up to ``budget`` rows in place."""
        for row in rows[:budget]:
            if self.exhausted:
                row["isrcLookup"] = "skipped-quota"
                continue
            try:
                await self._one(row)
            except QuotaExhausted:
                self.exhausted = True
                row["isrcLookup"] = "skipped-quota"
                if self.log:
                    self.log.warning(
                        "Spotify's search endpoint has rate-limited this IP, so ISRC "
                        "and popularity enrichment stops here. The ban follows the IP "
                        "for about 20 hours -- enable the proxy option to get a "
                        f"different one. {self.enriched} track(s) were enriched first."
                    )
            await asyncio.sleep(REQUEST_DELAY)
        for row in rows[budget:]:
            row.setdefault("isrcLookup", "not-attempted")

    async def _one(self, row: dict) -> None:
        name = quote(row.get("trackName") or "")
        artist = quote(row.get("artistName") or "")
        if not name:
            row["isrcLookup"] = "no-title"
            return
        query = f'track:"{name}"' + (f' artist:"{artist}"' if artist else "")
        self.attempted += 1
        try:
            payload = await self.client.search(query, "track", limit=20, market=self.market)
        except SpotifyError as exc:
            if "429" in str(exc):
                raise QuotaExhausted(str(exc)) from exc
            row["isrcLookup"] = "search-failed"
            return

        items = [i for i in ((payload.get("tracks") or {}).get("items") or []) if i]
        if not items:
            row["isrcLookup"] = "no-match"
            return

        # Prefer the exact same recording. Spotify issues a separate track id per
        # release, so the same ISRC can sit behind several ids -- matching the
        # playlist's own uri is the only way to be sure the score belongs to the
        # track that was actually in the playlist.
        wanted = row.get("trackUri")
        match = next((i for i in items if i.get("uri") == wanted), None)
        confidence = "exact"
        if match is None:
            target_name, target_artist = normalise(row.get("trackName")), normalise(artist)
            match = next(
                (
                    i
                    for i in items
                    if normalise(i.get("name")) == target_name
                    and any(normalise(a.get("name")) == target_artist
                            for a in (i.get("artists") or []))
                ),
                None,
            )
            confidence = "title-artist"
        if match is None:
            row["isrcLookup"] = "no-match"
            return

        row["isrc"] = (match.get("external_ids") or {}).get("isrc")
        row["popularity"] = match.get("popularity")
        row["previewUrl"] = match.get("preview_url")
        row["isrcLookup"] = confidence
        self.enriched += 1
        if confidence == "exact":
            self.exact += 1
