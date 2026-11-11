# AWS WAF (Bot Control / `AwsWafIntegration` JS challenge)

> **AWS WAF's Bot Control serves an active JavaScript challenge, not just a TLS gate.** The first response is an interstitial (usually HTTP `202`, sometimes `405`) whose body ships an obfuscated `AwsWafIntegration` / `goku` script that computes a token and sets an `aws-waf-token` cookie. A plain HTTP client — however perfect its JA3 — can't execute that JS, so it loops on the challenge forever. The bypass is to solve it once in a real browser and replay the cookie over HTTP.

## Diagnosis (how to tell it's AWS WAF)

- Response status is **`202`** (challenge) or **`405`** on requests that should return HTML.
- Body head contains `AwsWafIntegration`, `window.gokuProps`, or a script from `token.awswaf.com` / `*.awswaf.com`.
- A cookie named `aws-waf-token` is required for real content.
- Sometimes headers `x-amzn-waf-action` or `server` fronted by CloudFront (`x-amz-cf-id`, `via: ... cloudfront`).
- The homepage may load but every listing/API path returns the 202 interstitial.

```python
def is_aws_waf(resp) -> bool:
    return resp.status_code in (202, 405) or "AwsWafIntegration" in resp.text[:2000]
```

## Bypass strategies (in order of preference)

### Strategy 1: TLS fingerprint first (cheap — try before a browser)

A minority of AWS WAF deployments (rule-based, no JS challenge) pass with a correct fingerprint alone:

```python
from curl_cffi import requests as cc
r = cc.get(url, impersonate="chrome131", headers={"accept-language": "en-US,en;q=0.9,id;q=0.8"})
```

If this returns real HTML (not a 202/`AwsWafIntegration` body), you're done. If it loops on the challenge → Strategy 2.

### Strategy 2: browser solves once → transplant cookies to HTTP (the reliable path)

This is the production bypass for the JS-challenge variant. A headless browser executes the challenge, earns the `aws-waf-token` cookie, and that cookie is poured into a plain HTTP session (cloudscraper / curl_cffi) for the whole crawl. See the full pattern in [`skills/browser-cookie-transplant`](../skills/browser-cookie-transplant/SKILL.md).

```python
import cloudscraper
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")   # NOT "HeadlessChrome"

def bootstrap(scraper, url):
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA)
        try:
            pg = ctx.new_page()
            for attempt in range(1, 4):
                pg.goto(url, wait_until="domcontentloaded", timeout=60000)
                try:
                    pg.wait_for_selector("div.snippet", timeout=25000)   # real content selector
                    break
                except Exception:
                    pg.wait_for_timeout(3000 * attempt)
            for c in ctx.cookies():
                scraper.cookies.set(c["name"], c["value"], domain=c["domain"])
        finally:
            ctx.close(); b.close()

scraper = cloudscraper.create_scraper(browser={"custom": UA})
bootstrap(scraper, url)
resp = scraper.get(f"{url}?page=1", headers={"user-agent": UA, "referer": url})
if is_aws_waf(resp):        # cookie expired mid-crawl → solve again, once
    bootstrap(scraper, url)
    resp = scraper.get(f"{url}?page=1", headers={"user-agent": UA, "referer": url})
resp.encoding = "utf-8"     # AWS-WAF'd sites often omit charset → fixes mangled "m²"
```

## Headers / UA that matter

- **UA must NOT contain "HeadlessChrome"** — AWS WAF flags it immediately. Force one real desktop UA on BOTH the browser context and the HTTP session; the `aws-waf-token` is bound to the UA that earned it.
- Send full navigation headers on HTML GETs: `accept`, `accept-language`, `sec-fetch-dest: document`, `sec-fetch-mode: navigate`, `sec-fetch-site: same-origin`, `upgrade-insecure-requests: 1`, and a `referer` of the base URL.
- Copy each cookie **with its `domain`** so it replays on subdomains / API hosts.

## When you genuinely cannot pass

1. Confirm it's AWS WAF (202 + `AwsWafIntegration`) and not CloudFront rate-limiting (`x-amzn-errortype`, 403 with no challenge body).
2. If the browser challenge itself won't resolve in 3 attempts, the deployment may add a CAPTCHA action. **No-captcha-solver policy:** mark the URL failed and continue; don't integrate 2captcha unless the user explicitly asks.
3. Datacenter IP may be independently blocklisted — try a residential proxy before concluding the fingerprint/cookie is wrong.

## Caveats

- **`wait_until="domcontentloaded"` fires on the challenge page too.** Gate "solved" on a real-content selector, or you'll transplant worthless challenge-page cookies.
- **Token is short-lived.** Expect a mid-crawl re-challenge; re-bootstrap once and retry — don't abandon the run. Re-bootstrap idempotently (only after `is_aws_waf()`), never before every request.
- **Snap Chromium breaks the browser step on Linux servers** (AppArmor confinement). Use `.deb` google-chrome or Playwright's bundled Chromium and point the engine at it (`SNIFFER_CHROME_PATH=/usr/bin/google-chrome`); add `--no-sandbox --disable-dev-shm-usage` on headless servers.
- **Running the whole crawl in a browser works but is 10–50× slower.** Use the browser only for the challenge; extract over HTTP.
- Once through, the data itself is usually clean SSR — parse it via [`skills/schema-org-jsonld-extraction`](../skills/schema-org-jsonld-extraction/SKILL.md).

## Verified production matrix

| Target | Variant | Bypass | Extra |
| --- | --- | --- | --- |
| lamudi.co.id | JS challenge (`AwsWafIntegration`, HTTP 202) | Playwright solve once → cloudscraper cookie replay | UA ≠ HeadlessChrome; re-bootstrap mid-crawl; `resp.encoding="utf-8"` |

## See also
- [`skills/browser-cookie-transplant`](../skills/browser-cookie-transplant/SKILL.md) — the solve-once/replay-many mechanics
- [`skills/schema-org-jsonld-extraction`](../skills/schema-org-jsonld-extraction/SKILL.md) — parse the HTML once through
- [`skills/tls-fingerprinting`](../skills/tls-fingerprinting/SKILL.md) — Strategy 1 (try before a browser)
- [`skills/cookie-warmup`](../skills/cookie-warmup/SKILL.md) — same-client warm-up for non-JS challenges
- [`playbooks/waf-triage.md`](../playbooks/waf-triage.md) — identify which WAF is blocking you
