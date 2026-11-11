# Platform method reference

Detail teknis per platform: endpoint, header wajib, signing/token strategy, library reference. Volatile field (`doc_id`, `queryId`) — selalu validasi ulang dari bundle live sebelum deploy.

> Plan asli ada di `C:\Users\asus\.claude\plans\kamu-adalah-seorang-senior-cached-panda.md` — file ini adalah versi yang ditrack di repo.

---

## Bluesky (atproto)

- **Host strategy**: `https://public.api.bsky.app/xrpc/<method>` untuk mayoritas; `https://api.bsky.app/xrpc/app.bsky.feed.searchPosts` (public proxy 403 untuk search).
- **Header**: `User-Agent` desktop Chrome, `Accept: application/json`. Tidak ada auth.
- **Endpoint inti**:
  - `app.bsky.actor.getProfile?actor=<handle_or_did>`
  - `app.bsky.feed.getAuthorFeed?actor=<>&limit=&cursor=&filter=`
  - `app.bsky.feed.getPostThread?uri=at://<did>/app.bsky.feed.post/<rkey>&depth=&parentHeight=`
  - `app.bsky.feed.searchPosts?q=&limit=&cursor=&sort=`
  - `com.atproto.identity.resolveHandle?handle=<>`
- **Rate**: ~300 req/min/IP di public.api, ~60 di api.bsky.app (lebih ketat). Datacenter proxy OK.
- **Status**: Tested ✅ (per Mei 2026).

## Telegram (web public)

- **Host**: `https://t.me/s/<channel>` (HTML server-rendered).
- **Pagination**: `?before=<msg_id>` query param.
- **Parse**: BeautifulSoup `.tgme_widget_message` blocks → `data-post`, `.tgme_widget_message_text`, `.tgme_widget_message_views`, `.tgme_widget_message_date time`.
- **Limit**: ~100 message terbaru per page. Tidak ada API key. Tidak ada anti-bot signifikan.

## YouTube (innertube)

- **Host**: `https://www.youtube.com/youtubei/v1/<endpoint>?prettyPrint=false`.
- **API key** (hardcoded di web client, valid 2026): `AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8`. ANDROID client pakai key beda — cek `yt-dlp/extractor/youtube.py`.
- **Body**:
  ```json
  {
    "context": {
      "client": {
        "clientName": "WEB",
        "clientVersion": "2.20260101.00.00",
        "hl": "en",
        "gl": "US",
        "visitorData": "<from /visitor_id or HTML>"
      }
    },
    "<endpoint-specific>": "..."
  }
  ```
- **Endpoint inti**:
  - `youtubei/v1/browse` — channel (`browseId=UCxxx`), playlist, trending
  - `youtubei/v1/player` — video metadata (gunakan `WEB_EMBEDDED_PLAYER` atau `IOS` client untuk avoid PO Token)
  - `youtubei/v1/next` — comments (chain continuation token dari `continuationItems[].continuationItemRenderer.continuationEndpoint.continuationCommand.token`)
  - `youtubei/v1/search` — search
- **PO Token**: TIDAK perlu untuk metadata/comments/search di 2026 — hanya untuk stream URL (`gvs`, out of scope).
- **Reference**: `yt-dlp` extractor source.
- **Status**: planned.

## Instagram (Meta)

- **Host**: `https://www.instagram.com/api/graphql` + `https://www.instagram.com/{username}/`.
- **Pipeline per request batch**:
  1. GET HTML profile → regex extract `"LSD",[],{"token":"(\w+)"` → lsd token
  2. Set-Cookie response → `csrftoken`, `mid`, `ig_did`
  3. Fetch bundle `Consumer.js` / `PolarisProfilePageContainer.js` → regex doc_id per query name
  4. POST graphql dengan `doc_id` + `variables` (URL-encoded JSON) + `lsd`
- **Header wajib**:
  - `x-ig-app-id: 936619743392459`
  - `x-asbd-id: 129477`
  - `x-csrftoken: <from cookie>`
  - `x-fb-lsd: <from HTML>`
  - `x-fb-friendly-name: <Query name, mis. PolarisProfilePostsQuery>`
  - UA: desktop Chrome konsisten
- **doc_id snapshot (Mei 2026, VOLATILE)**:
  - PolarisProfilePostsQuery ≈ `9310670392322965`
  - PolarisPostRootQuery ≈ `8845758582119845`
  - PolarisReelsTabContentQuery ≈ `25981206651899035`
- **Rate**: ~150-200 req/jam/residential IP. Datacenter blocked. Sticky 5-10 menit/IP.
- **Fallback post**: `https://www.instagram.com/p/{shortcode}/embed/captioned/`.

## Threads (Meta)

- Sama pola IG. `x-ig-app-id: 238260118697367`. Referer `https://www.threads.com/...` (rebrand 2025).
- **doc_id snapshot (VOLATILE)**:
  - BarcelonaProfileQuery ≈ `23996318473300828`
  - BarcelonaProfileThreadsTabRefetchableQuery ≈ `6232751443445612`
  - BarcelonaPostPageQuery ≈ `5587632691339264`
- Auto-extract dari bundle `BarcelonaProfileRoute.js` / `BarcelonaPostPageRoute.js`.

## X / Twitter (Python, curl_cffi)

- **Runtime**: Python 3.10 + `curl_cffi` `chrome131` impersonation. Originally planned Node.js because of `x-client-transaction-id` — empirically NOT required for guest-token route (verified 2026-05-14).
- **Auth path**:
  1. POST `https://api.twitter.com/1.1/guest/activate.json` dengan public bearer → `guest_token` (TTL 2-4 jam, rotate on 401/403).
  2. GET `https://api.twitter.com/graphql/{queryId}/{operationName}?variables=...&features=...&fieldToggles=...` dengan headers `authorization: Bearer <bearer>`, `x-guest-token`, `x-twitter-client-language: en`, `x-twitter-active-user: yes`, `Origin: https://twitter.com`.
- **Bundle harvest** (sekali per actor instance, cached in-memory):
  1. GET `https://x.com/home` → regex `main\.[a-f0-9]+\.js` URL.
  2. GET that main.js → regex `queryId:"([A-Za-z0-9_-]+)",operationName:"(\w+)",operationType:"\w+",metadata:\{featureSwitches:\[([^\]]*)\],fieldToggles:\[([^\]]*)\]\}` → 158 ops dengan full feature set.
  3. Bearer juga di-extract dari bundle (regex `AAAAAAAAAAAAAAAAAAAAA[A-Za-z0-9%]{60,}`) — fallback ke hardcoded constant.
- **Feature switches**: setiap operation punya whitelist sendiri dari bundle. 7 switches MUST BE FALSE (`verified_phone_label_enabled`, `responsive_web_graphql_skip_user_profile_image_extensions_enabled`, `responsive_web_enhance_cards_enabled`, `tweet_awards_web_tipping_enabled`, `responsive_web_media_download_video_enabled`, `responsive_web_grok_show_grok_translated_post`, `responsive_web_grok_community_note_auto_translation_is_enabled`). Rest = True. Field toggles default False.
- **Anonymous-friendly endpoints (guest token)**:
  - `UserByScreenName` ✅
  - `UserByRestId` ✅
  - `UserTweets` ✅ (limit ~100 entries, no cursor for guest tokens)
  - `UserTweetsAndReplies` ✅
  - `UserMedia` ✅
  - `TweetResultByRestId` ✅
- **Login-walled (return 404 for guest)**:
  - `TweetDetail` — threaded conversation
  - `SearchTimeline` — general keyword search
- **Syndication fallback** (no auth, no bundle): `https://cdn.syndication.twimg.com/tweet-result?id=<id>&token=<t>`. Token = `((parseFloat(id)/1e15)*PI).toString(36).replace(/(0+|\.)/g,'')`. Used as S2 in `x/post-detail` when GraphQL fails.
- **`x/search` workaround**: pattern-match `from:USERNAME [keywords]` → degrade to `UserTweets` + client-side substring filter. General search returns `_error: "login_required"` until authenticated proxy is supplied.
- **queryId snapshot (Mei 2026, VOLATILE — code refreshes per-run)**:
  - UserByScreenName → `IGgvgiOx4QZndDHuD3x9TQ`
  - UserByRestId → `VQfQ9wwYdk6j_u2O4vt64Q`
  - UserTweets → `36rb3Xj3iJ64Q-9wKDjCcQ`
  - UserTweetsAndReplies → `D5eKzDa5ZoJuC1TCeAXbWA`
  - UserMedia → `9EovraBTXJYGSEQXZqlLmQ`
  - TweetResultByRestId → `2Acdg-VztGlHX7MjX67Ysw`
  - TweetDetail → `oCon7R-cgWRFy6EfZjaKfg` (login-walled)
  - SearchTimeline → `Yw6L66Pw54NHKuq4Dp7b4Q` (login-walled)
- **Reference impl**: [`x/account/shared/x_client.py`](../x/account/shared/x_client.py) — canonical, copied 1:1 to all 4 actor folders. Sync canonical via [`x/shared/src/x_client.py`](../x/shared/src/x_client.py).

## Reddit (post-2023 lockdown)

- **OAuth installed-app** (no user login, 60 rpm):
  - POST `https://www.reddit.com/api/v1/access_token` dengan basic auth `<client_id>:` (password kosong), body `grant_type=https://oauth.reddit.com/grants/installed_client&device_id=<uuid>`.
  - Use returned token sebagai `Authorization: Bearer <token>` untuk `oauth.reddit.com` endpoints.
- **Fallback** `.json` endpoint (10 rpm/IP), UA wajib unik (format Reddit: `<your-domain>/<actor-name> by /u/<username>`).
- Endpoint: `/r/{sub}/new.json`, `/comments/{post_id}.json`, `/user/{u}.json`, `/search.json`.
- **Reference**: `redditwarp` (installed-app support).

## Quora

- HTML scrape `https://www.quora.com/<question-slug>` → parse `<script id="__NEXT_DATA__">` JSON.
- **WAJIB** `curl_cffi` impersonate (`requests` polos langsung 403 dari Cloudflare).
- GraphQL internal opsional: `https://www.quora.com/graphql/gql_para_POST` butuh `x-csrf-token` + `x-quora-formkey` rotated.

## Facebook (mbasic-first)

- **Strategy**: `https://mbasic.facebook.com/{username_or_id}` (HTML simple) → fallback `m.facebook.com` → last resort `https://www.facebook.com/api/graphql/` dengan `lsd` + `jazoest` (no `fb_dtsg` untuk read).
- Limit anon ~1000 req/IP sebelum login-wall. Residential rotate wajib.
- Fragile — siap deprecate jika >50% block.

## Substack

- `https://{pub}.substack.com/api/v1/archive?sort=new&offset=0&limit=12` — list posts
- `https://{pub}.substack.com/api/v1/posts/{slug}` — post detail
- `https://substack.com/api/v1/publication/{id}` — publication meta
- No auth, no rate-limit signifikan.

## Twitch

- `https://gql.twitch.tv/gql` dengan hardcoded `Client-ID: kimne78kx3ncx6brgo4mv6wki5h1ko` (web client public ID).
- Body: batched GraphQL queries (array).

## Pinterest

- Internal Resource: `https://www.pinterest.com/resource/{Resource}Resource/get/?data=<urlencoded_json>` (mis. `UserResource`, `BoardResource`, `PinResource`).
- Cookie warm-up: GET landing dulu untuk `_pinterest_sess`.

## Mastodon (per-instance)

- `https://{instance}/api/v1/accounts/lookup?acct=<>`
- `https://{instance}/api/v1/statuses/{id}`
- Catatan: banyak instance set `DISALLOW_UNAUTHENTICATED_API_ACCESS=true` di 2025+; input wajib `instance` parameter + optional `access_token`.

## Medium

- Trik `https://medium.com/{slug}?format=json` — return JSON dengan prefix `])}while(1);</x>` (wajib strip).
- Fallback RSS `https://medium.com/feed/@{user}`.

## Tumblr

- v2 API `https://api.tumblr.com/v2/blog/{blog}/{posts|info}?api_key=<consumer_key>` — consumer-only, public.
- Tidak butuh OAuth user; consumer key di-register satu kali.
