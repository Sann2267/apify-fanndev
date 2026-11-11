# Crawling Method — Social Blade Creator Analytics Scraper

**Last verified:** 2026-09-08

## Target & why this one

`socialblade.com` — creator statistics for YouTube, TikTok, Twitch and
Instagram.

Babak 41 of `ACTOR_MARKET_RESEARCHER_NEW.md` listed this as candidate #2
and was explicit that the opening is **quality, not emptiness**:
`radeance/socialblade-api` has **352 users / 1,256,465 runs** (3,570
runs per user — the 8th-highest ratio in the entire high-stats pool) yet
sits at **2.5 out of 10** across its reviews, while the second-placed
seller has only 91 users. Demand is proven and recurring; the incumbent is
disliked.

Babak 41 also attached a condition: *Social Blade sells a paid API — verify
the logged-out public surface first.* That condition is satisfied here.
Everything this actor reads is what an anonymous visitor's own browser
receives in the page itself; no API key, no login, and no call to the paid
API is involved.

## Data source: server-rendered `__NEXT_DATA__`

Social Blade is Next.js (Pages Router) and hydrates a **tRPC query cache**
into `__NEXT_DATA__`. One plain GET therefore returns the whole record:

```
props.pageProps.trpcState.json.queries[] = {
  queryKey: [["youtube", "user"], {input: {...}, type: "query"}],
  state:    {data: {...}}
}
```

Per profile page the useful entries are:

| Query | Payload |
|---|---|
| `<platform>.user` | id, createdAt, displayName, avatar, country, channelType, socials, subscribers, videos, views, banner, madeForKids, description, **ranks**, identifiers |
| `<platform>.history` | up to 15 daily rows — YouTube `{date, subscribers, views, videos}`, TikTok `{date, followers, following, likes, videos}`, Twitch `{date, followers}` |

Extraction is a dictionary lookup by query name, not DOM scraping — markup
changes cannot break it. Queries whose `state.data` is `null`
(`auth.account.me`, `notice` for logged-out visitors) are skipped instead of
being emitted as empty records.

## Platform coverage (all verified live)

| Platform | `user` | `history` |
|---|---|---|
| YouTube | ✅ | ✅ 15 rows |
| TikTok | ✅ | ✅ 15 rows |
| Twitch | ✅ | ✅ 15 rows |
| Instagram | ✅ | ❌ none in the public payload |
| Facebook | ❌ | — |

Facebook was tested at `/facebook/page/<x>` and `/facebook/user/<x>`; both
returned **404** with no creator payload, so it is excluded from the input
enum rather than shipped as an option that always fails.

## Gotcha: the three YouTube URL shapes are NOT interchangeable

`/youtube/user/<h>`, `/youtube/c/<h>` and `/youtube/@<h>` are separate
namespaces. The first build normalised every input to `/user/<handle>`,
and `https://socialblade.com/youtube/@mrbeast` — MrBeast, **516M
subscribers** — silently resolved to `/youtube/user/mrbeast`, a different
channel with **2,100 subscribers** that merely shares the name.

That is the worst failure mode available here: a complete, plausible
record for the wrong creator, with no error to notice. The fix is that a
URL is fetched **verbatim** at the path given, and only a bare handle is
expanded (leading `@` → `/@<handle>`, otherwise `/user/<handle>`).
Verified after the fix: `/youtube/@mrbeast` → MrBeast, 516,000,000
subscribers, US.

## Leaderboard

`/youtube/top/100` returns a `youtube.top` payload with `creators`,
`nextCursor` and `processingTimeMs`.

Sizes are not free-form: `/youtube/top/100` and `/youtube/top/500` return
200, while `/youtube/top/50` and `/youtube/top/250` return **HTTP 400**.
Both valid sizes ship exactly **100 creators** in the server-rendered
payload — the remainder is paged client-side through `nextCursor` against
the API, which is out of scope, so the actor's honest cap is 100 per run
and the input enum offers only the two working sizes.

Leaderboards exist for YouTube only: `/tiktok/top/100` and
`/twitch/top/100` are 404.

## Anti-bot

Cloudflare fronts the domain but served **no challenge** to a `curl_cffi`
`chrome124` request across all four platforms and the leaderboard. No
cookie jar, no warmup, no login. Block detection stays wired so a future
challenge surfaces as an error rather than as a silently empty
`__NEXT_DATA__` parse.

`400` and `404` are treated as terminal (not retried): 404 is an unknown
creator, 400 is an unsupported leaderboard size.

## Known upstream quirks

- Audience counts on the profile record are **rounded** (109,000,000);
  the daily history rows carry finer values (110,000,000 / exact view
  counts). Both are emitted as published.
- `views` arrives as a **string** on some payloads and a number on others
  — passed through unchanged rather than coerced.
- Rank keys differ per platform (`subscribers`/`views`/`country`/`category`
  on YouTube; `followers`/`likes`/`videos` on TikTok; `followers` on
  Twitch; `followers`/`engagementRate` on Instagram), so `ranks` is passed
  through as an object instead of being flattened into fixed columns.
