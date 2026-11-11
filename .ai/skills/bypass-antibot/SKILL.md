---
name: bypass-antibot
description: "Concrete per-WAF tactics for getting past specific anti-bot systems (Cloudflare and others) by symptom, with curl_cffi/TLS examples. Use when a scraper hits a 403, a challenge page, or a cf-ray header and needs a targeted workaround."
---

# Skill: Bypassing Anti-Bot Protections

## Cloudflare (FT, some others)

**Symptom**: 403 or challenge page with `cf-ray` header.

**Solution**: Use `curl_cffi` with Chrome TLS fingerprint.

```python
import curl_cffi.requests as cfreq

def _cffi_fetch(url, impersonation="chrome145"):
    resp = cfreq.get(
        url,
        impersonate=impersonation,
        headers={"User-Agent": "...", "Referer": "https://www.google.com/"},
        timeout=30,
        allow_redirects=True,
    )
    return resp if resp.status_code == 200 else None
```

**Working impersonations for FT**: `chrome145` (confirmed working as of Apr 2026)
**Failed**: `httpx`, `requests`, all standard HTTP clients

---

## DataDome (Reuters, Forbes)

**Symptom**: 401 (Reuters) or 403 (Forbes) with `X-Datadome` response header.

**Solution**: Use `primp` - Python bindings for the Rust `rquest` library.

```python
import primp

def _primp_fetch(url, impersonation="chrome_126"):
    client = primp.Client(impersonate=impersonation, follow_redirects=True, timeout=30)
    resp = client.get(url)
    return resp if resp.status_code == 200 else None
```

**Working impersonations**: `chrome_100` through `chrome_133`, `firefox_109` through `firefox_133`, `safari_15` through `safari_18`, `okhttp_4_9`, `okhttp_4_10`

**Blocked impersonations**: `chrome_133_0`, `safari_18_2`, `okhttp_3_9`, `okhttp_5`

**Why primp works**: Rust TLS stack produces a different TLS fingerprint (JA3/JA4) that DataDome hasn't flagged. curl_cffi uses Python's SSL which DataDome recognizes.

**Fallback chain**:
```python
async def _primp_fetch(url, impersonation="chrome_126"):
    for imp in ["chrome_126", "firefox_133", "chrome_131", "safari_18"]:
        try:
            client = primp.Client(impersonate=imp, follow_redirects=True, timeout=30)
            resp = client.get(url)
            if resp.status_code == 200:
                return resp
        except Exception:
            continue
    return None
```

---

## PerimeterX / PX (Bloomberg)

**Symptom**: 403 from every IP type including residential.

**Solution**: use library scrapling with tls impersonation

---

## Soft Paywalls

### Fortune pattern
Fortune wraps article content in `<div class="paywall">`. Standard `clean_html()` strips it.

```python
body = soup.select_one("article")
if body:
    paras = [p.get_text(strip=True) for p in body.find_all(["p","h2","h3","blockquote"])
             if len(p.get_text(strip=True)) > 20]
    content = "\n\n".join(paras)
```

### SCMP pattern
SCMP full article is in NEXT_DATA:
```python
nd = extract_next_data(html)
article = deep_get(nd, "props.pageProps.payload.data.article") or {}
content = article.get("body", {}).get("text", "")
```

### NYTimes pattern
NYT article body in NEXT_DATA:
```python
nd = extract_next_data(html)
# Deep search for articleBody key
```

---

## RSS Feed Access

Most sites' RSS feeds are served from different domains/CDNs and don't inherit the site's bot protection:
- Reuters RSS (`feeds.reuters.com`) - no DataDome
- Forbes RSS (`forbes.com/news/feed/`) - may or may not be protected (standard httpx usually works)
- FT RSS (`ft.com/?format=rss`) - no Cloudflare on RSS endpoint

Always try standard `httpx` for RSS before using primp/curl_cffi.
