# Skills — what a future agent needs to maintain this codebase

A future AI agent inheriting this codebase should be able to do all of
the following. Each skill is a competency, not a task list.

## Core skills

### 1. TLS impersonation reasoning
- Know the difference between `curl_cffi` (curl-impersonate, uses BoringSSL
  via libcurl) and `primp` (Rust + BoringSSL native). Know that primp
  profile names use underscores (`firefox_148`) and `curl_cffi` does not
  (`chrome131`).
- Know that proxy authentication WITH commas in the username breaks
  primp but works in curl_cffi. Switch transports accordingly.

### 2. WAF marker detection
- Detect WAF blocks by **body markers**, not HTTP status:
  `punish.html`, `_____tmd_____`, `baxia-manager`, `x5secdata`,
  `FAIL_SYS_USER_VALIDATE`, `RGV587_ERROR`, PerimeterX `_pxhd`.
- Know that AliExpress's WAF allow-lists SEO crawler User-Agents
  (Bingbot, Googlebot) on SEO-indexed pages (search, category) but
  not on MTOP gateway.

### 3. JS data-island extraction
- Walk balanced braces with a custom scanner (handles strings + escapes).
- Know the canonical paths for each platform's data variable
  (`__NEXT_DATA__`, `_init_data_`, `window.runParams`,
  `window.__INIT_DATA__`, `__APP_INITIAL_STATE__`).

### 4. Signed API replication
- Understand the MTOP signing protocol:
  `sign = md5(token & ts & app_key & data)`, where `token` is the
  32-char hex prefix of the `_m_h5_tk` cookie.
- Know which gateways are signed (`acs.aliexpress.com`) vs unsigned
  (`shoprenderview.aliexpress.com`).
- Know that ALL `acs.aliexpress.com` MTOP endpoints share the same
  Baxia gate — one workaround unlocks all of them, no workaround
  blocks all.

### 5. Apify SDK fluency
- `Actor.push_data(row)` for each output row.
- `Actor.get_input()` for the validated input object.
- `Actor.create_proxy_configuration(actor_proxy_input=...)` →
  `proxy_cfg.new_url()` rotates per-call.
- `Actor.log.info / warning / error` for structured logs.
- Build pinning: `apify ~= 2.7`, `pydantic == 2.9.2`,
  `browserforge == 1.2.3` (must be 1.2.3, not 1.2.4),
  `curl_cffi ~= 0.7`.

### 6. Asyncio + sync transport interop
- `curl_cffi` and `primp` are synchronous. Wrap them in
  `await loop.run_in_executor(None, lambda: sync_fn(...))`.
- `Actor` itself is async — use `async with Actor:` at the entry.
- `asyncio.Semaphore(max_concurrency)` limits parallel workers.

### 7. Apify input schema discipline
- Every property MUST have `description` (Apify rejects schemas
  without it). Add an `editor` field too where natural.
- `description` on `actor.json` MUST be ≤ 300 chars.
- `required` is a top-level array; only mark genuinely required
  properties.

### 8. Memory-system literacy
- `~/.claude/projects/<project>/memory/` is persistent context.
- Read `MEMORY.md` (index) at session start.
- Update individual memory files when discovering non-obvious facts
  (e.g. `project_shoprenderview_discovery.md` was written when
  shoprenderview was found to bypass Baxia for store-products).

## Reverse-engineering skills

### 9. Browser-capture reading
- Parse a `requests.get(...)` capture: identify cookies that matter
  (`_m_h5_tk`, `_baxia_sec_cookie_`, `cna`, `xman_*`) vs tracking
  noise (`_ga`, `_fbp`, `_uetvid`).
- Decode JSONP wrappers: strip `{cb}({...})` to get JSON.
- Read URL params: `jsv`, `appKey`, `t`, `sign`, `api`, `data`
  (URL-encoded JSON) — recognize the Alibaba/Taobao MTOP shape.

### 10. Probe design under proxy
- Spin up an Apify "probe mode" temporarily inside an existing actor
  (gated by an input flag). Don't deploy fresh actors just for probing.
- Per probe: log status, byte count, WAF markers, presence of
  expected JS variables, Set-Cookie names.
- Push raw probe results to a dataset so they can be inspected
  post-run without rerunning.

### 11. Field-availability auditing
- Live-dump `items[0].keys()` to verify the actual API schema. The
  documentation lies; the live response is ground truth.
- When fields turn null across the board, suspect an upstream API
  change before debugging the parser (verified happened to
  AliExpress `store` fields in 2026).

## Operational skills

### 12. Apify CLI workarounds
- Ignore the `Unknown error: Unexpected end of JSON input` exit code
  on push/call — known false-positive in apify-cli 1.5.0.
- Read the build log (not exit code) for the actual result. Look for
  `Build finished` + `Success: Actor was deployed`.

### 13. PowerShell ↔ Bash quoting
- PowerShell strips quotes from `--input` JSON strings. Use
  `--input-file <path>.json` instead.
- HEREDOCs for multi-line strings: single-quoted (`@'...'@`) preserves
  `$` literally; double-quoted (`@"..."@`) interpolates.

### 14. QA loop
- Run `qa_actors.py` after substantive changes. It runs
  `test_local.py` for every scraper, checks output field counts, and
  posts a Telegram summary.
- Expected to see AliExpress scrapers report WAF-block locally — this
  is normal (WAF blocks local IPs). They pass on Apify with
  RESIDENTIAL proxy.

## What NOT to learn

- **Baxia tfstk reversal**. The token is generated by obfuscated JS
  that Alibaba rotates monthly. Multiple public reverse-engineering
  projects exist but all break within weeks. Out of scope.
- **CAPTCHA solving**. Out of scope (the constraint is HTTP-only with
  no third-party challenge services).
- **Browser automation**. Hard constraint — never propose Playwright /
  Selenium / Puppeteer.
