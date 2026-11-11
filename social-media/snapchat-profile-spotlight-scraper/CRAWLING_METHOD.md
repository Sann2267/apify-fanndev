# Crawling method - snapchat.com

Recon date: **2026-09-18**. All findings below were verified live, from a
residential Indonesian IP, with no proxy, no cookie and no login.

## Surface map

| Surface | URL | Result |
|---|---|---|
| Profile | `https://www.snapchat.com/add/<user>` | 200, redirects to `/@<user>`. 136 KB (mkbhd) - 1.4 MB (netflix). Full SSR payload. |
| Profile (alt form) | `https://www.snapchat.com/@<user>` | 200, byte-equivalent payload. |
| Spotlight hub | `https://www.snapchat.com/spotlight` | 200, 324 KB, 24-25 stories in `spotlightFeed.spotlightStories`. |
| Lens hub | `https://www.snapchat.com/lens` | 200, 178 KB, `topLenses` (25) + `categories` (7). |
| Discover hub | `https://www.snapchat.com/discover` | 200, 232 KB, but the payload is an Apollo cache of `Snap:` entities with **empty media URLs** - no usable show/publisher data. Not implemented. |
| Unknown username | `/add/<garbage>` | **404**, 6 KB. Clean not-found signal. |

**No WAF was observed.** No Cloudflare challenge, no captcha, no `cf-mitigated`
header, no bot cookie, on any of the ~40 requests made during recon. `chrome124`
is used per the repo default (`chrome131` is widely blocklisted in 2026), not
because Snapchat demanded a particular fingerprint.

## Extraction layer

Everything comes from `<script id="__NEXT_DATA__" type="application/json">` -
tier 3 of the preference ladder in `.ai/CLAUDE.md` (JSON-LD > `__NEXT_DATA__` >
Apollo > HTML). There is no JSON-LD block carrying profile stats, so this is the
highest available tier.

`props.pageProps` for a profile carries **all of these in one response**:

| Key | Contents |
|---|---|
| `userProfile.publicProfileInfo` | username, title, bio, websiteUrl, subscriberCount, badge, category/subcategory string IDs, images, `relatedAccountsInfo` |
| `spotlightStoryMetadata[]` | per-video stats: `viewCount`, `shareCount`, `durationMs`, `uploadDateMs`, `contentUrl`, `contextCards` |
| `spotlightHighlights[]` | the same posts' media: `snapList`, `storyId`, `highlightId` |
| `curatedHighlights[]` | Stories/highlights with every snap's media URL and timestamp |
| `lenses[]` | AR lenses published by the account |
| `story` | the live Story, when one is running |

That is why `profile`, `spotlight`, `highlights` and `lenses` are **one request
per username** between them.

## Gotchas found (and handled in code)

1. **`_next/data/<buildId>/at/@user.json` returns 404.** The page exposes
   `curatedHighlightsCursor`, `spotlightHighlightsCursor` and `lensCursor`, but
   the Next.js data route that would consume them is not reachable publicly.
   Deeper pagination is therefore **not available** - documented as a limit in
   the README instead of faked. Any future attempt should start by looking for
   a POST API behind the Lens hub's "load more".
2. **Locale follows the exit IP, not `Accept-Language`.** Sending
   `Accept-Language: en-US` still produced `locale: id-ID` from an Indonesian IP.
   The only lever that works is the query parameter `?locale=en-US`. The path
   form `/en-US/add/<user>` returns **404**.
3. **Some scalars are boxed as `{"value": ...}` and some are not** - on the same
   object. `storyTitle` is boxed, `storySubtitle` is bare. A boxed value reaching
   the dataset as a dict where the schema says string is exactly the failure that
   broke three Actors in this repo at push time, so `extractor.normalize_record`
   unwraps every top-level field as a final pass.
4. **`subscriberCount: "0"` is a real answer, not a missing value.** Netflix
   publishes 0 while NASA publishes 758800. It is never coerced to null.
5. **Counts are strings** (`"758800"`, `"24931"`). Parsed to int in the friendly
   field; the original stays in `_raw`.
6. **Tagged unions.** `userProfile` has a `$case` key naming which member is
   populated (`publicProfileInfo`), and `videoMetadata.creator` does the same
   (`personCreator`). Reading `$case` rather than hardcoding the key means a
   business-profile variant still resolves.
7. **Hub pages have their own `buildId`s** (profile, spotlight and lens hubs
   returned three different ones on the same day). `buildId` is therefore
   recorded per record as `_buildId`, which makes shape drift diagnosable from
   the dataset alone.

## Verified numbers (2026-09-18)

| Account | Bytes | Subscribers | Spotlight | Highlights | Lenses | Related |
|---|---:|---:|---:|---:|---:|---:|
| `nasa` | 660 KB | 758,800 | 7 | 10 | 3 | 3 |
| `mkbhd` | 136 KB | 208,500 | 0 | 1 | 0 | - |
| `kyliejenner` | 1.31 MB | 29,389,100 | 24 | 18 | 1 | - |
| `netflix` | 1.42 MB | 0 (hidden) | 30 | 19 | 16 | 0 |

## What was rejected

- **Discover hub** - the Apollo cache ships entities with blank `mediaUrl`, so
  there is no data worth a mode.
- **Comment data** - `encodedSpotlightComments` (139 KB on the NASA page) is an
  encoded blob, not JSON. Not decoded; not worth the fragility for this release.
- **Browser automation** - never needed. Every surface answers plain HTTP.
