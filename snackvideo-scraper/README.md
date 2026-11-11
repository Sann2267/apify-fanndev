# SnackVideo Scraper - Profiles, Videos, Hashtags, Search & Trending

Scrape public data from [SnackVideo](https://www.snackvideo.com) with **no login and no account**. One actor, six modes:

| Mode | Input | What you get |
|---|---|---|
| **Profile** | usernames or profile URLs | Creator stats (followers, following, video count) + **every** video, newest first + their playlists |
| **Video** | video URLs, share links or IDs | Full details for each video |
| **Hashtag** | hashtags | Every video under a hashtag - the most complete way to collect a topic (thousands per hashtag) |
| **Search** | keywords | Videos SnackVideo recommends for the keyword (see note below) |
| **Trending** | nothing | The For You feed for the proxy's country |
| **Playlist** | playlist URLs or IDs | Playlist info + every video in it |

Every video includes views, likes, comments, shares, caption, hashtags, upload time, duration, creator, music, a direct MP4 URL and a cover image.

## Input example

```json
{
  "mode": "profile",
  "usernames": ["https://www.snackvideo.com/@AgathisDammaraa41198"],
  "maxItems": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

## Output example (one video)

```json
{
  "_input": "5256413826759439232",
  "_source": "S1-api-slides",
  "_scrapedAt": "2026-09-24T19:07:33Z",
  "recordType": "VIDEO",
  "id": "5256413826759439232",
  "videoUrl": "https://www.snackvideo.com/@AgathisDammaraa41198/video/5256413826759439232",
  "profileUrl": "https://www.snackvideo.com/@AgathisDammaraa41198",
  "captionText": "KALAU MAU LIHAT laki2 yang SUKSES LIHATLAH DARI isterinya゚##donggggggg",
  "createdAt": "2026-09-21T22:11:04Z",
  "hashtags": ["donggggggg"],
  "durationMs": 24838,
  "playUrl": "https://aws-br-cdn.kwai.net/upic/2026/09/22/06/BMjAy...mp4?tag=...",
  "coverUrl": "https://aws-br-pic.kwai.net/upic/2026/09/22/06/BMjAy...webp",
  "view_count": 16099,
  "like_count": 297,
  "comment_count": 19,
  "forward_count": 266,
  "kwai_id": "AgathisDammaraa41198",
  "user_name": "Agathis Dammara",
  "photo_id_str": "5256413826759439232",
  "... 40 more SnackVideo fields": "music, ext_params, headurls, main_mv_urls, ..."
}
```

`recordType` is `VIDEO`, `PROFILE`, `PLAYLIST` or `ERROR`. An input that can't be scraped (deleted video, unknown user, empty hashtag) produces an `ERROR` row with `_error` = `not_found` / `no_results` / `invalid_input` instead of being dropped silently.

## Good to know

- **Search is a recommendation feed, not an exact search.** SnackVideo returns different videos for the same keyword on every call, and only some of them mention it (it returns videos even for nonsense words). Each search result has `keywordMatched`; switch on **Only keyword matches** to keep just those. For complete, repeatable results on a topic, use **Hashtag** mode.
- **Proxy country = content region.** Trending and Search follow the country of the IP (Indonesia, Pakistan, India, Bangladesh...). Set the proxy country to choose. SnackVideo doesn't block direct requests, so the proxy is about region, not access.
- **Comments are not available.** SnackVideo returns an empty comment list to anyone who isn't logged in, so this actor gives `comment_count` but not comment text.
- **Playlists:** SnackVideo lists up to 20 playlists per creator.
- **Profile video count:** the feed can end a few videos short of `publicVideos` (e.g. 60 of 64); that's all SnackVideo serves.
- `playUrl` and other media URLs are signed and expire after a few days, so download media soon after scraping.
- Use `photo_id_str` / `id` rather than `photo_id`. It is a 64-bit number that spreadsheets and JavaScript round off.

## How it works (technical)

SnackVideo (Kuaishou's international app) is a Nuxt site backed by a JSON API on the same domain (`/rest/o/w/...`). Recon on 2026-09-25 found no WAF (Tengine origin, no Cloudflare/Akamai/DataDome) and no request signing: plain HTTP returns 200. The actor still sends browser-grade TLS (curl_cffi `chrome124`, rotating to `safari17_0` / `firefox133` / `chrome99_android` on any 403 or challenge page), retries with exponential backoff and jitter, and switches to a new proxy IP on transport errors or HTTP 429.
