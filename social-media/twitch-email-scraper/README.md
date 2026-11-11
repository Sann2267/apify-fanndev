# Twitch Email Finder

Extract publicly-published business contact emails from Twitch streamers' channel bio and About panels — no account or API key needed.

## Why use this actor

- Finds real contact emails streamers have already chosen to publish for sponsorship/business inquiries — nothing private, nothing guessed
- Checks **both** the channel bio and every About panel — a real test run found a business email that existed only in a panel, not the bio, confirming both sources matter
- Bulk mode: give it a game/category and it discovers the top live channels there for you, then checks each one — built for sponsorship-outreach list-building
- No account, login, or API key required
- Honest results: a channel with no public email returns `emailFound: false` rather than a guess or a fabricated value

## How it works

Pick a `mode`:
1. **`channel`** — check one or more specific channel logins.
2. **`by-game`** — discover the top live channels in a game/category, then check each one for a public email.

## Input

**Specific channels:**
```json
{ "mode": "channel", "logins": ["pokimane", "shroud"] }
```

**Top channels in a category:**
```json
{ "mode": "by-game", "gameName": "Just Chatting", "limit": 30 }
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"channel"` (default) or `"by-game"`. |
| `login` / `logins` | string / array | `channel` mode — channel login(s) to check. |
| `gameName` | string | `by-game` mode — exact game/category name as shown on Twitch. |
| `limit` | integer | `by-game` mode — how many top live channels to check. Max 30 (Twitch's own ceiling). |
| `maxConcurrency` | integer | How many channels to check in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per checked channel:
```json
{
  "_input": "pokimane",
  "_source": "S1-gql",
  "_scrapedAt": "2026-08-25T20:20:26Z",
  "login": "pokimane",
  "displayName": "pokimane",
  "emails": ["teampokimane@wmeagency.com"],
  "emailFound": true,
  "emailSources": [
    { "field": "description", "emails": ["teampokimane@wmeagency.com"] }
  ],
  "description": "hi ♡ i stream sometimes 📧 Business inquiries: teampokimane@wmeagency.com"
}
```

A channel with no public email:
```json
{
  "_input": "shroud",
  "_source": "S1-gql",
  "_scrapedAt": "2026-08-25T20:20:30Z",
  "login": "shroud",
  "displayName": "shroud",
  "emails": null,
  "emailFound": false,
  "emailSources": null,
  "description": "I'm back baby"
}
```

A record with `_error` instead means that lookup failed (`"_error": "channel_not_found"` for a login that doesn't exist, or `"_error": "game_not_found_or_empty"` for a category with no live channels in `by-game` mode).

## Known limits

- **Only finds what streamers have chosen to publish.** Most channels don't list a public email at all — that's the honest, common outcome (`emailFound: false`), not a failure of this actor.
- **Doesn't follow outbound links.** A panel's `linkURL` (e.g. a Linktree page) is not crawled — this actor only reads Twitch's own bio/panel text, not third-party destination pages.
- **`by-game` mode checks at most the top 30 live channels** in a category per run — Twitch's own platform enforces this ceiling for anonymous/HTTP-only access.

## A note on use

This actor surfaces email addresses that account holders have deliberately made public for the purpose of being contacted about business opportunities. Please use the results responsibly and in line with applicable anti-spam laws (e.g. CAN-SPAM, GDPR/PECR) in your jurisdiction and the recipient's.
