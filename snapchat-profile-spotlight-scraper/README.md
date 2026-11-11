# Snapchat Scraper - Profiles, Spotlight Videos, Stories & Lenses

Extract public Snapchat data without an account: profile stats (subscribers, bio, website, category, verified badge), every Spotlight video with its **view count**, Stories and highlights with direct media links, the AR **lenses** a brand or creator publishes, plus the public Spotlight feed and the Lens chart.

Snapchat is the social platform most missing from marketing datasets, because it has no public API. This Actor reads the same public pages anyone can open in a browser and turns them into clean rows.

## Why use this actor

- **No login, no API key, no cookies.** Nothing to configure before your first run.
- **Real view counts** on Spotlight videos - the number Snapchat publishes on the post itself.
- **Eight modes in one Actor**, so profile research, content analysis, lens tracking and discovery all share one input format and one dataset schema.
- **Account discovery built in.** The `related` mode walks Snapchat's own "related accounts" links, turning one seed handle into a list of accounts in the same niche.
- **Nothing fails silently.** An unknown username returns a clear `not_found` row; an account with no Spotlight returns an explicit `empty_section` row instead of an empty dataset you have to debug.
- **Stable output.** Named fields for the things you filter on, plus the untouched original object in `_raw` so nothing is lost when Snapchat changes something.

## How it works

1. You give the Actor one or more Snapchat usernames - `nasa`, `@nasa` or `https://www.snapchat.com/add/nasa` all work.
2. The Actor opens each public profile page and reads everything it publishes: profile details, Spotlight videos, Stories/highlights, lenses and related accounts.
3. The mode you picked decides which of those becomes rows. Because it all arrives together, each username costs a single page load.
4. Results stream into your dataset as they arrive, ready to download as JSON, CSV or Excel, or to pull through the API.

You never manage browsers, sessions or retries - the Actor retries transient failures itself.

## Input

```json
{
    "mode": "profile",
    "usernames": ["nasa", "netflix"],
    "locale": "en-US",
    "maxItems": 200,
    "maxConcurrency": 4
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | Which data to return. See the table below. Default `"profile"`. |
| `username` | string | A single username or profile URL. |
| `usernames` | array | Several usernames or profile URLs in one run. |
| `relatedDepth` | integer | `related` mode only. `0` = seeds only, `1` = seeds + accounts Snapchat links as related, up to `3`. Default `1`. |
| `locale` | string | Language for Snapchat's own labels. Default `"en-US"`. Without it Snapchat follows the server's location, so output language would change with the run's region. |
| `maxItems` | integer | Maximum rows for the whole run. Default `200`. |
| `maxConcurrency` | integer | How many usernames to process in parallel. Default `4`. |
| `proxyConfiguration` | object | Optional. Not required - every test ran cleanly without a proxy. |

### Modes

| Mode | Needs a username | Returns |
|---|---|---|
| `profile` | yes | One row per account: subscribers, bio, website, category, badge, counts, related accounts. |
| `spotlight` | yes | One row per Spotlight video: view count, duration, upload time, video and thumbnail URLs. |
| `highlights` | yes | One row per Story/highlight, with every snap's media URL and timestamp. |
| `lenses` | yes | One row per AR lens the account publishes, with preview video and unlock link. |
| `related` | yes | Full profile rows for the accounts Snapchat links as related, expanded level by level. |
| `trending` | no | The public Spotlight feed - what Snapchat is showing right now, with view counts. |
| `top-lenses` | no | The Lens hub chart, with the lens category it was read from. |
| `reference` | no | A live check of which public surfaces are answering, with the counts measured. |

### Example inputs

Audit two brand accounts:

```json
{ "mode": "profile", "usernames": ["netflix", "nasa"] }
```

Pull one account's Spotlight performance:

```json
{ "mode": "spotlight", "username": "nasa", "maxItems": 100 }
```

Discover accounts in a niche, two hops out from a seed:

```json
{ "mode": "related", "username": "nasa", "relatedDepth": 2, "maxItems": 60 }
```

Track what is trending on Spotlight, on a schedule:

```json
{ "mode": "trending", "maxItems": 25 }
```

## Output

Every row carries `_input`, `_source`, `_scrapedAt` and `recordType`, so several modes can share one dataset and still be split cleanly.

### `PROFILE` (profile and related modes)

```json
{
    "_input": "nasa",
    "_source": "S1-next-data",
    "_scrapedAt": "2026-09-17T18:25:11Z",
    "recordType": "PROFILE",
    "username": "nasa",
    "displayName": "NASA",
    "profileUrl": "https://www.snapchat.com/@nasa",
    "bio": "Explore the universe and discover our home planet with official NASA snaps.",
    "websiteUrl": "https://www.nasa.gov",
    "subscriberCount": 758800,
    "badgeName": "official",
    "isVerified": true,
    "category": "business group",
    "subcategory": "government org",
    "hasStory": false,
    "hasCuratedHighlights": true,
    "hasSpotlightHighlights": true,
    "lensCount": 3,
    "curatedHighlightCount": 10,
    "spotlightCount": 7,
    "relatedAccountCount": 3,
    "relatedAccounts": [
        { "username": "whitehouse", "title": "The White House", "badge": 1, "profileUrl": "https://www.snapchat.com/@whitehouse" },
        { "username": "ilikerockets", "title": "Destin Smarter Every Day", "badge": 0, "profileUrl": "https://www.snapchat.com/@ilikerockets" }
    ]
}
```

| Field | Type | Description |
|---|---|---|
| `username` / `displayName` | string | Handle and the name shown on the profile. |
| `subscriberCount` | integer | Subscribers. Snapchat publishes `0` for accounts that hide the number - that is a real answer, not a missing value. |
| `isVerified` / `badgeName` | boolean / string | Official badge status. |
| `category` / `subcategory` | string | Snapchat's own classification, e.g. `business group` / `government org`. |
| `bio` / `websiteUrl` / `address` | string | Profile text, outbound link and address where published. |
| `lensCount`, `curatedHighlightCount`, `spotlightCount` | integer | How much content the profile is currently publishing. |
| `relatedAccounts` | array | Accounts Snapchat links from this profile - feed them into `related` mode. |
| `relatedDepth` | integer | How many hops from your seed (`related` mode). |

### `SPOTLIGHT_VIDEO` (spotlight mode)

```json
{
    "recordType": "SPOTLIGHT_VIDEO",
    "username": "nasa",
    "spotlightIndex": 0,
    "storyId": "W7_EDlXWTBiXAEEniNoMPwAAYeG9xcGd0ZWd3AZ14BVv0AZ14BQkrAAAAAQ",
    "title": "Spotlight Snap",
    "description": "Another Spotlight Snap brought to you by Snapchat",
    "viewCount": 24931,
    "shareCount": 0,
    "durationMs": 87330,
    "width": 540,
    "height": 960,
    "uploadedAt": "2026-04-10T15:31:29Z",
    "videoUrl": "https://cf-st.sc-cdn.net/d/1z1p5kZtkBheBrRMCmyGi.27...",
    "thumbnailUrl": "https://cf-st.sc-cdn.net/d/1z1p5kZtkBheBrRMCmyGi.256...",
    "creatorUsername": "nasa",
    "creatorName": "NASA",
    "contextCards": [
        { "contextType": 2, "title": "Original Sound", "subtitle": "nasa", "id": "109480625804" },
        { "contextType": 3, "title": "NASA", "subtitle": "nasa", "url": "https://www.snapchat.com/@nasa" }
    ]
}
```

| Field | Type | Description |
|---|---|---|
| `viewCount` | integer | Views as published on the post. |
| `shareCount` | integer | Shares as published on the post. |
| `durationMs`, `width`, `height` | integer | Video length in milliseconds and pixel dimensions. |
| `uploadedAt` | string | UTC upload time. |
| `videoUrl` / `thumbnailUrl` | string | Direct media links. They are signed and expire - download soon after the run. |
| `hashtags`, `keywords` | array | Tags attached to the post. |
| `contextCards` | array | Attribution shown on the post: original sound, creator, lens used. |

### `HIGHLIGHT` (highlights mode)

```json
{
    "recordType": "HIGHLIGHT",
    "username": "nasa",
    "highlightKind": "curated",
    "storyTypeName": "CURATED_HIGHLIGHT",
    "title": "Moon Joy",
    "highlightId": "ddf02468-ae16-4fc6-b1bc-bde7e1e22218",
    "snapCount": 9,
    "firstSnapAt": "2026-04-10T15:32:54Z",
    "snaps": [
        { "snapIndex": 0, "mediaType": 1, "mediaUrl": "https://cf-st.sc-cdn.net/d/wAUDrJs74QBAl504N3DhT.1322...", "timestamp": "2026-04-10T15:32:54Z" },
        { "snapIndex": 1, "mediaType": 1, "mediaUrl": "https://cf-st.sc-cdn.net/d/h2ao1JvA4lER8PICU97Gc.1322...", "timestamp": "2026-04-10T15:32:54Z" },
        "... 7 more"
    ]
}
```

| Field | Type | Description |
|---|---|---|
| `highlightKind` | string | `curated`, `spotlight` or `live-story` (a Story that was live at scrape time). |
| `title` / `subtitle` / `emoji` | string | Labels the account gave the highlight. |
| `snapCount` / `firstSnapAt` | integer / string | How many snaps, and when the earliest was posted. |
| `snaps` | array | Each snap: index, media type, media URL, preview URL, timestamp. |

### `LENS` (lenses and top-lenses modes)

```json
{
    "recordType": "LENS",
    "lensName": "Avatar State",
    "creatorDisplayName": "Netflix",
    "isOfficialSnapLens": false,
    "previewVideoUrl": "https://community-lens.storage.googleapis.com/preview-media/final/61819e93...mp4",
    "unlockUrl": "https://www.snapchat.com/unlock/?type=SNAPCODE&uuid=e1d8b5e913a94978bb9db82d64323ec2",
    "lastUpdatedEpoch": 1777424813
}
```

| Field | Type | Description |
|---|---|---|
| `lensName` / `lensId` | string | Lens name and Snapchat's identifier. |
| `creatorUsername` / `creatorDisplayName` | string | Who published the lens. |
| `isOfficialSnapLens` | boolean | True for lenses made by Snap itself rather than a brand or community creator. |
| `category` | string | Which Lens hub chart the row came from (`top-lenses` mode): For You, Trending, Face, World, Music, Creators, Web Live. |
| `previewImageUrl` / `previewVideoUrl` / `unlockUrl` | string | Preview media and the link that opens the lens in the app. |

### `TRENDING_SPOTLIGHT` (trending mode)

```json
{
    "recordType": "TRENDING_SPOTLIGHT",
    "feedIndex": 0,
    "title": "Spotlight Snap",
    "viewCount": 741728,
    "durationMs": 14030,
    "uploadedAt": "2025-11-18T16:47:57Z",
    "creatorUsername": "nninajwa",
    "creatorName": "manje",
    "creatorUrl": "https://www.snapchat.com/@nninajwa",
    "videoUrl": "https://bolt-gcdn.sc-cdn.net/v/vdRYvL0ImK1i7hYHVgAWP.27..."
}
```

`feedIndex` is the position Snapchat served at scrape time - run it on a schedule to track how the feed moves.

### `SURFACE` (reference mode)

```json
{
    "recordType": "SURFACE",
    "surface": "lens-hub",
    "isAvailable": true,
    "detail": "payload parsed",
    "sample": { "topLenses": 25, "categories": ["FOR_YOU", "TRENDING", "FACE", "WORLD", "MUSIC", "CREATORS", "WEB_LIVE"] }
}
```

### Error rows

```json
{
    "recordType": "ERROR",
    "_input": "zzqqxx_not_a_real_user_123",
    "_error": "not_found",
    "_errorDetail": "Snapchat returned 404 for this username"
}
```

`_error` is one of `not_found`, `invalid_username`, `empty_section` (the account exists but publishes nothing of that kind) or `blocked_or_transient`.

## What you can build with it

- **Influencer vetting** - subscriber counts and Spotlight view counts side by side, so you can see reach *and* whether the audience actually watches.
- **Competitive content tracking** - schedule `spotlight` weekly per brand and chart view counts over time.
- **Niche account discovery** - `related` mode from three seed accounts gives you a ranked list of accounts in the same space.
- **AR lens benchmarking** - which brands ship lenses, how often they update them, and what is charting on the Lens hub.
- **Creative asset archives** - `highlights` returns direct media links for every snap in a Story.

## Notes & limits

- **Only public data.** Private accounts, friend stories, direct messages and anything behind a login are not accessible, and this Actor does not attempt them.
- **Media URLs expire.** Snapchat signs its CDN links; download the files soon after the run rather than storing the URLs long-term.
- **One page per username.** Snapchat publishes a fixed window of recent content per profile - typically up to 30 Spotlight videos and 20 highlights for large accounts. There is no public "load more" for profile pages, so a run returns that window, not the full lifetime archive.
- **Subscriber count can be `0`.** Some large accounts (Netflix, for example) choose not to publish it. The row is still complete; the number is genuinely hidden.
- **`creatorFollowerCount` is often 0** on Spotlight payloads - Snapchat leaves it blank there. Use the `profile` mode row for that account instead.
- **Lens IDs are empty on profile lenses.** Brand-published lenses arrive without a numeric ID; lenses from the Lens hub carry one.

## Scheduling tips

- `trending` and `top-lenses` change through the day - hourly or every few hours gives a usable time series.
- `profile` is the cheapest monitoring mode: one row per account per run.
- For large account lists, raise `maxConcurrency` to 8-10 and set `maxItems` high enough that later usernames are not cut off.

## Troubleshooting / FAQ

**A username returns `not_found`.** The handle does not exist or was renamed. Snapchat handles are lower-case and may contain dots, dashes and underscores; open `https://www.snapchat.com/add/<handle>` in a browser to confirm.

**`empty_section` for spotlight or lenses.** The account is real but publishes none of that content type. Check `spotlightCount` and `lensCount` on its `profile` row first - that tells you what is worth requesting.

**Output text is not English.** Set `locale` to `en-US` (the default). Snapchat otherwise follows the location of the machine running the scrape.

**Can I get more than the newest videos?** Not from the public pages - Snapchat does not expose older content there. Schedule the Actor instead and accumulate rows over time.

**Do I need a proxy?** No. Every mode was verified without one. Add one only if your runs are rate-limited or you want a specific country's view of the trending feed.

## Legal & fair use

This Actor collects only data that Snapchat publishes publicly, without logging in and without circumventing any access control. You are responsible for using the output in line with Snapchat's terms and with the privacy laws that apply to you - in particular, treat creator profiles as personal data where your jurisdiction says so.
