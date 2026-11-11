---
name: browser-cookie-transplant
description: How to beat a JS-challenge WAF (AWS WAF, Incapsula/Imperva, some Cloudflare/DataDome interstitials) by solving the challenge ONCE in a headless browser (Playwright/nodriver) and transplanting the resulting cookies onto a plain HTTP session (cloudscraper/curl_cffi/requests) that does the actual bulk crawl. Use this skill whenever plain HTTP returns a challenge you can't reproduce with TLS spoofing alone — HTTP 202/405 on every request, body markers `AwsWafIntegration` / `window.gokuProps` / `token.awswaf.com`, an `aws-waf-token` cookie requirement, "Just a moment" that a warm-up GET can't clear, or Imperva `___utmvc` / `reese84`. Consult this for the solve-once-replay-many pattern, the mandatory non-"HeadlessChrome" UA, cookie copy across domains, the `is_challenge()` detector, mid-crawl re-bootstrap on cookie expiry, and why this beats running the whole crawl in a browser. Proven on lamudi.co.id (AWS WAF).
---

# Browser Cookie Transplant (solve-once, replay-many)

> **Some challenges can't be spoofed — only solved.** When a WAF runs a JS challenge (AWS WAF `goku`, Imperva, hard Cloudflare interstitials), no TLS profile or header set alone will pass, because the gate is *JavaScript execution*, not the ClientHello. The fix: let a real headless browser execute the challenge once, steal the trust cookies it earns, and pour them into a fast plain-HTTP session for the whole crawl. One slow browser launch buys thousands of cheap HTTP requests.

## Problem

[`tls-fingerprinting`](../tls-fingerprinting/SKILL.md) and [`cookie-warmup`](../cookie-warmup/SKILL.md) cover challenges that a correctly-fingerprinted HTTP client can clear by itself. But a class of WAFs serves an **active JS challenge**: the first response is an interstitial (often HTTP `202`/`405`) whose body ships obfuscated JavaScript that computes a token and sets a cookie. A plain HTTP client — however perfect its JA3 — can't run that JS, so it loops on the challenge forever.

Running the *entire* crawl in Playwright works but is 10–50× slower and memory-heavy: every page pays browser render + navigation cost. You don't need the browser for data extraction — you need it only for the one thing HTTP can't do: **execute the challenge**.

## Solution: bootstrap in a browser, crawl over HTTP

### Step 1: solve the challenge in a headless browser, harvest cookies

```python
import cloudscraper
from playwright.sync_api import sync_playwright

# AWS WAF instantly flags the default headless UA (it literally contains
# "HeadlessChrome"). Force a normal desktop UA on BOTH the browser and the
# HTTP session so the cookies stay valid when replayed.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

def bootstrap_waf(scraper, url: str) -> bool:
    """Solve the JS challenge in a real browser, copy its cookies to the HTTP session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)
        try:
            page = ctx.new_page()
            passed = False
            for attempt in range(1, 4):
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                try:
                    page.wait_for_selector("div.snippet", timeout=25000)   # real content = solved
                    passed = True
                    break
                except Exception:
                    page.wait_for_timeout(3000 * attempt)                  # challenge still resolving
            for c in ctx.cookies():                                        # transplant the trust cookies
                scraper.cookies.set(c["name"], c["value"], domain=c["domain"])
            return passed
        finally:
            ctx.close(); browser.close()
```

**Wait for real content, not navigation.** `wait_until="domcontentloaded"` returns on the *challenge* page too. The reliable "solved" signal is a content selector that only exists on the real page (`div.snippet` here). Retry with growing backoff — the challenge sometimes needs a second pass.

### Step 2: detect the challenge on the HTTP side

```python
def is_challenge(resp) -> bool:
    # AWS WAF: 202/405 status OR the integration script in the body head
    return resp.status_code in (202, 405) or "AwsWafIntegration" in resp.text[:2000]
```

Add other vendors' markers as needed: `window.gokuProps`, `token.awswaf.com`, Imperva `___utmvc`/`reese84`, Cloudflare `challenge-platform`.

### Step 3: crawl over HTTP, re-bootstrap when the cookie expires

Trust cookies are short-lived. When a mid-crawl request trips the challenge again, re-solve once and retry — don't abandon the run:

```python
def crawl(url, max_pages, delay):
    scraper = cloudscraper.create_scraper(browser={"custom": UA})
    bootstrap_waf(scraper, url)
    NAV = {"user-agent": UA, "accept-language": "en-US,en;q=0.9,id;q=0.8",
           "sec-fetch-dest": "document", "sec-fetch-mode": "navigate",
           "sec-fetch-site": "same-origin", "upgrade-insecure-requests": "1"}
    rows = []
    for page in range(1, max_pages + 1):
        target = f"{url}?page={page}"
        resp = scraper.get(target, headers={**NAV, "referer": url})
        if is_challenge(resp):                        # cookie expired mid-crawl
            bootstrap_waf(scraper, url)               # solve again, once
            resp = scraper.get(target, headers={**NAV, "referer": url})
        resp.encoding = "utf-8"                        # WAF'd sites often omit charset
        rows += parse_cards(resp.text)                 # → schema-org-jsonld-extraction
        time.sleep(delay)
    return rows
```

## Pattern: async equivalent (nodriver / Playwright async)

The same shape works with an async browser and an async HTTP client. Bootstrap once at handler start, replay cookies on every `__get`, and re-bootstrap inside `__get` when `is_challenge()` fires. (This is exactly the production `Lamudi` controller's `__bootstrap_session` → `__get` flow.)

## Caveats

- **UA must match and must NOT say "HeadlessChrome".** The transplanted cookie is often bound to the UA that earned it. Use one real desktop UA string for the browser context AND the HTTP session. Mismatch → instant re-challenge.
- **Copy cookies with their domain.** Set each cookie with `domain=c["domain"]` so it replays on subdomains/API hosts, not just the exact page host.
- **`wait_until` is not "solved".** Gate on a content selector, not on load state, or you'll transplant challenge-page cookies that are worthless.
- **Prefer the cheapest tier that works.** Try [`tls-fingerprinting`](../tls-fingerprinting/SKILL.md) + [`cookie-warmup`](../cookie-warmup/SKILL.md) first. Only reach for a browser when the challenge is genuinely JS-gated (202/405 loop, `AwsWafIntegration`). A browser per crawl is a real cost.
- **Snap-packaged Chromium breaks nodriver/Playwright** on Linux servers (AppArmor confinement blocks the temp profile dir). Use the `.deb` google-chrome or Playwright's bundled Chromium; point the engine at it explicitly (`SNIFFER_CHROME_PATH=/usr/bin/google-chrome`). See [`playbooks/sniff-fallback-workflow.md`](../../playbooks/sniff-fallback-workflow.md).
- **Headless servers need `--no-sandbox` + `--disable-dev-shm-usage`** (root/container) or Chrome won't launch.
- **Set `resp.encoding = "utf-8"`** — WAF-fronted sites frequently omit the charset, so `requests`/cloudscraper fall back to ISO-8859-1 and mangle non-ASCII (e.g. `m²`).
- **Re-bootstrap is idempotent, not per-request.** Solve on session start and only again after `is_challenge()` — never before every call.

## When transplant does NOT work: Fastly `_fs_ch_` (session-bound clearance)

**Not every JS challenge yields a portable cookie.** Transplant works when the WAF issues a *token* cookie that is valid for any client presenting it (AWS WAF `aws-waf-token`, Imperva `reese84`). It **fails** when the clearance is bound to the solving browser's live session/fingerprint.

**Verified failure — Houzz / Fastly Tier-2 (2026-07-09):** Camoufox (`StealthyFetcher`) clears the `/_fs-ch-/` challenge (200, 1.3 MB real content, harvests a full `_fs_ch_st_*` token), but replaying those cookies over `curl_cffi` (chrome124/131/99_android) **and** `primp` (firefox_135/133 — real Firefox JA3, matching UA) **still returns the 3 KB `_fs_ch_` interstitial**. The Fastly clearance is not a portable token — the browser has to do the actual content fetches (reuse one warm context). See [`anti-bot/fastly.md`](../../anti-bot/fastly.md) Tier 2.

**Rule of thumb:** transplant-then-probe once before committing. Solve in the browser, replay the cookie over HTTP, and check for real content. If HTTP still gets the challenge, the cookie is session-bound → the browser must fetch (don't burn cycles trying more HTTP profiles).

## Where used

- **lamudi.co.id** (AWS WAF `AwsWafIntegration`, HTTP 202) — Playwright solves once, cloudscraper replays the cookies for every SERP + detail page; re-bootstrap on mid-crawl challenge. Data then parsed via [`schema-org-jsonld-extraction`](../schema-org-jsonld-extraction/SKILL.md). **Transplant works** (portable `aws-waf-token`).
- **Houzz** (Fastly `_fs_ch_`, HTTP 200 3KB interstitial) — transplant **does NOT work** (session-bound); browser must fetch. Counter-example above.
- Applies to Imperva/Incapsula (`___utmvc`, `reese84`) and hard Cloudflare interstitials that a warm-up GET can't clear.

## See also
- [`anti-bot/aws-waf.md`](../../anti-bot/aws-waf.md) — AWS WAF vendor diagnosis + bypass
- [`cookie-warmup`](../cookie-warmup/SKILL.md) — same-client warm-up (try first; lighter than a browser)
- [`tls-fingerprinting`](../tls-fingerprinting/SKILL.md) — clear challenges without a browser when possible
- [`schema-org-jsonld-extraction`](../schema-org-jsonld-extraction/SKILL.md) — parse the HTML once you're through
- [`playbooks/waf-triage.md`](../../playbooks/waf-triage.md) — identify which WAF is blocking you
