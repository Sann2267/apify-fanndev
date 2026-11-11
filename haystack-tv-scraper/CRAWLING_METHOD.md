# Crawling method — Haystack News (haystack.tv)

Recon date: **2026-09-14**. Everything below was measured, not assumed.

## 1. There is no WAF

haystack.tv fronts on **Heroku + Express** (`server: Heroku`, `x-powered-by: Express`).
No Cloudflare, no DataDome, no PerimeterX, no Akamai, no AWS WAF — no `cf-ray`,
no challenge body, no interstitial. The whole TLS ladder came back identical on
the same IP against the *authenticated* `/api/v1/playlist`:

| Client | `/api/v1/playlist?category=news` |
| --- | --- |
| `requests` (no impersonation at all) | `200` |
| `curl_cffi` chrome99_android | `200` |
| `curl_cffi` chrome124 | `200` |
| `curl_cffi` chrome131 | `200` |
| `curl_cffi` chrome136 | `200` |
| `curl_cffi` safari17_0 | `200` |
| `curl_cffi` edge101 | `200` |
| `curl_cffi` firefox133 | `200` |

**Do not rotate TLS profiles here.** `chrome124` is pinned purely for portfolio
consistency. A failure is upstream load, a bad parameter, or a missing header —
never a fingerprint. `robots.txt` blocks a long list of AI crawlers but sets
`User-agent: * → Allow: /` with only `/activate*` and `/signin*` disallowed;
every path this actor touches is in the allowed set.

## 2. The two real gates

Both are satisfiable without any login.

### 2a. Client-version headers

```
hs-client-version: 7.1
hs-client-os: web
```

Omit `hs-client-version` and `/api/v1/playlist` answers:

```json
400 {"errorTitle":"Please Upgrade","errorString":"...This version is no longer supported."}
```

`7.1` is the literal constant `Ca=7.1` in the live web bundle. When Haystack
retires it, `client.refresh_client_version()` walks `CLIENT_VERSION_LADDER` on
the first "Please Upgrade" body rather than dying. If the whole ladder is
rejected, `UpstreamVersionRetired` crashes the run on purpose — re-read
`Ca=` from the bundle and update `constants.CLIENT_VERSION`.

### 2b. Anonymous bearer token

```
Authorization: Bearer <hs_access_token>
```

`www.haystack.tv` hands this out **to every visitor in a `Set-Cookie` on any
page load** — no sign-in, no device registration:

```
hs_access_token=eyJ...; Max-Age=31536000; Path=/; Secure
hs_user_type=anonymous
```

The JWT decodes to `{"userid":"anon_<uuid>","roles":[],"isAnonymous":true,
"iat":...,"exp":...}` with a **one-year** expiry, and it is portable — a token
minted in one session works from a different session and a different exit IP.
One `GET https://www.haystack.tv/` per run is all the bootstrap needed.

Without the Bearer header, `/playlist`, `/search`, `/localEvents`, `/onboarding`,
`/hsChannels` and `/user/me` all return a bodyless `401`.

## 3. Endpoint map

Host: `https://api.haystack.tv` (the site itself is `https://www.haystack.tv`).

| Endpoint | Auth | Returns |
| --- | --- | --- |
| `GET /api/v1/playlist` | Bearer | The universal feed. 15–30 streams. |
| `GET /api/v1/search?type=&q=` | Bearer | Entity search: channels, locations, topics. |
| `GET /api/v1/localEvents?geo=<json>` | Bearer | Local events, 10 per call. |
| `GET /api/v1/channel` | **none** | 483-channel directory. |
| `GET /api/v1/sitemap` | **none** | 816 KB taxonomy: 36 categories, 9 video categories, 111 live channels, special streams, 100 poll slugs. |
| `GET /api/v1/suggest?type=city_or_zip&search=` | **none** | City lookup → slug + `lng_lat`. |
| `GET https://www.haystack.tv/polls/__data.json` | none | 78 polls with live vote counts. |
| `GET https://www.haystack.tv/sitemap.xml` | none | 299 `/location/<slug>` city slugs. |

Endpoints that stay `401` for an anonymous token and are **not** used:
`/api/v1/user/me`, `/api/v1/hsChannels`, `/api/v1/onboarding`, `/api/v1/userChannels`.

## 4. `firstVideo` is a universal resolver, not a cursor

This is the key finding. The site is SvelteKit and makes its API calls
server-side, so the client bundle carries no `/api/v1` paths — but it does carry
the param-builder (`Od`), which switches on an internal entity enum:

| Entity | Params sent to `/api/v1/playlist` |
| --- | --- |
| Category | `category=<name>` + `firstVideo=https://www.haystack.tv/<name>` |
| Channel | `category=channel/<name>` |
| Topic | `firstVideo=https://www.haystack.tv/tag/<tag>` |
| Location | `firstVideo=https://www.haystack.tv/location/<slug>` |
| Video (slug) | `firstVideo=https://www.haystack.tv/v/<slug>` |
| Video (id) | `firstVideo=https://www.haystack.tv/id/<id>` |
| Search | `search=<query>` |

So `firstVideo` takes **any haystack.tv URL** and the server works out which
feed it belongs to. `src/targets.py` is a direct port of that mapping — it is
why one code path serves six entity types.

**`firstVideo` does NOT paginate.** Verified: passing the last video id of a
page returns the *identical* 21 streams, four times in a row. Six repeated
identical calls also returned 0 new items. `page`, `limit`, `offset` and `skip`
are all ignored. Breadth comes from fanning out across targets (483 channels ×
299 cities × 36 categories), not from paging.

## 5. Two response traps

### 5a. Video detail is a different shape from the feed

Anchoring the playlist on a video (`firstVideo=.../v/<slug>`) makes `streams[0]`
the **full 51-field object** — the feed shape only carries ~27. The extra fields
are the valuable ones: `llm` (Haystack's own per-story classification:
category, contentType, urgency, editorialStance, primaryEmotion,
emotionalIntensity, broadAppeal, headlineMagnetism, narrativeResolution),
`views`, `exit_ratio`, `exit_users`, `total_users_for_exit`, `sourceUrl`,
`downloadUrl`, `cluster`, `haystackTags`, `videoTypeFlags`.

When the slug/id does not exist the API does **not** 404 — it silently returns a
generic feed. `run_video_detail` therefore verifies `streams[0]` actually matches
the requested id/slug and emits `_error: not_found` when it does not.

### 5b. Search never reports "no results"

A nonsense query returns ~20 clips like any other. It is not a fixed fallback
list — two different gibberish queries overlapped only 5/20, so it is fuzzy
ranking that degrades rather than emptying. `channelInfo.title` merely echoes the
query back (`"Search results for zzqqxx99nonsensequery"`), so it carries no
signal. Since the search is semantic, a literal-term miss is not proof of a bad
hit — so the actor measures and reports relevance (`SEARCH_SUMMARY` with
`termMatchRatio`, `_warning` when 0) instead of dropping rows.

## 6. Local events: premium cap and how far slicing gets

`/api/v1/localEvents?geo=<json>` needs the geo object as a **JSON string** —
every flat alternative (`location=`, `slug=`, `lat=`/`lon=`, `city=`/`region=`)
returns `{"events":[],"total":0}` with a 200. Build it from
`/api/v1/suggest?type=city_or_zip`, which maps a city name to `slug` and
`lng_lat`.

Anonymous callers get **10 events of `total`** (Houston reports 700,
`eventsHidden: 690`). The cap is server-side and cannot be paged past:
`page`, `limit`, `offset`, `skip`, `isSubscribed`, `premium` are all ignored.

Only two filters shift the result set:

| Param | Honoured? |
| --- | --- |
| `sort` = `diversified` / `date` / `distance` | **yes** — each returns a different 10 |
| `category` = one of 5 category ids | **yes** — singular `category`, *not* `categories` |
| `labels`, `label`, `categoryIds`, `cat`, `maxDistance`, `dateFilter` | no |

Slicing 3 sorts × 5 categories + 3 bare sorts + base = 19 calls, de-duplicated:
**107 unique events for Houston, 99 for San Francisco** — roughly 10× a single
call. Note `total` is scoped to the slice's own filter (`category=sports`
reports 46, unfiltered reports 700), so only unfiltered slices are used to
populate `eventsTotalUpstream`. The `LOCAL_EVENTS_SUMMARY` row reports the gap
and carries `_warning: premium_capped_partial_harvest`.

## 7. Polls come from the SvelteKit SSR payload

There is no public poll API. `www.haystack.tv/polls/__data.json` returns
SvelteKit's **flattened devalue** array — a flat list where every nested value is
an integer index back into the same list. Rather than implementing the full
devalue hydrator, `_polls_from_sveltekit` scans the flat array for objects
carrying both `question` and `choices` and dereferences only their own fields.
Shorter, and tolerant of SvelteKit layout changes. If the scan finds nothing it
raises `UnexpectedShape` rather than pushing an empty result.

## 8. Rate limiting

None observed. 19 sequential slices per city × 2 cities concurrently, plus
~100 playlist calls during recon, produced no 429 and no throttling. One
transient slice failure was seen under concurrency and did not reproduce
sequentially; the client's 5-attempt exponential backoff absorbs it and the
summary row reports `slicesFailed` with detail.

`maxConcurrency` defaults to 4 to stay a polite client, not because the service
pushes back.

## 9. Proxy

Not required. The default input is `useApifyProxy: false` and every test in this
document ran direct. `_maybe_proxy_url` only builds a `ProxyConfiguration` when
the user explicitly asks — calling `Actor.create_proxy_configuration`
unconditionally makes the SDK demand an Apify proxy password and kills runs that
never wanted a proxy.

A US exit IP is only useful for the bare `/` *My Headlines* target, which is
geo-personalised. The `geo` param on `/localEvents` is explicit, so local events
do **not** follow the exit IP.
