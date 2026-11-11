# CLAUDE.md — Agent Operating Guide for Scraping Projects

> **You are working in a scraping/data-extraction project.** Read this file before doing anything else. It encodes 19 projects' worth of hard-won knowledge about what works, what doesn't, and what to never bother trying.

---

## Core Principles (non-negotiable)

1. **HTTP-only by default.** Never reach for Playwright/Puppeteer/Selenium until you have *proven* that no HTTP path works. Browsers are 10× slower, 10× more expensive, and detectable. Only acceptable browser tools: **Camoufox** (Firefox stealth) and only when a JS-VM-derived signature (Shopee `x-sap-sec`, TikTok pre-X-Gnarly era) is genuinely unreproducible.
2. **TLS fingerprint first, headers second, cookies third.** Most modern WAFs (Cloudflare, PerimeterX, DataDome, Akamai, Aliyun, Fastly) gate on JA3/JA4 before parsing headers. If your `requests`/`httpx` baseline returns 403, switch the HTTP library (see [`skills/tls-fingerprinting.md`](skills/tls-fingerprinting.md)) before tweaking UA strings. **One profile failing is a data point, not a verdict** — `chrome131` is widely blocklisted in 2026. Run the full ladder (`curl_cffi` chrome124/chrome99_android/safari17_0/edge101 + `primp` firefox_135) on the SAME IP before ever concluding "IP-blocked" or "needs a browser." A browser is 10× the cost; earn it (see [`lessons-learned.md`](lessons-learned.md) — "Escalating to a browser after ONE TLS profile").
3. **Identify the WAF before coding the bypass.** A 403 from Cloudflare and a 403 from Kasada need completely different solutions. See [`playbooks/waf-triage.md`](playbooks/waf-triage.md).
4. **Prefer JSON-LD > `__NEXT_DATA__` > Apollo state > HTML scraping > GraphQL persisted query.** Lower index = more stable across redesigns. Only escalate when the layer above doesn't carry the data you need.
5. **Raw passthrough, minimal renaming.** Output upstream's field shape verbatim. Downstream consumers (Elasticsearch, SQL, RAG pipelines) will normalize. Renaming creates schema-drift incidents when upstream changes. See [`conventions/dataset-envelope.md`](conventions/dataset-envelope.md).
6. **Fail loud, never fail silent.** A scraper returning `{}` for a missing field is worse than crashing — it silently corrupts datasets. Use Pydantic validators that *raise* on shape changes. See [`conventions/error-handling.md`](conventions/error-handling.md).
7. **Trust-but-verify cache for volatile artifacts.** `doc_id`/`queryId`/persisted-query SHA-256/RPC IDs rotate every 2–4 weeks. Cache them, but refresh on first 400/404 — don't pin and rot.
8. **Use Apify Residential proxy by default for any non-public-API target.** Datacenter ASN is fingerprinted upstream of TLS/headers for IG, FB, Google, Shopee, Realtor (Kasada), Zillow (PerimeterX), Skyscanner. Local DC may work for testing but production needs residential.

---

## Default Stack

| Layer | Default Choice | When to Switch |
| --- | --- | --- |
| HTTP client | `curl_cffi` (`chrome131`) | DataDome → `primp`; PerimeterX-Bloomberg → `scrapling[fetchers]` (`safari2601`); Capterra/Firefox-trusted → `curl_cffi firefox133` |
| Async runtime | `asyncio` + `httpx.AsyncClient` for low-risk; `curl_cffi.AsyncSession` for impersonation | n/a |
| HTML parsing | `selectolax` (fast) → `BeautifulSoup4 + lxml` (compatibility) → `parsel` (XPath needed) | Trafilatura for last-resort article-body enrichment |
| JSON extraction | Custom balanced-brace walker (see [`skills/balanced-brace-json.md`](skills/balanced-brace-json.md)) | jmespath for deeply nested fixed paths |
| Validation | `Pydantic v2` with `extra="forbid"` on output models | n/a |
| Deployment | Apify Actor (Python 3.10–3.12, base image `apify/actor-python`) | Beanstalk+Kafka pipeline for high-volume (Tokopedia, TikTok crawler, Shopee shopesss) |
| Output | Apify Dataset (`Actor.push_data()`) | Kafka topic if Beanstalk pipeline |
| Pinning | `pydantic >=2.9.0, <2.10.0` if using `crawlee 0.6.12` (HttpHeaders TypeError bug) | Otherwise pydantic latest |

See [`stacks/python-apify-actor.md`](stacks/python-apify-actor.md) for the canonical boilerplate.

---

## Decision Tree: New Target, Where Do I Start?

```
Target a new platform / endpoint
        │
        ▼
1. curl/wget baseline: does plain `requests` get 200? 
        │
        ├── YES → use httpx, ship it (Bluesky, Telegram, Mastodon, Substack tier)
        │
        └── NO (403/429/empty)
              │
              ▼
2. WAF triage: which vendor? (see playbooks/waf-triage.md)
        │
        ├── Cloudflare        → curl_cffi chrome145 / firefox133 (anti-bot/cloudflare.md)
        ├── PerimeterX        → scrapling safari2601 OR curl_cffi profile ladder (anti-bot/perimeterx.md)
        ├── DataDome          → primp 27-profile shuffle (anti-bot/datadome.md)
        ├── Akamai            → curl_cffi chrome131 + homepage warmup (anti-bot/akamai.md)
        ├── Aliyun (baxia)    → curl_cffi safari18_0 + body-marker detect (anti-bot/aliyun.md)
        ├── Kasada            → User-Agent: Googlebot trick (anti-bot/kasada.md)
        ├── Fastly (Varnish)  → RUN THE PROFILE LADDER FIRST (chrome124/safari17_0/edge101) before browser; 403-tiny=JA3 block, 3KB _fs_ch_=JS challenge (anti-bot/fastly.md)
        ├── AWS WAF (202)     → TLS first; else browser-solve-once + aws-waf-token transplant (anti-bot/aws-waf.md)
        ├── TikTok webmssdk   → Node sidecar X-Gnarly + mobile-params-on-web-host (anti-bot/tiktok-mssdk.md)
        ├── Meta (FB/IG/Threads) → warm-page token harvest + doc_id (skills/warm-page-token-harvest.md)
        └── Shopee x-sap-sec  → Camoufox browser interception (skills not bypassable HTTP-only; see lessons-learned.md)
              │
              ▼
3. Extract data — priority order:
   JSON-LD (most stable) → __NEXT_DATA__ → Apollo state → SSR HTML CSS selectors
        │
        ▼
4. Auth-walled? warm-page token harvest pattern (Meta) or guest-token flow (Twitter) or installed-app OAuth (Reddit) or session-token endpoint (Google batchexecute).
        │
        ▼
5. Pagination strategy: cursor (Reddit, IG) vs offset (Google Maps reviews) vs `start=`/`page=` (SERP) vs continuation token (YouTube/TikTok).
        │
        ▼
6. Ship multi-strategy fallback: S1 (primary) → S2 (fallback) → S3 (degraded). Always emit _source envelope tag.
```

---

## Required Quality Bar Before Shipping

- [ ] **Smoke test passes** on at least 1 representative input (real handle, real URL).
- [ ] **TLS profile rationale documented** in source code comment (why `chrome131` not `chrome120`).
- [ ] **Pagination has stop condition** (`hasMore=false`, empty page streak, max_results cap).
- [ ] **No silent empty returns** — missing required field raises `UnexpectedShape` / similar.
- [ ] **Envelope tag `_source`** present on every record (which strategy emitted it).
- [ ] **Concurrent calls bounded** by `asyncio.Semaphore(max_concurrency)` (default 1–6).
- [ ] **Volatile artifacts cached with refresh hook** (doc_id, queryId, RPC ID, persisted hash).
- [ ] **Dockerfile builds clean** on `apify/actor-python:3.X` base.
- [ ] **`actor.json` + `input_schema.json` + `output_schema.json`** present and valid (`apify validate-schema`). See [`skills/actor-output-schema/SKILL.md`](skills/actor-output-schema/SKILL.md).
- [ ] **README documents which WAF + which TLS profile + known limits.**
- [ ] **Store category + evidence-based monetization configured** (or its exact manual step
      documented) before the actor is considered complete — see
      [`skills/actor-store-monetization/SKILL.md`](skills/actor-store-monetization/SKILL.md). This
      runs automatically as the last step of `adding-new-actor`, not on separate request.

---

## When to Ask the User Before Coding

Confirm with the user before:
- Adopting **browser automation** (Camoufox/Playwright) — high cost/maintenance, only justify with concrete proof HTTP path fails.
- Adopting **OAuth user-flow** (Reddit user-OAuth, Tumblr user-key, Mastodon authenticated). Installed-app / consumer keys are usually allowed.
- Adopting **paid 3rd-party service** (CAPTCHA solver, residential proxy reseller beyond Apify). No-captcha-solver policy is default.
- Touching **Apify spend cap** — proxy plan budgets are user's decision.
- Building a **standalone server** (FastAPI, etc.) instead of an Apify Actor.

---

## Project Memory — Auto Memory System

If the user's environment has the auto-memory hook (`~/.claude/projects/<repo>/memory/`), maintain it per the global rules:
- Save user/feedback/project/reference entries as separate `.md` files.
- Update `MEMORY.md` index with one-line pointers.
- Link related memories with `[[name]]`.
- Don't duplicate what's already in this `.ai/` folder — memory is for *this conversation/project's quirks*, not generic scraping knowledge.

---

## File Index (read on demand)

| File | When to read |
| --- | --- |
| [`README.md`](README.md) | Folder overview & navigation |
| [`skills/*`](skills/) | When implementing a specific technique |
| [`skills/actor-store-monetization/SKILL.md`](skills/actor-store-monetization/SKILL.md) | After any new actor passes build/test/push (Phase 1-3) — required before marking it done |
| [`anti-bot/*`](anti-bot/) | When triaging a block |
| [`playbooks/*`](playbooks/) | When starting a multi-step task |
| [`stacks/*`](stacks/) | When bootstrapping a new actor/pipeline |
| [`conventions/*`](conventions/) | Before writing the first push_data call |
| [`lessons-learned.md`](lessons-learned.md) | Before sinking >2 hours into a "novel" approach — check if it's already in the dead-ends list |

---

## Final Reminder

**This folder is the memory of every scraper that came before.** When you hit a wall, the answer is probably already in here. Search before improvising. When you discover something genuinely new, add a file — the next agent who lands in a fresh project will thank you.
