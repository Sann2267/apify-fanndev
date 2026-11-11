# Crawling Method — Twitch Email Finder

**Last verified:** 2026-08-26

## Scope and why this is a legitimate, separate actor

This actor extracts business/contact email addresses from exactly two
public fields on a Twitch channel: the channel bio (`user.description`)
and the "About" panels shown below the video player. Both are fields a
streamer fills in themselves, specifically visible to any logged-out
visitor, and very commonly used specifically to publish a contact email
for sponsorship/business inquiries (e.g. a real sampled channel's bio
literally reads "... Business inquiries: <redacted>@wmeagency.com").
This actor does not log in, does not access account-linked private
email, and does not scrape anything a human visitor to
`twitch.tv/<channel>/about` couldn't already read themselves.

It is kept as its own actor rather than a mode on `twitch-channel-scraper`
or `twitch-analytics-scraper` (both already in this portfolio) because
"email finder" is a distinct, separately-searched-for product category
on the Apify Store (buyers specifically search "Twitch email finder",
not "Twitch channel scraper") — matching this portfolio's established
precedent of keeping meaningfully-different-use-case Twitch data in
separate actors even when they share the same GQL client.

## WAF

Identical finding to the sibling Twitch actors: **none.** `gql.twitch.tv`
accepts `curl_cffi` `chrome124` with just the public web
`Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko` header.

## Real discovery: panel content requires GraphQL interface fragments

`user.panels` returns a plain array (not a paginated connection — no
cursor/pageInfo, confirmed by inspecting the shape) of `Panel` objects.
Querying any content field directly (`title`, `description`, `linkURL`,
`imageURL`) as a bare field on `Panel` fails with `"Cannot query field
X on type Panel"` — because **`Panel` is a GraphQL interface**, not a
concrete type. Confirmed via `__typename`: real channels' panels resolve
to either `DefaultPanel` (a text/image/link panel — what "About" panels
normally are) or `ExtensionPanel` (an embedded interactive third-party
widget, e.g. a donation tracker — no text content to extract, correctly
skipped). Content fields only resolve through an inline fragment:

```graphql
panels {
  id
  __typename
  ... on DefaultPanel { title description linkURL }
}
```

This is a different technique than anything needed in the sibling
`twitch-channel-scraper`/`twitch-analytics-scraper` actors, which never
needed to query an interface type.

Three legacy REST endpoints that historically served panel content
directly before the GQL migration were checked and confirmed dead (404):
`api.twitch.tv/api/channels/<x>/panels`, `.../kraken/channels/<x>/panels`,
`.../v5/channels/<x>/panels`. GQL with the interface fragment above is
the only live path.

## Both sources are necessary — confirmed empirically, not assumed

A live discovery-mode test run (`by-game`, "Just Chatting", top 10
channels) found a real business email (`blur@anc-network.com`) that
existed **only** in a panel's `description` field — that channel's
`user.description` (bio) field was unrelated flavor text with no email
at all. If this actor only scanned the bio (the more "obvious" source),
it would have silently missed a real, findable contact email. Both
`user.description` and every `DefaultPanel`'s `title`+`description` are
scanned on every lookup, and `emailSources` in the output records
exactly which field(s) each found email came from — for both
transparency and so a downstream consumer isn't left guessing which of
several possible emails (if a channel lists more than one) is the "main"
one.

## Extraction: standard + deliberately-obfuscated patterns

Two regex passes run against every text source:
1. A standard email pattern (`local-part@domain.tld`).
2. A common human-readable obfuscation pattern — `name (at) domain (dot)
   com`, `name [AT] domain [DOT] com`, `name AT domain DOT com`,
   case-insensitive — normalized back to a real address and validated
   against the standard pattern before being accepted. This is not a
   WAF/security bypass; it's unobfuscating text a streamer already chose
   to publish specifically so a reader (human or otherwise) could
   recover their real contact address while dodging the crudest
   spam-bot regexes. No sample channel in this actor's own recon
   happened to use this format, but it is common enough on Twitch/social
   bios generally that it's included proactively rather than added
   reactively after a user reports a miss.

Results across both patterns and both sources are deduplicated
(case-insensitive) into a single sorted `emails` list per channel.

## Data sources (all `S1-gql`, no fallback)

### 1. `channel` mode
`CHANNEL_EMAIL_QUERY` — one call per login: `description` + `panels`
(with the `DefaultPanel` inline fragment). A nonexistent login resolves
`user: null` (confirmed, no error) and is reported as
`_error: "channel_not_found"`.

### 2. `by-game` mode
Two-stage: `GAME_STREAMS_DISCOVERY_QUERY` first (same `game.streams`
connection and the same confirmed 30-item ceiling documented in
`twitch-analytics-scraper`'s CRAWLING_METHOD.md — reused here purely as
a discovery step, not exposed as its own output) to get the top N live
channels' logins in a category, then `channel` mode's own lookup for
each discovered login. A game with zero live channels (or a nonexistent
game name — `game: null`) returns a single
`_error: "game_not_found_or_empty"` record rather than an empty, silent
run.

## Known limits

- Only emails the channel owner has chosen to publish in their bio or
  About panels are found. A streamer with no public contact info simply
  returns `emailFound: false` — this is the honest, expected majority
  case (2 of 3 channels sampled directly, and most of a 10-channel
  `by-game` sample, had no email at all), not a bug.
- Emails inside a panel's linked-out destination page (e.g. a Linktree
  or personal website reachable via `linkURL`) are NOT followed or
  scraped — this actor extracts only Twitch's own data, not arbitrary
  third-party pages a panel happens to link to.
- `by-game` mode inherits the same 30-channel ceiling as
  `twitch-analytics-scraper`'s `game.streams` connection (Twitch's own
  device-integrity gate blocks deeper HTTP-only pagination) — it
  discovers the top 30 live channels in a category at most per run, not
  every channel that has ever streamed that game.

## Diff cadence

Quarterly smoke test recommended.
