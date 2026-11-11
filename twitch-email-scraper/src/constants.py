"""Endpoints, headers, whitelists -- all in one place.

Scope note: this actor extracts business/contact email addresses that
streamers VOLUNTARILY publish in their own public channel bio
(`user.description`) and "About" panels -- the exact same fields a
human visitor sees on twitch.tv/<channel>/about, most often explicitly
labeled "Business inquiries:" / "For business:" / a management agency
contact. It never logs in, never accesses account-linked private email,
and never scrapes anything not already visible to a logged-out visitor.

Recon summary (2026-08-26): same gql.twitch.tv/gql endpoint, same public
web Client-Id (kimne78kx3ncx6brgo4mv6wki5h1ko), same zero-WAF finding as
the sibling `twitch-channel-scraper`/`twitch-analytics-scraper` actors in
this portfolio.

Key discovery: `user.description` (bio) is the primary source (confirmed
live -- e.g. a real sampled channel's description literally reads "...
Business inquiries: <redacted>@wmeagency.com"). Panel *content*
(title/description/linkURL/imageURL) is NOT queryable as a bare field on
`Panel` -- `Panel` is a GraphQL interface with two concrete types,
`DefaultPanel` and `ExtensionPanel` (confirmed via `__typename`); content
fields only resolve through an inline fragment `... on DefaultPanel {
title description linkURL imageURL }`. `ExtensionPanel` (interactive
third-party widgets, not text) has no content fields to extract and is
skipped. `panels` itself is a plain array, not a paginated connection --
no cursor/pageInfo, no integrity-wall risk, a single call returns
everything.

Legacy REST endpoints that used to serve panel content directly
(`api.twitch.tv/api/channels/<x>/panels`, `.../kraken/channels/<x>/panels`,
`.../v5/channels/<x>/panels`) are all confirmed dead (404) -- GQL is the
only live path. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

GQL_URL = "https://gql.twitch.tv/gql"
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

DEFAULT_HEADERS = {
    "Client-Id": CLIENT_ID,
    "Content-Type": "text/plain;charset=UTF-8",
}

# Same confirmed hard ceiling as twitch-analytics-scraper's `streams`/
# `game.streams` connections -- used by "by-game" mode's discovery step.
MAX_FIRST_STREAMS = 30

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
