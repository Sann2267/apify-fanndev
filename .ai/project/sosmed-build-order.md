# Build order & status

Urutan pembangunan ROI-prioritized (high-demand di Apify marketplace dulu, fragile/edge case di akhir).

## Status legenda

- ✅ — built + smoke-tested live
- 🟡 — built, belum di-smoke-test (bundle drift mungkin terjadi)
- 🟠 — scaffold only (folder + Dockerfile + shared/), scraper logic TODO
- ⬜ — planned, belum dimulai
- ❌ — di-skip (out of scope)

## Order

| # | Platform | Runtime | Actors | Status | Catatan |
|---|---|---|---|---|---|
| 1 | Bluesky | Python | 4 | ✅ 4/4 | account, account-posts, post-detail, search — XRPC anon |
| 2 | Telegram | Python | 2 | ✅ 2/2 | channel-posts, post-detail — HTML only |
| 3 | YouTube | Python | 8 | ✅ 6/8 | channel, video-detail, video-comments, search, playlist, shorts (via video-detail). ❌ transcripts (PO Token gating), trending (removed/login-walled) |
| 4 | Substack | Python | 3 | ✅ 3/3 | publication, publication-posts, post-detail — JSON public, easy |
| 5 | Instagram | Python | 7 | ✅ 5/7 | account ✅, account-posts ✅, account-reels ✅, post-detail ✅, **post-comments ✅ (PolarisPostCommentsContainerQuery doc_id 26113520058347588, anon-friendly via warm-page tokens)**. ❌ hashtag (api/v1/tags 404→HTML shell→login redirect), search (web/search/topsearch 401) |
| 6 | Threads | Python | 4 | ✅ 4/4 | account ✅ (S1-html SSR), account-threads ✅ (Barcelona GraphQL), account-replies ✅ (Barcelona GraphQL), post-detail ✅ (S1-html SSR + S2 GraphQL fallback) |
| 7 | X (Twitter) | Python | 4 | ✅ 4/4 | account, account-tweets, post-detail; search via from:user fallback. curl_cffi + bundle queryId harvest + guest token |
| 8 | Reddit | Python | 4 | ⚠️ 3/4 | subreddit-posts ✅ (www-json), user-profile + search ✅ (old.reddit fallback). ❌ post-detail (comment threads www-403 + old-404 anon; needs `redditClientId` for OAuth) |
| 9 | Mastodon | Python | 2 | ✅ 2/2 | account, status-detail — per-instance public API |
| 10 | Medium | Python | 2 | ✅ 2/2 | user ✅ (profile + 10 recent posts via Apollo+RSS fallback), post-detail ✅ (full article body via Apollo bodyModel walk — soft paywall bypass per .ai/skills/apollo-state-paywall.md) |
| 11 | Tumblr | Python | 2 | ✅ 2/2 | blog ✅, post-detail ✅ — auto-fallback to v1 anonymous endpoint when api_key not provided (works out of the box; richer fields with key) |
| 12 | Twitch | Python | 3 | ✅ 3/3 | channel, clips, video-detail — inline GQL queries |
| 13 | Pinterest | Python | 3 | ✅ 3/3 | user-profile ✅ (S2 __PWS_INITIAL_PROPS__ DFS walk), board ✅ (S2 warm-page boards/BoardFeedResource preload), pin-detail ✅ (S2 widgets.pinterest.com/v3/pidgets public endpoint) |
| 14 | Quora | Python | 2 | ✅ 2/2 | user-profile ✅, question-detail ✅ — Relay GraphQL via warm-page token harvest. rootClsKey → operation map; queryId resolved live from page-bundle rspack chunk |
| 15 | Facebook | Python | 3 | ✅ 3/3 | page ✅ (ProfileCometHeaderQuery, auto-rotated doc_id), post-detail ✅ (inline JSON Story walk; CometSinglePostDialogContentQuery doc_id 26218104541200201 wired for deep comment pagination), **page-posts ✅** (migrated to ProfileCometTimelineFeedRefetchQuery doc_id 26818010721182044 with full relay-provider variables — 1 edge/call, paginate via per-edge cursor; handles both old-style usernames and Profile Plus URLs) |

## Blocked / needs special access

Actor yang masih butuh dependency eksternal. Lihat [`SETUP.md`](../SETUP.md) untuk instruksi detail user-action.

| Platform | Actor | Blocker | Action required |
|---|---|---|---|
| YouTube | `transcripts` | `/api/timedtext` return 200 empty tanpa PO Token (BotGuard JS gating, mid-2024+) | **User action**: pilih strategy di [SETUP.md § YouTube PO Token](../SETUP.md#youtube-po-token-untuk-transcripts) (A: 3rd-party API, B: BotGuard sidecar, C: skip) |
| Reddit | `post-detail` | www `/comments/<id>.json` 403 anti-bot, old.reddit 404 untuk slugless | **User action**: register Reddit installed-app → set `redditClientId` di INPUT. Step-by-step di [SETUP.md § Reddit OAuth](../SETUP.md#reddit-oauth-untuk-post-detail) |

Status setelah fix Quora + Pinterest (2026-05-18): **49/52 actor working** (94%). Sisa 3:
- 1 actor butuh user action (`reddit/post-detail`)
- 1 actor butuh decision (`youtube/transcripts`)
- 1 actor genuinely out of scope (`youtube/trending` — login-walled)

Detail issue + repro log untuk masing-masing ada di [`reports.md`](../reports.md) (cari Issue #17–#21).

## Out of scope (tidak akan dibangun)

Platform/actor yang skip karena ROI rendah / blocker arsitektural fundamental / butuh login session:

- ❌ **LinkedIn** — soft auth-wall + status 999 aggressive
- ❌ **Snapchat Spotlight** — signed param tidak dapat di-reverse
- ❌ **Discord** — login + WS, tidak HTTP-only
- ❌ **Weibo** — cookie CN + proxy regional, low ROI
- ❌ **TikTok** — sudah ada di sibling project [`../apify-tiktok-actors/`](../../apify-tiktok-actors/)
- ❌ **Instagram `hashtag`** — `/api/v1/tags/logged_out_web_info/` 404 → HTML shell → redirect login. Butuh authenticated session cookie (login-walled 2025).
- ❌ **Instagram `search`** — `/web/search/topsearch/` 401 `{"message":"Server Error"}`. Login-walled 2025.
- ❌ **YouTube `trending`** — `FEtrending` dihapus 2024–2025; `FEwhat_to_watch` / `FEexplore` / `FEpopular` / `FEcharts` semua 400 atau anon-shell. YouTube genuinely killed anon trending; butuh session cookie.

## Marathon notes

Saat menjalankan marathon build (semua platform berturut-turut):

1. Build canonical `shared/` di actor pertama platform → cp ke sibling actors.
2. Smoke-test minimal 1 actor per platform sebelum lanjut.
3. Update status di tabel atas saat selesai per platform.
4. Saat ketemu bundle drift / endpoint dead → log di `.ai/troubleshooting.md`.

## Refresh cadence

Karena `doc_id` / `queryId` / signature volatile (rotate 2-4 minggu di IG/Threads/X), actor di platform tersebut butuh **healthcheck schedule** di Apify Console:

| Platform | Healthcheck interval | Alert kondisi |
|---|---|---|
| X | daily | bundle hash diff, GraphQL 400 |
| Instagram | weekly | doc_id 404, lsd token kosong |
| Threads | weekly | sama dengan IG |
| YouTube | weekly | innertube API key invalid |
| Reddit | monthly | installed-app token grant gagal |
| Lainnya | monthly | smoke-test sample |
