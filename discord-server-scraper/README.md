# Discord Server & Community Scraper

Nine Discord extractors in one actor. No login, no bot token, no self-botting —
everything here is data Discord serves to an anonymous visitor.

Find servers across Discord's ~53,000-server public directory, pull a
community's full profile including its outbound social links, resolve **any**
invite link to live member and online counts, see who is online and in voice
right now, snapshot servers on a schedule to chart their growth, and read
Discord's weekly trending-games chart with week-on-week movement.

---

## What this actor does and does not do

**It does not read messages.** Message history, ticket transcripts, member
rosters and DMs all require a bot token that has been invited to the server, or
a user token — and a user token is self-botting, which Discord bans accounts
for. This actor asks for neither, so there is nothing to leak and no account to
lose.

**What it reads instead** is the public layer, which turns out to be the
commercially useful part: which communities exist, how big they are, how alive
they are, who runs them and where else they publish.

| You want | Use |
|---|---|
| Find Discord communities in a niche | `discoverySearch` |
| Everything in a whole category | `discoveryCategory` |
| A community's social links and long description | `serverProfile` |
| Live member/online counts for a link you already have | `inviteLookup` |
| Who is online and in voice right now | `serverWidget` |
| Track the same servers week after week | `serverSnapshot` |
| Which games are surging on Discord | `trendingGames` |
| One game in depth | `gameProfile` |
| Public metadata for a bot or app | `botProfile` |

---

## The number that matters: `engagementRatePct`

Every server-shaped record carries `engagementRatePct` — online members as a
percentage of total members. It is on every row because it is the one figure
that separates a real community from a vanity number:

* **150,000 members, 400 online (0.3%)** — a shell. Bought, botted, or dead.
* **9,000 members, 2,000 online (22%)** — worth an outreach email.

Discord's own directory sorts by size, so the biggest servers surface first and
the engaged ones do not. Sorting your dataset by `engagementRatePct` instead is
usually the whole job.

---

## Modes

### `discoverySearch` — find servers by keyword

Searches Discord's public Server Discovery directory. Matches server names,
descriptions and the keywords owners tag their communities with.

```json
{
  "mode": "discoverySearch",
  "searchKeywords": ["crypto", "indie game dev", "spanish learning"],
  "maxPagesPerTarget": 10,
  "maxItems": 500
}
```

Discord serves **12 servers per request** and ignores any page size you ask
for, so `maxPagesPerTarget: 10` is up to 120 servers per keyword.

This is also how you reach the ~45 categories that have no browsable page —
Cryptocurrency, Finance, Anime & Manga, Memes, Esports and the rest exist only
as tags on server records.

### `discoveryCategory` — browse a whole category

Discord publishes a browsable page for exactly **five** categories:
`gaming`, `music`, `entertainment`, `science & tech`, `education`.
Anything else is a 404 on Discord's side; the actor tells you so up front
rather than collecting error rows.

```json
{ "mode": "discoveryCategory", "categories": ["science & tech"], "maxPagesPerTarget": 20 }
```

### `serverProfile` — the lead-generation mode

A discoverable server's full public page. Adds four things the search index
does not carry:

* `about` — the long-form description the owner wrote
* `socialLinks` — **the community's own GitHub, X, Patreon and YouTube URLs**
* `website`
* `reasonsToJoin` and the real `created_at`

```json
{ "mode": "serverProfile", "serverTargets": ["https://discord.gg/python"] }
```

### `inviteLookup` — the universal resolver

The only mode that reaches servers which never joined Server Discovery, which
is the overwhelming majority of Discord. Give it any invite — a vanity
(`discord.gg/python`) or a random code (`discord.gg/B9qbPSzX`) — and get live
counts, boosts and boost tier, verification level, the server tag, the landing
channel and who created the invite.

```json
{ "mode": "inviteLookup", "inviteCodes": ["https://discord.gg/python", "B9qbPSzX"] }
```

`expiresAt: null` means the invite never expires. That is not a missing value.

### `serverWidget` — live activity

Up to 100 people currently online, their status, and which voice channel they
are in — plus the voice channel list and a freshly minted invite.

Only works when the owner has switched the widget on under
**Server Settings → Widget**. Most have not; the actor reports
`widget_disabled` rather than failing.

**Discord anonymises these members itself.** The `id` field in its response is
a position in that response ("0", "1", "2"…), never a user ID, so the actor
publishes it as `positionInResponse`. These rows cannot be joined across runs,
and that is Discord's design, not a limitation of the scraper.

### `serverSnapshot` — growth tracking

One comparable row per server per run. Point it at a list of servers, run it on
an Apify schedule, and the dataset accumulates membership, online count and
boost history with no diffing on your side.

```json
{
  "mode": "serverSnapshot",
  "serverTargets": [
    "https://discord.gg/python",
    "https://discord.gg/midjourney",
    "267624335836053506"
  ]
}
```

It combines all three open surfaces and records which of them answered in
`sources`. Invite and Discovery counts are kept side by side
(`memberCount` vs `discoveryMemberCount`) because Discord computes them on
different schedules — in testing the same server reported 431,648 members via
its invite and 431,638 via its Discovery page, seconds apart.

### `trendingGames` — the weekly chart

Rank, week-on-week player change, 7-day streaming-activity delta, how many
weeks a title has been trending, and each game's official Discord server with
its own counts.

```json
{ "mode": "trendingGames", "weeksOfHistory": 12, "gameCategory": "survival" }
```

History walks backwards by following the previous-week link inside each chart.
That matters: Discord answers a date it has no chart for with the **current**
chart rather than a 404, so stepping dates by seven would quietly refill your
dataset with duplicates. The actor checks every response against the week it
asked for.

### `gameProfile` and `botProfile`

`gameProfile` takes the `gameUrl` that `trendingGames` emits and returns
genres, platforms, publisher, developer, release date, Discord's own 30-day
popularity rank, and the game's official links (site, X, YouTube, Reddit,
Twitch).

`botProfile` takes any application ID — or any URL containing one — and
returns the app's public metadata: tags, verification and monetization status,
whether the bot is public, its install scopes and permissions, and its terms
and privacy URLs.

---

## Input

Every mode accepts whatever form you happen to have. For servers, all of these
resolve to the same place:

```
https://discord.gg/python
https://discord.com/invite/B9qbPSzX
https://discord.com/servers/python-267624335836053506
https://discord.com/servers/267624335836053506
267624335836053506
python
```

There is also a generic `targets` array that gets routed into whichever list
the selected mode needs, so this actor can be driven from another actor or a
scheduler with one field regardless of mode.

One asymmetry worth knowing: **a bare guild ID only resolves if the server is
in Discovery or publishes a widget.** An invite code always resolves. Discord
offers no ID-to-invite lookup, so when in doubt supply the invite.

## Speed, cost and proxies

| Setting | Default | Why |
|---|---|---|
| `requestDelaySecs` | 2 | Directory pages allow ~6 requests back to back per IP, then HTTP 429 with no `Retry-After`. 2s was measured clean over 16 consecutive requests. |
| `apiRequestDelaySecs` | 0.4 | Discord's JSON API is far more permissive — a 25-request burst drew no throttling at all. |
| `maxItems` | 200 | Your main cost control. |

**A proxy is optional here, which is unusual.** Discord served every surface
this actor uses to a plain datacentre address during testing. A proxy buys
rate-limit headroom, not access, so a long Discovery walk finishes sooner
behind rotating addresses — and `DATACENTER` is enough. You do not need
residential.

## Output

Every record shares one envelope, so a single dataset can hold servers,
invites, widgets, games, bots and diagnostics and still be joined on `id`
(the guild ID for everything server-shaped):

```json
{
  "item_type": "server_snapshot",
  "id": "267624335836053506",
  "data": {
    "name": "Python",
    "memberCount": 431648,
    "onlineCount": 34152,
    "engagementRatePct": 7.91,
    "boostCount": 28,
    "socialLinks": ["https://github.com/python-discord/", "https://twitter.com/PythonDiscord"],
    "createdAt": "2017-01-08T12:03:33+00:00",
    "sources": ["invite", "discovery", "widget"]
  },
  "metadata": { "scrapedAt": "2026-09-21T11:20:03+00:00", "mode": "serverSnapshot", "sourceUrl": "..." }
}
```

Icon, banner and splash fields arrive as ready-to-use CDN URLs rather than the
raw hashes Discord's API returns, animated assets included. `createdAt` is on
every record — published outright on profile pages, and decoded from the guild
ID's own timestamp bits everywhere else.

**The run never finishes with an empty dataset.** Anything that fails produces
an `error` row naming the input and the reason (`not_found`,
`not_in_discovery`, `widget_disabled`, `week_not_published`, …), so a
downstream join can tell "nothing matched" apart from "the run crashed".

## Limitations, stated plainly

* **No messages, members or transcripts.** See the top of this README.
* **Member counts are approximate.** Discord labels them
  `approximate_member_count`; for very large servers they are rounded.
* **Discovery only lists servers that opted in** — around 53,000 of them. Most
  Discord servers are not in it. `inviteLookup` is the way to reach the rest.
* **Widget data is opt-in and anonymised**, and capped at 100 members
  (`memberListTruncated` tells you when you hit the cap).
* **`nbHits` drifts.** Discord's index is live; the reported total changed by
  several hundred between consecutive requests during testing, so the actor
  never uses it as a loop bound and neither should you.
