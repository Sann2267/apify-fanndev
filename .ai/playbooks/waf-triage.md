# Playbook: WAF Triage — Which Protection Is Blocking Me?

> **Same 403, different solutions.** Cloudflare 403 needs `firefox133`. DataDome 403 needs `primp`. PerimeterX 403 needs `scrapling safari2601`. Kasada 429 needs Googlebot UA. Picking the wrong bypass burns hours. This decision tree gives you the right answer in 60 seconds.

## Step 1 — Capture the failed response

Don't guess from a 403 code alone. Capture:

```python
async def probe(url: str):
    # Baseline: plain httpx
    import httpx
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url)
    print("STATUS:", r.status_code)
    print("HEADERS:", dict(r.headers))
    print("COOKIES:", dict(r.cookies))
    print("BODY HEAD:", r.text[:2000])
```

You need: status code, response headers, cookies set, first 2KB of body.

## Step 2 — Decision tree

```
┌─────────────────────────────────────────────────────────────┐
│  1. RESPONSE HEADERS                                         │
├─────────────────────────────────────────────────────────────┤
│  cf-ray present? cf-mitigated present?         → CLOUDFLARE  │
│  x-datadome-cid present?                       → DATADOME    │
│  x-kasada-tier present?                        → KASADA      │
│  x-akamai-* present?                           → AKAMAI      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. COOKIES SET BY RESPONSE                                  │
├─────────────────────────────────────────────────────────────┤
│  _px3 / _pxhd / pxcts / _pxvid?               → PERIMETERX   │
│  _dd_s / datadome?                            → DATADOME     │
│  _abck / bm_sz / ak_bmsc?                     → AKAMAI       │
│  KP_UIDz / KP_RTID?                           → KASADA       │
│  __cfduid / __cflb / __cf_bm?                 → CLOUDFLARE   │
│  _m_h5_tk?                                    → ALIYUN (MTOP) │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. BODY MARKERS (status may be 200!)                        │
├─────────────────────────────────────────────────────────────┤
│  "_____tmd_____" / "baxia-manager"                           │
│      / "sufei-punish" / "punish.html"          → ALIYUN      │
│  "tosv.html"                                   → PERIMETERX  │
│  "captcha-delivery.com" / "datadome.co"        → DATADOME    │
│  "Just a moment..." / "_cf_chl_"               → CLOUDFLARE  │
│  "Pardon Our Interruption" / "_abck"           → AKAMAI      │
│  "Please verify you are a human"               → PERIMETERX  │
│  "verify.captcha" in URL                       → TIKTOK      │
│  status_code: 2146                             → TIKTOK      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. STATUS CODE (last resort, ambiguous)                     │
├─────────────────────────────────────────────────────────────┤
│  429 (with no Retry-After)                    → KASADA likely │
│  429 (with Retry-After)                       → standard rate │
│  403 + opaque body                            → CLOUDFLARE   │
│  empty 200 / 0 bytes                          → TIKTOK / PX  │
└─────────────────────────────────────────────────────────────┘
```

## Step 3 — Confirm with a control fetch

Once you have a hypothesis, try the bypass with a known-working library/profile combo:

| Hypothesized WAF | Quick control |
| --- | --- |
| Cloudflare | `curl_cffi firefox133` → 200 expected |
| PerimeterX | `scrapling safari2601` → 200 expected |
| DataDome | `primp chrome_131` → 200 expected |
| Akamai | `curl_cffi chrome131` + homepage warmup → 200 expected |
| Aliyun | `curl_cffi safari18_0` + `aep_usuc_f` cookie → 200 expected |
| Kasada | `User-Agent: Googlebot/2.1` → 200 expected |
| TikTok | `curl_cffi chrome110` + warmup `/explore` → 200 expected |
| Meta GraphQL gate | warm-page entity URL + harvest `lsd` → POST works |

If the control fetch ALSO fails, your diagnosis is wrong — re-read body/cookies.

## Step 2.5 — Run the impersonation ladder BEFORE any browser/proxy escalation (MANDATORY)

**A single-profile 403 is a data point, not a verdict.** Modern WAFs (Fastly especially) blocklist specific JA3/JA4 fingerprints, not the IP. `chrome131` is widely burned as of 2026. Before you conclude "IP-blocked / needs premium residential / needs a browser," rotate the profile on the SAME IP:

```python
CC_LADDER = ["chrome124", "chrome116", "chrome99_android", "safari17_0", "edge101"]  # curl_cffi
PRIMP_LADDER = ["chrome_131", "firefox_135", "safari_18"]  # primp: real Firefox JA3 rarely blocked
# chrome99_android and safari17_0 clear a surprising number of PerimeterX/Fastly deploys.
```

- If SOME profile returns real content → it was a JA3 block; ship it HTTP-only. (Rightmove: chrome131=403 on a real UK-resi IP, chrome124=200.)
- If EVERY profile returns the SAME block → now classify it:
  - tiny-body 403, no JS → hard JA3/IP gate (try residential, then re-run ladder).
  - ~3 KB JS interstitial (`_fs_ch_` / `AwsWafIntegration` / `challenge-platform`) → JS challenge. Only now consider a browser — and prefer **cookie-transplant** (browser solves once → replay cookie over HTTP) over full-browser. Note: transplant works for AWS WAF, **not** Fastly `_fs_ch_` (session-bound). See [`skills/browser-cookie-transplant`](../skills/browser-cookie-transplant/SKILL.md).
- On Apify the proxy is unreachable from off-platform (`curl 56 CONNECT`) → run the ladder via an in-actor cloud probe or the `waf-probe` actor (`{targets, profiles, ladder:true, proxyConfiguration}`), not just locally.

**Never say "needs a browser" until this ladder is exhausted.** See [`lessons-learned.md`](../lessons-learned.md) — "Escalating to a browser after ONE TLS profile."

## Common confusables

### Cloudflare vs PerimeterX
Both can return 403 with opaque body. **Cookie tells:**
- `__cf_bm` / `__cfduid` → Cloudflare
- `_px3` / `_pxhd` → PerimeterX
- Both set? → Stacked deployment (rare; use scrapling safari2601 first, then escalate)

### DataDome vs PerimeterX
Both can stack with Cloudflare. **Cookie tells:**
- `_dd_s` → DataDome
- `_px3` → PerimeterX
- **Distinguishing test:** `primp chrome_131` passes DataDome, fails PerimeterX. `scrapling safari2601` passes PerimeterX, may not help DataDome.

### Kasada vs rate limit
Both return 429. **Distinguishing test:**
- Switch UA to `Googlebot/2.1` — Kasada returns 200, normal rate limit still 429.
- `x-kasada-tier` header present → Kasada confirmed.

### Akamai vs generic CDN
Akamai often hides behind generic-looking responses. **Test:**
- `_abck` cookie set in any response on the domain → Akamai.
- `bm_sz` / `ak_bmsc` cookie → Akamai.

### Aliyun WAF (returns 200!)
The trap: status_code is 200, but body is `<html>...baxia-manager...</html>`. **Always body-marker check Alibaba responses**, even on 200.

## Stacked WAFs

Some sites use multiple layers. Order of bypass:

1. **Cloudflare + PerimeterX** (StockX): TLS impersonation that works for both — `safari17/18_0` rotate
2. **Cloudflare + PerimeterX + Piano paywall** (IBD): `scrapling[fetchers]` covers both, then Piano gives intro + metadata
3. **Cloudflare + DataDome** (some tier-1 news): `primp` from Apify residential
4. **PerimeterX + IP-reputation gate** (Bloomberg deep pagination): 5-layer evolution (see [`anti-bot/perimeterx.md`](../anti-bot/perimeterx.md))

## Diagnostic Output Template

When you've diagnosed, write a one-paragraph note in the actor's README:

```
WAF: PerimeterX (PX8FCGYgk4) confirmed by _pxhd cookie + 403 body.
Bypass: scrapling Fetcher with safari2601 from Apify datacenter IP.
Fallback: rotate to safari260 on 403; on second fail, escalate to residential.
Known limits: deep pagination (>5 pages) requires 5-layer rotation.
Last verified: 2026-05-17.
```

This is your healthcheck baseline for quarterly re-verification.

## When triage gives no clear answer

- **No cookies, no markers, just 403:** likely a custom WAF or a misconfigured nginx. Try `curl_cffi chrome131` from residential — if that works, ship; if not, manually inspect from a real browser DevTools.
- **200 with empty body:** TikTok / PerimeterX `tosv.html` / some Meta queries. Use body length as heuristic: <1KB on a page that should be ≥10KB = soft block.
- **Different behavior from local vs Apify cloud:** confirms IP-reputation gating is part of the stack. Test from both before declaring a fix.

## See also
- [`anti-bot/cloudflare.md`](../anti-bot/cloudflare.md)
- [`anti-bot/perimeterx.md`](../anti-bot/perimeterx.md)
- [`anti-bot/datadome.md`](../anti-bot/datadome.md)
- [`anti-bot/akamai.md`](../anti-bot/akamai.md)
- [`anti-bot/aliyun.md`](../anti-bot/aliyun.md)
- [`anti-bot/kasada.md`](../anti-bot/kasada.md)
- [`anti-bot/tiktok-mssdk.md`](../anti-bot/tiktok-mssdk.md)
