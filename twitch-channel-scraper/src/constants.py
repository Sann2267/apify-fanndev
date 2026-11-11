"""Endpoints, headers, enum whitelists -- all in one place.

Recon summary (2026-08-26): gql.twitch.tv/gql is Twitch's own internal
GraphQL endpoint, used by the twitch.tv web frontend itself for every
logged-out visitor. It has NO WAF challenge of any kind -- the only
"auth" it needs is the public web `Client-Id` header
(`kimne78kx3ncx6brgo4mv6wki5h1ko`), which is not a secret: it is shipped
in Twitch's own frontend JS bundle and used by every anonymous browser
tab. Full inline query text (not persisted-query sha256 hashes) is sent
directly in the POST body -- this sidesteps the hash-rotation problem
entirely (see .ai/skills/graphql-doc-id-rotation.md) since there is no
hash to rotate.

Real, confirmed limit (not a bug): single-page queries with `first` up to
100 work with zero friction. Requesting a SECOND page via the `after`
cursor on `videos`/`clips` triggers `IntegrityCheckFailed` -- a
device-attestation gate that an HTTP-only anonymous `Client-Integrity`
token (from `gql.twitch.tv/integrity`) cannot satisfy, even when bound to
a real `unique_id` cookie harvested from a real page load and a matching
`Client-Session-Id`. This is the same category of "genuinely
unreproducible without a JS VM" wall documented in .ai/lessons-learned.md
for Shopee/TikTok -- NOT chased with a browser here per project
constraints; the actor caps at 100 most-recent (or most-viewed) items per
connection and documents this honestly rather than silently truncating.
See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

GQL_URL = "https://gql.twitch.tv/gql"
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

DEFAULT_HEADERS = {
    "Client-Id": CLIENT_ID,
    "Content-Type": "text/plain;charset=UTF-8",
}

# Hard platform ceiling confirmed live: `first` > 100 returns a GraphQL
# validation error ("argument 'first' value must be between 1 and 100").
MAX_FIRST = 100

# Confirmed live via error-probing (gql.twitch.tv rejects unknown enum
# members with a generic "does not exist in <EnumName> enum" message that
# does not list valid values, so each of these was found by testing
# candidates one at a time -- see CRAWLING_METHOD.md).
VIDEO_SORT_VALUES = ["TIME", "VIEWS"]
VIDEO_TYPE_VALUES = ["ARCHIVE", "HIGHLIGHT", "UPLOAD", "PAST_PREMIERE", "PREMIERE_UPLOAD"]
CLIPS_PERIOD_VALUES = ["LAST_DAY", "LAST_WEEK", "LAST_MONTH", "ALL_TIME"]
CLIPS_SORT_VALUES = ["VIEWS_DESC", "TRENDING"]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
