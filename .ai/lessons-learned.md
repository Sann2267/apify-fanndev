# Lessons Learned — What NOT to Try

> **Every entry on this page represents days (sometimes weeks) of effort that didn't pan out.** If you're tempted by any of these approaches, the cumulative evidence says: don't. Read this BEFORE sinking 2+ hours into a "novel" solution — it's probably already in here.

---

## ❌ Switching HTTP library/profile/headers against a CDN-edge-cache-state gate

**Tempting approach:** When a site returns a JS-interstitial "bot check" (theprint.in's CloudFront + `X-Powered-By: luroConnect`, ~1.8KB 200-OK "Just a moment" body), assume it's a fingerprint-based WAF like the others in this portfolio and run the usual TLS-profile ladder / try a different HTTP library / add realistic headers / warm up the session first.

**Why it doesn't work — if the gate is keyed on CDN cache state, not fingerprint, none of the usual levers apply.** Confirmed on theprint-scraper (2026-08-26) with 34 distinct HTTP-layer configurations against a fixed 8-URL test set (mixing seconds-old to years-old articles): 20 `curl_cffi` impersonate profiles, 8 `primp` (rquest/BoringSSL, a different TLS stack) profiles, `scrapling`'s HTTP-only `Fetcher` with `stealthy_headers=True` (auto-realistic `Accept`/`Sec-Fetch-*`/`Referer`) and `http3=True`, homepage-warmup-first vs. cold-start, and same-session same-URL retries up to ~90s — **zero variance in outcome across all 34**. Same URLs blocked, same URL a hit, every single time. The tell: response headers carry `X-Cache: Miss from cloudfront` on every blocked response and `Hit from cloudfront` on every clean one — check for a CDN cache-status header FIRST when a "bot check" looks weirdly binary (always-blocked or never-blocked per URL, no partial credit for a "better" TLS profile).

**What works instead:** Nothing HTTP-side. The interstitial only appears on a cache MISS; a real, previously-published/organically-trafficked URL is usually already cached and returns instantly with zero special handling. The only lever is time — retry the specific failing URL minutes-to-hours later once organic/CDN traffic populates that edge. A brand-new article (published in the last few minutes) is the case most likely to transiently fail; it resolves itself once traffic (or the CDN's own crawl) reaches it. Detect the failure mode (`Miss from cloudfront` + interstitial body markers) and surface it as a distinct, honest error/retry-later state rather than burning HTTP-library-switching effort on it.

**Time spent confirming this:** ~1 hour of systematic ladder-testing (see `theprint-scraper/CRAWLING_METHOD.md` "Follow-up investigation" section for full per-URL data).

---

## ❌ Shopee `x-sap-sec` HTTP-only signature replication

**Tempting approach:** Reverse-engineer Shopee's `x-sap-sec` token generation to scrape `/api/v4/*` endpoints with full per-variant price + stock + sold count.

**Why it doesn't work:**
Shopee's token engine is a **bytecode VM** inside `sandbox-indirect-eval-secure.6fe0aecd645a631774be.js` (758KB). The algorithm composes:
- Salsa20 (20-round)
- Custom RC4 (256-byte S-box hardcoded permutation)
- xxHash32/64
- SHA-1, MD5, Adler-32
- BKDR Hash, zlib/Deflate
- RSA BigInteger Montgomery exponentiation
- **23-byte behavioral telemetry** (Yt/Bt/jt/Zt ring buffers of mouse/scroll/keyboard/touch events)
- **Device fingerprinting** (canvas, WebGL, AudioContext)
- RLE compression scheme `A|{count}|`

Without a real browser runtime providing `requestAnimationFrame`, `navigator`, `crypto.subtle`, the bytecode VM throws halfway through. **Conclusion (verified by cyber-security RE analysis):** TIDAK MUNGKIN replikasi tanpa JS engine.

**What works instead:**
- Googlebot UA spoofing for SEO render (gives price + basic data, no per-variant)
- Camoufox browser interception of `/api/v4/pdp/get_pc` response — the only way to get per-variant price/stock/sold

**Time wasted exploring this:** ~5 days across multiple attempts. Don't.

**Documented in:** Shopee Camoufox shopesss `ANALYSIS.md` (Cyber Security RE)

---

## ❌ TikTok PO Token / BotGuard HTTP-only generation

**Tempting approach:** Generate a valid PO Token (Proof-of-Origin) for YouTube/TikTok endpoints that gate behind it (`/api/timedtext` transcripts, parts of TikTok signed paths).

**Why it doesn't work:**
PO Token / BotGuard is Google's per-session JS challenge designed specifically to require a JS execution environment. It's a "you must execute this JS in something that looks like a browser to prove you're real" challenge. The output is signed by Google's infrastructure based on the challenge state — not crypto reversible.

**What works instead:**
- For YouTube transcripts: accept the limitation, mark as TODO (PO Token harvest via Node BotGuard runner is the planned future work — not yet shipping)
- For TikTok: use the carcabot X-Gnarly approach for X-Gnarly specifically (that one IS pure crypto), but PO Token-equivalent paths remain blocked

**Time wasted exploring this:** unknown, multiple attempts in YouTube transcripts actor.

---

## ❌ Playwright / Selenium for TikTok

**Tempting approach:** Use Playwright or Selenium to bypass TikTok's signature requirement by letting a real browser produce signatures.

**Why it doesn't work:**
- TikTok detects `navigator.webdriver` flag
- `ticket_guard` never bootstraps in webdriver-controlled contexts
- X-Gnarly signature is never produced (response body is 0 bytes)
- Even with `--disable-blink-features=AutomationControlled`, deeper detection (mouse movement entropy, timing analysis) triggers

**What works instead:**
- Camoufox (Firefox stealth fork) — has more aggressive automation hiding
- BUT for TikTok specifically: the Node X-Gnarly sidecar from `carcabot/tiktok-xgnarly-decoded` is faster, cheaper, and avoids browser entirely. Use it. Reserve Camoufox for Shopee per-variant pricing only.

**Documented in:** TikTok Apify actors collection — "What didn't work" section.

---

## ❌ Solving CAPTCHA challenges programmatically (2captcha, anti-captcha)

**Tempting approach:** Integrate a CAPTCHA solver (2captcha, anti-captcha, etc.) to clear PerimeterX/DataDome/Cloudflare CAPTCHA escalations.

**Why it doesn't work (well enough to ship):**
- Sub-1% success rate for modern PX/DD CAPTCHAs in production tests
- $1–$3 per solve is expensive at scale
- Solving creates a "I'm a bot that just solved a CAPTCHA" fingerprint that PX/DD use to escalate further
- Adds external service dependency + privacy concerns

**What works instead:**
- **No-captcha-solver policy:** When a captcha is served, mark the URL as failed (`_error: "captcha_escalation"`) and continue. Use rotation/proxy budget to avoid hitting captcha walls in the first place.
- For Bloomberg/Zillow specifically: TLS profile rotation extends working pages 4× before captcha appears.

**Documented across:** all anti-bot/ files (no-captcha-solver policy).

---

## ❌ Hardcoded GraphQL doc_id without refresh path

**Tempting approach:** "Just commit the doc_id we captured today; the scraper will work."

**Why it doesn't work:**
Meta (IG/FB/Threads) doc_ids rotate every 2–4 weeks. Twitter queryIds rotate roughly weekly. A hardcoded value pages ops every fortnight.

**What works instead:**
- Snapshot in code (last-known-good) for instant first-run
- Bundle harvest function that programmatically extracts the current value
- Trust-but-verify cache: try snapshot, on 400/404 trigger harvest, retry once
- Weekly healthcheck smoke test

**Documented in:** [`skills/graphql-doc-id-rotation.md`](skills/graphql-doc-id-rotation.md).

---

## ❌ Escalating to a browser (or blaming the proxy) after ONE TLS profile 403s

**Tempting approach:** `curl_cffi chrome131` returns 403 → conclude "this target is IP-blocked / needs premium residential / needs Camoufox" and reach for the expensive option.

**Why it doesn't work (it's premature surrender):**
Most modern WAFs — Fastly especially — blocklist **specific JA3/JA4 fingerprints**, not the IP. `chrome131` is widely burned as of 2026. A single-profile 403 tells you almost nothing. Declaring "browser needed" here throws away a 10×-cheaper HTTP path that usually exists — and browsers are 10× slower, 10× costlier, and detectable (see the Camoufox-for-everything entry below).

**Proof (Rightmove, UK, 2026-07-09):** `curl_cffi chrome131` → 403 from a *genuine UK residential IP* (Plusnet). Same IP, same everything, just a different profile: `chrome124` / `chrome116` / `chrome99_android` / `safari17_0` / `edge101` → **200, 1.1 MB**. All `primp` profiles → 200. The initial "Apify residential is IP-blocked, needs premium UK resi or a browser" conclusion was **wrong** — it was a one-profile JA3 block. Fixing the profile turned a "give up" into a fully working HTTP-only actor (search + detail).

**What works instead — the mandatory ladder BEFORE any browser/proxy escalation:**
1. Run a full impersonation ladder on the SAME IP: `curl_cffi` `[chrome124, chrome116, chrome99_android, safari17_0, edge101]`, then `primp` `[chrome_131, firefox_135, safari_18]` (real Firefox JA3 is rarely blocked). `chrome99_android` and `safari17_0` clear a surprising number of PerimeterX/Fastly deploys.
2. Only if EVERY profile returns the *same* block do you have a real JS challenge / hard IP gate.
3. Distinguish the block class: a tiny-body 403 = JA3 block (ladder fixes it); a ~3KB JS interstitial (`_fs_ch_`, `AwsWafIntegration`, `challenge-platform`) = JS challenge (then, and only then, consider a browser — and even then prefer cookie-transplant over full-browser; note Fastly `_fs_ch_` won't transplant, AWS WAF will).
4. On Apify the proxy is unreachable off-platform (curl 56 CONNECT), so run the ladder via an in-actor cloud probe or the `waf-probe` actor (`{targets, profiles, ladder:true, proxyConfiguration}`) — don't conclude from local alone.

**The rule:** one profile failing is a data point, not a verdict. Never say "needs a browser" until the ladder is exhausted. See [`anti-bot/fastly.md`](anti-bot/fastly.md) and [`playbooks/waf-triage.md`](playbooks/waf-triage.md) Step 2.5.

---

## ❌ `requests` / `httpx` defaults against modern WAFs

**Tempting approach:** "It's just an HTTP request, `requests` is fine."

**Why it doesn't work:**
Every major WAF (Cloudflare, PerimeterX, DataDome, Akamai, Aliyun, Kasada) fingerprints TLS ClientHello. Python's default JA3/JA4 hash is on every blocklist. Plain `requests.get()` returns 403 instantly on any non-public-API target.

**What works instead:**
- `curl_cffi impersonate="chrome131"` baseline
- See [`skills/tls-fingerprinting.md`](skills/tls-fingerprinting.md) for per-target profile matrix

**This is the #1 mistake newcomers make.** Internalize this before starting.

---

## ❌ MTOP API name guessing without instrumentation

**Tempting approach:** "Let me guess the MTOP API name for Alibaba reviews — maybe it's `mtop.alibaba.reviews.get`?"

**Why it doesn't work:**
Aliyun MTOP API names are not in the public bundle (often). 498-combination brute-force probing (3 gateways × 7 app keys × 24 candidate names) all returns `FAIL_SYS_API_NOT_FOUNDED` for **Alibaba review-list specifically** as of May 2026. The API has been deprecated/internalized.

**What works instead:**
- Document the failure with diagnostic `mtopStatus` field
- Fall back to AGGREGATE-only (per-criterion star scatter from SSR HTML)
- Don't waste runtime in production probing — keep the candidate list but log discovery only once per deployment.

**Documented in:** [`skills/mtop-signed-requests.md`](skills/mtop-signed-requests.md) and Alibaba review-scraper README.

---

## ❌ Realtor.com `/api/v1/hulk_main_srp` with Googlebot UA

**Tempting approach:** "Googlebot bypass worked for SSR — let me also use it on the API path."

**Why it doesn't work:**
Realtor's Kasada-protected `/api/v1/hulk_main_srp` returns **404 to Googlebot UA by design** (Google doesn't index APIs, so allowing the API to be Googlebot-accessible serves no SEO purpose, and exposing it would defeat the Kasada protection).

**What works instead:**
- Scrape the SSR HTML path (`/realestateandhomes-search/<slug>/pg-<N>`) — that IS Googlebot-indexed.
- Parse `__NEXT_DATA__` from SSR for full listings.
- Document the trade-off: SSR doesn't carry priceHistory/taxHistory; ship `[]` and a note.

**Documented in:** [`anti-bot/kasada.md`](anti-bot/kasada.md).

---

## ❌ Sharing HTTP sessions across asyncio tasks

**Tempting approach:** "Let me share one `AsyncSession` across all worker tasks for efficiency."

**Why it doesn't work:**
- `curl_cffi.AsyncSession` wraps a curl handle that's NOT designed for concurrent use from multiple async tasks. You get weird intermittent failures: cookie jar corruption, partial responses, segfaults.
- Anti-bot cookies bind to "I am this client" — sharing a jar across N parallel "sessions" looks like rapid IP shuffling to the WAF.
- CSRF tokens get scrambled — request from worker A signed with worker B's just-rotated token.

**What works instead:**
- One `Session` per worker.
- One worker per asyncio task (use `asyncio.Semaphore(N)` to bound concurrency, not session-sharing).
- See [`skills/session-pool-rotation.md`](skills/session-pool-rotation.md).

---

## ❌ Mid-conversation proxy IP rotation

**Tempting approach:** "Rotate IP per request to evade rate limits."

**Why it doesn't work:**
- All anti-bot cookies (`_abck`, `_pxhd`, `_dd_s`, `__Secure-session_id`) bind to egress IP. Rotating IP mid-conversation invalidates them all.
- The "session_id" parameter in Apify residential proxy IS designed for sticky sessions — using random session IDs defeats the point.
- For ~10-minute runs, one session_id = one IP = one cookie jar = best results.

**What works instead:**
- Sticky session per Apify run (one session_id at startup, reuse).
- Rotate ONLY on explicit block (403/429/body marker), via the rotation_pool pattern.
- See [`skills/session-pool-rotation.md`](skills/session-pool-rotation.md).

---

## ❌ Manually overriding `Accept-Encoding`

**Tempting approach:** "Let me force `Accept-Encoding: gzip` for predictable response size."

**Why it doesn't work:**
Real Chrome 131 sends `gzip, deflate, br, zstd`. Real Firefox sends `gzip, deflate, br`. Overriding to `gzip` is a tell — Cloudflare/PerimeterX/DataDome use it as one of dozens of fingerprint signals.

**What works instead:**
- Let `curl_cffi`/`primp`/`scrapling` set `Accept-Encoding` via `impersonate=`.
- Verify it's the canonical value (`gzip, deflate, br, zstd` for Chrome 131) — don't touch it.

---

## ❌ Forcing HTTP/3 (QUIC) upgrade

**Tempting approach:** "HTTP/3 is newer, harder to fingerprint."

**Why it doesn't work:**
- Most impersonation libs default-disable h3 because the underlying curl/rquest/BoringSSL has limited h3 fingerprint coverage.
- WAFs may have started fingerprinting h3 specifically (less data, but real).
- Pinning h2 is more predictable and well-tested.

**What works instead:** Stay on h2. Don't follow `alt-svc` headers to h3.

---

## ❌ Camoufox / Playwright for everything

**Tempting approach:** "Just use a real browser everywhere; it'll work."

**Why it doesn't work (well enough):**
- 10× slower than HTTP-only
- 10× more expensive (RAM, CPU, Apify compute units)
- Still detectable on hard targets (TikTok, fully-Akamai-protected Tokopedia would detect)
- High maintenance burden (browser updates, profile drift, lock files)

**What works instead:**
- HTTP-only by default. Only escalate to Camoufox after exhausting HTTP options.
- The only verified Camoufox-required target in the portfolio is **Shopee per-variant pricing** (x-sap-sec is genuinely unreproducible).
- TikTok's X-Gnarly looks like it needs a browser but actually doesn't — pure Node sidecar.

---

## ❌ Replicating Akamai sensor_data POST

**Tempting approach:** Replicate the Akamai `_bm/_data` JS sensor POST to skip warmup.

**Why it doesn't work (well enough):**
- The sensor JS is intentionally obfuscated and updates monthly.
- Open-source projects (`akamai-spoofer`) exist but are brittle, single-platform, often regress.
- The TLS impersonation + homepage warmup pattern gets 99% of the way at 1% of the maintenance cost.

**What works instead:** `curl_cffi chrome131` + `await session.get("/")` warmup. Done. See [`anti-bot/akamai.md`](anti-bot/akamai.md).

---

## ❌ Trying to fix scraping issues by adding more headers

**Tempting approach:** "I'll add `X-Requested-With`, `X-CSRF-Token`, `X-Origin-Source`, ... until it works."

**Why it doesn't work:**
Most 403/429s are TLS-level, not header-level. Adding random headers makes the request look LESS like a real browser, not more. WAFs notice header sets that don't match a known UA's typical fingerprint.

**What works instead:**
- Diagnose WAF first ([`playbooks/waf-triage.md`](playbooks/waf-triage.md)).
- Trust your impersonation library's header set — only add platform-contract headers (`x-ig-app-id`, `x-source: tokopedia-lite`), not anti-bot guesses.
- Diff your headers against a real browser DevTools capture and match exactly.

---

## ❌ "It works locally; let's ship"

**Tempting approach:** Local smoke test passes → push to Apify Marketplace.

**Why it doesn't work:**
- Apify cloud runs from datacenter ASN; local runs from your residential/office IP.
- WAFs sometimes work for residential and fail for datacenter (or vice versa).
- Apify proxy availability differs (your residential subscription vs Apify's pool).
- Cold-start behavior differs (Apify containers have different memory profile).

**What works instead:** Always run a 1-input smoke test on Apify cloud before declaring done. See [`playbooks/apify-deploy.md`](playbooks/apify-deploy.md).

---

## ❌ Silent empty returns

**Tempting approach:** `return {} if not found else parsed_data` — let downstream filter.

**Why it doesn't work:**
- Downstream sees a stream of `{}` records and thinks the actor is working.
- Real bugs (schema rotation, profile burn, auth failure) look identical to "entity doesn't exist."
- Dataset pollution at scale; ops can't diagnose.

**What works instead:**
- Always emit a structured `_error` record on failure.
- See [`conventions/error-handling.md`](conventions/error-handling.md) and [`conventions/dataset-envelope.md`](conventions/dataset-envelope.md).

---

## ❌ TikTok mobile API direct (`tiktokv.com`)

**Tempting approach:** Hit `tiktokv.com/api/...` with mobile UA + device params.

**Why it doesn't work:**
The mobile host requires `X-Gorgon` signature + device-registration handshake (TikTok's mobile app registers each install). Without registration, requests return 200 with empty data or 403.

**What works instead:**
- The **mobile-params-on-web-host trick**: send mobile params (`aid=1233`, `device_type=iPhone13,2`, iOS UA) to **`www.tiktok.com`** instead. Web host accepts mobile params without X-Gorgon for comment/reply endpoints.
- See [`anti-bot/tiktok-mssdk.md`](anti-bot/tiktok-mssdk.md).

---

## ❌ Using `_m_h5_tk_enc` cookie (Aliyun MTOP)

**Tempting approach:** "I see `_m_h5_tk_enc` in browser DevTools — let me replicate it."

**Why it doesn't work:**
The `_m_h5_tk_enc` cookie is browser-set but **unused by MTOP server-side**. Sending it adds noise. Some Aliyun deployments use its presence as a trigger for extra anti-bot checks.

**What works instead:** Only `_m_h5_tk` (the unencrypted variant) is needed. Bootstrap it via throwaway request, ignore the `_enc` variant. See [`skills/mtop-signed-requests.md`](skills/mtop-signed-requests.md).

---

## ❌ Reformatting whitespace-sensitive GraphQL queries

**Tempting approach:** "Let me pretty-print the giant GraphQL query string for readability."

**Why it doesn't work:**
Tokopedia's `REVIEW_LIST_QUERY` (and similar persisted queries on other Apollo deployments) — the **server validates a hash** of the exact query string. Pretty-printing changes the bytes → hash mismatch → request rejected.

**What works instead:**
- Keep the exact minified string as captured from DevTools.
- Comment in code: `# DO NOT REFORMAT — whitespace-sensitive, hash-validated`.
- See [`anti-bot/akamai.md`](anti-bot/akamai.md) gotcha #2.

---

## ❌ Sorting Google Maps reviews by "relevant" from outside US

**Tempting approach:** "`!3e1` is the default sort; just use it."

**Why it doesn't work:**
From IPs outside US-locale, `!3e1` (sort=relevant) returns `[null,null,null,null,null,null,1]` — an ambiguous "denied" signal. Empty data, no error code.

**What works instead:**
- Auto-fallback to `!3e2` (newest) when `!3e1` returns nulls.
- The new sort yields real reviews. See [`skills/google-internal-apis.md`](skills/google-internal-apis.md).

---

## ❌ `curl_cffi firefox*` profile (silently falls back)

**Tempting approach:** "`curl_cffi impersonate='firefox133'` should give Firefox JA3."

**Why it doesn't work:**
`curl_cffi` is built on curl-impersonate which only supports Chrome/Safari/Edge real Firefox impersonation. Firefox profile name silently falls back to `random` — you get a randomized Chrome-like fingerprint, not Firefox.

**What works instead:**
- For Firefox JA3 specifically: use `primp` or `scrapling` (both ship real Firefox profiles).
- `curl_cffi firefox133` is fine for Capterra anyway — Capterra accepts `random` Chrome fingerprints just fine; the real win is "not stock Python."

---

## ❌ Auth-walled Twitter endpoints (`TweetDetail`, `SearchTimeline`)

**Tempting approach:** Use `TweetDetail` for threaded replies, `SearchTimeline` for general keyword search.

**Why it doesn't work:**
Both endpoints return 404 with anonymous guest token in 2025+. Twitter has deliberately gated threaded conversations and general search behind login.

**What works instead:**
- For threaded replies: use `TweetResultByRestId` (gives root tweet, not replies) + accept the limit.
- For general search: pattern-match `from:USERNAME [keywords]` → degrade to `UserTweets` + client-side substring filter. General keyword search across all of Twitter — not available without login.
- See [`skills/warm-page-token-harvest.md`](skills/warm-page-token-harvest.md) Twitter section.

---

## ❌ Building everything as one monorepo with shared deps

**Tempting approach:** "Let me share `client.py` across 8 Tokopedia actors via a parent package."

**Why it doesn't work:**
- Apify's Docker build context is **one folder**. Cross-actor imports break at build time.
- Even if you tar in the parent, you lose per-actor versioning.
- Updating shared code accidentally breaks 8 actors at once.

**What works instead:**
- Self-contained per actor — copy `client.py` into each actor folder via build script (e.g. `scripts/sync_shared.py` in Google Maps suite).
- Trade duplication for isolation. Refactor by updating the source then re-running sync.

---

## ❌ Skipping cookie warmup "to save one request"

**Tempting approach:** "The first API call might work — let me try without homepage warmup."

**Why it doesn't work:**
Akamai, PerimeterX, DataDome all issue trust cookies (`_abck`, `_pxhd`, `_dd_s`) on the first HTML page visit. Direct API call returns 403. The warmup is not optional.

**What works instead:**
- Idempotent `init_session()` that's called once per worker startup.
- See [`skills/cookie-warmup.md`](skills/cookie-warmup.md).

---

## ❌ Copying a site's full request body verbatim ("site parity") when a minimal one works

**Tempting approach:** Once you've found the real internal API a site's own
front-end calls, copy its exact request body field-for-field — surely
matching the real client most closely is the safest, most "authentic" way
to call it.

**Why it doesn't work (well enough):**
Agoda's `POST /api/cronos/property/review/HotelReviews` accepts the site's
full 10-field body (`hotelId`, `hotelProviderId`, `demographicId`, `pageNo`,
`pageSize`, `sorting`, `reviewProviderIds`, `isReviewPage`,
`isCrawlablePage`, `paginationSize`, `filters`) — but doing so returns HTTP
200 with `hasReviewsData: true` and a **silently empty** `comments` array
~40–60% of the time, across fresh sessions and different backend pods
(ruling out session/pod staleness). A field-by-field isolation sweep found
the failure is caused by some combination of the "extra" fields
(`reviewProviderIds` in particular looked implicated, but no single field
reproduced it in isolation — only certain combinations did). A **minimal**
4-field body (`hotelId`, `pageNo`, `pageSize`, `sorting`) was **10/10**
reliable across two independent sweeps and a real multi-page pull.

**What works instead:**
- When reverse-engineering a REST/JSON body from bundle JS, start from the
  *smallest* body that returns real data, not the site's full field set.
  Add fields back one at a time only if you need the behavior they change
  (e.g. `sorting` for order, `pageSize`/`pageNo` for pagination) — and
  re-verify reliability (3+ repeats) after each addition, not just after
  the first success.
- Treat "HTTP 200 but the array I actually want is empty" as its own
  failure class distinct from `not_found` — don't let a soft-empty response
  masquerade as either a real empty result or a hard error. Retry it like a
  transient (Category 2, `.ai/conventions/error-handling.md`), and use a
  ground-truth field (total review/result count from an aggregate section
  of the same payload, if present) to sanity-check against.

**Documented in:** `agoda-reviews-scraper/CRAWLING_METHOD.md`
("Body-shape reliability sweep").

---

## Dead end: `www.thenoplace.com` — no data surface at all (not a WAF problem)

**Tempting approach:** Domain looks like a live social platform ("noplace"),
so assume there is an internal REST/GraphQL API behind a WAF and start the
TLS profile ladder.

**Why it doesn't work:** There is nothing to block. The site is a **6-page
Vercel/Next.js Pages-Router landing site** for an iOS-only app
(`Islands XYZ, Inc.`, App Store id `6478601246`, bundle `xyz.islands.nospace.official`).
Plain `curl_cffi chrome124`, no proxy, no header tuning → `200 OK` on the
first try. `robots.txt` is `Allow: /`. Recon findings (2026-08-29):

- `_buildManifest.js` decodes to **11 routes total**, none of them data routes.
- `sitemap.xml` → `sitemap-0.xml` contains **exactly 1 URL** (`/blog`).
- All 16 client chunks grepped: the only backend hosts are
  `noplace-blog.ghost.io` (Ghost CMS) and a POST-only
  `waitlist-api-3d3lznnfca-uc.a.run.app`, plus the Firebase SDK.
- **The Ghost blog is dead**: `noplace-blog.ghost.io` returns
  `402 Site unavailable` (lapsed subscription), so the site's own
  `/api/ghost-posts` and `/api/ghost-settings` proxies return
  `500 {"error":"Request failed with status code 402"}`.
- `_buildManifest` has a rewrite `/@:handle` → `/user/:handle`, but **no
  `/user/[handle]` page exists** — every handle returns `404` with
  `x-matched-path: /404`. There are no public profiles.
- Subdomain sweep (22 names: `api`, `graphql`, `app`, `data`, `backend`, …)
  → **zero DNS resolutions**. Only apex + `www`.
- `/graphql`, `/api/posts`, `/api/users`, `/api/feed`, `/api/events`,
  `/.well-known/apple-app-site-association` → all `404`.

The entire scrapable surface is 6 static Notion-sourced markdown documents
(`privacy-policy`, `terms-of-service`, `sms-terms-of-service`,
`community-rules`, `faq`, `contact-us`), readable via
`/_next/data/<buildId>/<slug>.json`. No listing, no pagination, no feed.

**What works instead:**
- **Run the route census before the WAF ladder.** `_buildManifest.js`
  (Pages Router) or `app-build-manifest.json` (App Router) plus
  `sitemap*.xml` plus a subdomain sweep costs ~2 minutes and tells you
  whether a data surface exists *at all*. A 200 OK is not a green light —
  "no WAF" and "no data" look identical until you enumerate routes.
- Treat **`402` from a SaaS CMS backend** (Ghost, Webflow, Contentful) as a
  distinct signal: the customer stopped paying. It is not transient, not
  rate-limiting, and not fixable by retry or proxy rotation.
- For a **mobile-first app with a marketing-only website**, the real data is
  behind the app's authenticated backend (Firebase here). That is
  out-of-scope under `project/CONSTRAINTS.md` (Public Data / No Login) —
  stop and re-confirm the target with the user rather than escalating.

**Time cost if skipped:** ~15 min of recon saves an afternoon of profile
laddering against a site that was never blocking anything.


## Silent-empty trap: handle-based `at://` URIs on Bluesky / AT Protocol

**Tempting approach:** A bsky.app post URL is
`https://bsky.app/profile/<handle>/post/<rkey>`, and `at://` URIs accept
either a handle or a DID as the authority. So parse the URL straight into
`at://<handle>/app.bsky.feed.post/<rkey>` and skip the
`com.atproto.identity.resolveHandle` round-trip — the AppView resolves
handles everywhere else, and one fewer request is one fewer request.

**Why it doesn't work:** handle-based and DID-based `at://` URIs are NOT
interchangeable across XRPC methods. Same post, same rkey, measured
2026-08-29 against `public.api.bsky.app`:

| Method | `at://bsky.app/...` | `at://did:plc:z72i.../...` |
| --- | --- | --- |
| `app.bsky.feed.getPostThread` | 200, thread object | 200, thread object |
| `app.bsky.feed.getLikes` | **200, `likes: []`** | 200, `likes: 5` |
| `app.bsky.feed.getQuotes` | **200, `posts: []`** | 200, `posts: 5` |
| `app.bsky.feed.getPosts` | **200, `posts: []`** | 200, `posts: 1` |
| `app.bsky.feed.getRepostedBy` | **500 InternalServerError** | 200, `repostedBy: 3` |

Three of the five answer **HTTP 200 with a silently empty array**. Only
`getPostThread` tolerates a handle — which is exactly the method you are
most likely to smoke-test first, so the bug passes your first check and
then quietly produces empty like/quote/repost datasets forever. "This
post has no likes" and "you passed the wrong URI shape" are
indistinguishable downstream.

**What works instead:**
- Normalise **every** post-shaped `at://` URI to its DID authority via
  `com.atproto.identity.resolveHandle` before calling anything, and
  memoise the handle→DID map for the run (it is one cheap call per
  distinct account, not per post).
- More generally: on any API where an identifier has two spellings,
  test **every** consuming endpoint with both. Do not generalise from
  the one endpoint that happens to be lenient.
- Make the local test harness **fail a mode that returns zero rows**,
  rather than printing "ok, 0 records". That audit is what surfaced
  this; reading the lexicon docs would not have, because the lexicon
  says nothing about it.
- Emit an `empty_result` diagnostic row when a handler legitimately
  returns nothing, so a genuinely empty result is visibly distinct from
  a broken one in the dataset itself.

**Time cost if skipped:** the bug is invisible in testing and produces
plausible-looking empty datasets in production — the expensive kind.

**Documented in:** `bluesky-scraper/CRAWLING_METHOD.md` §4.

---

## Rate limit: retrying while blocked can extend the block (Bluesky searchPosts)

**Tempting approach:** treat HTTP 403 from a rate limiter as a normal
transient — retry on an exponential backoff until it clears.

**Why it doesn't work:** `app.bsky.feed.searchPosts` on `api.bsky.app`
(the only host serving it — `public.api.bsky.app` returns a BunnyCDN
HTML 403 for that path under every URL variant tried) uses a per-IP
token bucket whose penalty compounds when you keep knocking. Measured on
one IP:

| State | Result |
| --- | --- |
| Rested IP, burst of 8 | 200 ×5, then 403 |
| Paced 1 req / 3 s, 8 novel queries | 200 ×5, then 403 — pacing buys nothing |
| Blocked, single retry at +60 s | 200 (one token) |
| Blocked, rest 120 s, burst of 8 | 200 ×7 |
| After further blocked bursts, rest 180 s | 200 ×0 |
| After further blocked bursts, rest 300 s | 200 ×0 |
| End of a day's recon on that IP, rest 420 s, **single** request | 403 |

It is a bucket on request *count*, so spacing requests does not earn
extra calls — and each blocked attempt appears to keep the bucket
drained, which is why a longer rest returned fewer tokens than a shorter
one. An eager retry loop converts a 60-second inconvenience into an IP
that stays punished for many minutes, and the damage accumulates across
a session: by the end of one day's recon, that IP refused a single
search request after 420 s of complete silence. Past a point, waiting
stops working at all.

**Practical consequence for testing:** budget your recon requests on a
throttled endpoint. Burning them exploring the limit can leave you
unable to integration-test the very feature that needs them, with no
second IP to fall back to.

**What works instead:**
- **Rotate the exit IP** — a new IP is a new bucket, and this is the only
  reliable fix. Apify Residential handles it; rotate on the block rather
  than sleeping.
- When no proxy exists, **pace to stay under the limit** rather than
  discovering it (~1 request per 20 s here), cap the number of blocked
  waits (2), and then **fail loudly** with an actionable
  `rate_limited` row telling the user to enable the proxy. Do not keep
  retrying.
- Force such a mode to **concurrency 1** — parallel workers share one
  exit IP and only drain the shared bucket faster.
- Check the **blast radius** before assuming an IP ban: here every other
  method on the same host and same session kept returning 200 while
  search was blocked. A scoped throttle needs a scoped response.

**Documented in:** `bluesky-scraper/CRAWLING_METHOD.md` §3.


## Meta-lesson

**The pattern across all these dead-ends:** people try to bypass the fundamental architecture of bot defense (TLS fingerprinting, JS execution, IP reputation) with HTTP-level hacks. None of them work durably.

**The pattern across all the wins:** match the architecture. Use a library that produces the right TLS. Use a sidecar where JS crypto IS the requirement. Use a browser only where JS execution genuinely IS required. Don't fight the architecture.

---

## When to add to this list

When you sink >2 hours into an approach that ultimately fails, add an entry here. Specifically:
1. What you tried
2. Why it failed (specific symptom)
3. What works instead
4. Approximate time wasted (so the next person internalizes the cost)

Future agents land in a fresh project; this list saves them.

## See also
- [`README.md`](README.md)
- [`CLAUDE.md`](CLAUDE.md)
- The "What does NOT work" sections in every `anti-bot/*.md` file
