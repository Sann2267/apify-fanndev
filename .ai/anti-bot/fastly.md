# Fastly (Varnish edge + Next-Gen WAF / Bot Management)

> **A Fastly 403 is usually NOT an IP block — it is most often a TLS/JA3 fingerprint block on your specific impersonation profile.** Fastly fronts many sites via Varnish (`Server: Varnish`, `X-Served-By: cache-<pop>`, `X-Cache`). It ships in (at least) two escalating tiers, and they need completely different responses. Diagnose the tier before you touch a proxy or a browser.

## Diagnosis (Fastly present)

- Response headers: `Server: Varnish`, `X-Served-By: cache-<pop>-<id>` (e.g. `cache-sin-...`), `X-Cache: MISS/HIT`, `X-Timer`, `Via: 1.1 varnish`.
- No `cf-ray` / `x-datadome` / `_abck` — if those are present it's a different WAF stacked in front.

```python
def is_fastly(resp) -> bool:
    h = {k.lower(): (v or "").lower() for k, v in resp.headers.items()}
    return "varnish" in h.get("server", "") or "cache-" in h.get("x-served-by", "")
```

## The two tiers (identify BEFORE escalating)

### Tier 1 — TLS/JA3 fingerprint block  (403, tiny body, NO JS challenge)

Signature: **HTTP 403**, `Server: Varnish`, body is small (~400–500 bytes) with no challenge JavaScript. This is Fastly Bot Management refusing your **ClientHello JA3/JA4** — it has fingerprinted and blocklisted the specific impersonation profile you used (commonly **`chrome131`**, which is widely burned across WAF vendors as of 2026). **A real residential IP with the wrong profile still gets 403 here.** This is the trap that looks like an IP/geo block but is not.

**Fix: rotate the impersonation profile — do NOT reach for a browser.** Run the ladder:

```python
CC_LADDER = ["chrome124", "chrome116", "chrome99_android", "safari17_0", "edge101"]  # curl_cffi
# primp also clears it: chrome_131 / firefox_135 / safari_18 (real Firefox JA3 is rarely blocked)
```

**Verified (Rightmove, UK, 2026-07-09):** `curl_cffi chrome131` → **403** (len ~425) even from a genuine UK residential IP (Plusnet, `dyn.plus.net`, GB). `chrome124` / `chrome116` / `chrome99_android` / `safari17_0` / `edge101` → **200, ~1.1 MB**; all `primp` profiles → 200. Proxy was never the problem — the profile was. Only `chrome131` was blocklisted.

> **Diagnostic that nails it:** if a Fastly 403 persists on a confirmed-good residential IP, run the profile ladder through that SAME IP before concluding anything about the proxy. On Apify, the proxy is unreachable from outside the platform (curl error 56 CONNECT), so iterate the ladder via an in-actor cloud probe or the `waf-probe` actor (input-driven: `{targets, profiles, ladder:true, proxyConfiguration}`).

### Tier 2 — JavaScript clearance challenge  (200, ~3 KB interstitial)

Signature: **HTTP 200** but a tiny (~3 KB) CSP-locked HTML shell that loads assets from **`/_fs-ch-<id>/`** and sets a challenge-STATE cookie **`_fs_ch_st_<id>`** (`Max-Age=10`). The real content never arrives over HTTP. This is Fastly's active JS Bot-Management challenge — the client must execute JS to compute a clearance token.

**No HTTP library clears this** — verified against Houzz with **11 profiles** (curl_cffi chrome131/124/116/99_android/safari17_0/safari18_0/edge101 + primp chrome_131/firefox_135/safari_18/chrome_130), Googlebot & Bingbot UA, session cookie-retry, and the site's ajax endpoint — **all returned the same 3 KB `_fs_ch_` interstitial.**

**Cookie transplant does NOT work for Fastly Tier-2** (this is the key difference from AWS WAF). A browser (Camoufox via scrapling `StealthyFetcher`) clears it (200, real ~1.3 MB content, harvests a full `_fs_ch_st_*` token), **but replaying those cookies over curl_cffi OR primp (even Firefox JA3 + matching UA) still returns the 3 KB challenge** — the Fastly clearance is bound to the solving browser's live session/fingerprint, not a portable token. See the caveat in [`skills/browser-cookie-transplant`](../skills/browser-cookie-transplant/SKILL.md).

**Fix:** the browser must do the actual content fetches (Camoufox / `StealthyFetcher`), reusing one warm context for the whole crawl. This is the one genuinely browser-required tier — but only reach it AFTER proving Tier-1 (the ladder) doesn't apply.

**Verified (Houzz, 2026-07-09):** Tier-2. HTTP-only impossible; `StealthyFetcher(headless=True, network_idle=True)` → 200 + full contractor directory. Data is rich SSR once through.

## Decision flow

```
Fastly detected (Server: Varnish / X-Served-By: cache-*)
        │
        ├── 403 + tiny body, no JS  → TIER 1: rotate profile (chrome124/safari17_0/edge101/primp)
        │                              NOT a browser, NOT (only) the proxy.
        │
        └── 200 + ~3KB /_fs-ch-/ shell, _fs_ch_st_ cookie → TIER 2: JS challenge.
              HTTP-only impossible (ladder won't help); cookie transplant won't help.
              → Camoufox/StealthyFetcher does the fetching.
```

## What does NOT work

- ❌ Blaming the proxy on a Tier-1 403 without running the profile ladder first (the Rightmove mistake — cost several wrong "needs premium residential" conclusions).
- ❌ `chrome131` against Fastly Tier-1 (blocklisted; use chrome124+).
- ❌ Cookie transplant (browser→HTTP) for Tier-2 `_fs_ch_` — the clearance is session-bound, not a portable token (works for AWS WAF, not Fastly).
- ❌ Googlebot/Bingbot UA for Tier-2 — Fastly serves the challenge to crawler UAs too.
- ❌ Warm-up GET / session cookie-retry for Tier-2 — the `_fs_ch_st_` state cookie (Max-Age 10) is not a clearance cookie.

## Caveats

- Some sites migrate their data layer under Fastly independently of the WAF tier — e.g. Rightmove moved search to Next.js `__NEXT_DATA__` and detail to `window.__PAGE_MODEL` (a `flatted` index-array). Solve the WAF first, then re-inspect the data container; don't assume the old anchors.
- Tier can differ per-path on the same host (homepage Tier-0/open, listing pages Tier-1/2).
- Fastly rotates which JA3s are blocklisted; keep the ladder, don't pin one profile forever.

## Verified production matrix

| Target | Tier | Bypass | Notes |
| --- | --- | --- | --- |
| Rightmove (UK) | 1 (JA3 block) | `curl_cffi chrome124` + UK residential | chrome131=403 even on real UK resi; data in `__NEXT_DATA__` / `window.__PAGE_MODEL` (flatted) |
| Houzz | 2 (JS challenge) | Camoufox / `StealthyFetcher` | HTTP-only impossible; transplant proven not to work |

## See also
- [`skills/tls-fingerprinting`](../skills/tls-fingerprinting.md) — the profile ladder mechanics (Tier 1)
- [`skills/browser-cookie-transplant`](../skills/browser-cookie-transplant/SKILL.md) — Tier-2 note (why transplant fails on Fastly)
- [`playbooks/waf-triage.md`](../playbooks/waf-triage.md) — ladder-before-browser step
- [`lessons-learned.md`](../lessons-learned.md) — "don't escalate to a browser after one profile"
