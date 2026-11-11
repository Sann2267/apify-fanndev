# Cloudflare Bot Management

> **Most aggressive Cloudflare deployments fingerprint JA3/JA4 in addition to header signals.** Plain Python HTTP gets 403/`cf-mitigated: challenge`. The right TLS profile + UA combo passes silently — no CAPTCHA, no JS challenge.

## Diagnosis (how to tell it's Cloudflare)

- Response headers contain `server: cloudflare` or `cf-ray: <ID>-XXX`
- Response headers contain `cf-mitigated: challenge` on a 403
- Body contains `Just a moment...`, `challenge-platform`, or `_cf_chl_` JS
- 200 with body `<title>Attention Required! | Cloudflare</title>` (legacy)

## Bypass strategies (in order of preference)

### Strategy 1: `curl_cffi firefox133` — wins where Chromium fails

This is the most surprising production discovery: **`curl_cffi` Chromium profiles get `cf-mitigated: challenge` on Capterra**, but `firefox133` passes cleanly. Same IP, same headers — only the JA3 fingerprint differs.

```python
from curl_cffi.requests import AsyncSession

session = AsyncSession(impersonate="firefox133", timeout=30)
r = await session.get("https://www.capterra.com/voip-software/")
# 200 OK, no challenge
```

**Verified working against:**
- Capterra (B2B suite)
- Some lighter Cloudflare deployments

**Verified BLOCKED (all return `cf-mitigated: challenge` 403):**
- `chrome120`
- `chrome131`
- `chrome133a`

### Strategy 2: `curl_cffi chrome145` — current Cloudflare-baseline winner

For the bulk of Cloudflare sites where Firefox is also blocked or where the site fingerprints Firefox profiles:

```python
session = AsyncSession(impersonate="chrome145", timeout=30)
```

**Verified working against:**
- Financial Times (combined with `User-Agent: Googlebot-News` → Zephr paywall flips to GRANTED)
- IBD (Investor's Business Daily) — combined with `scrapling`
- Investing.com (combined with `primp` random profile)
- Many tier-1 news sites

### Strategy 3: `primp` random profile — DataDome-flavored Cloudflare bypass

For Cloudflare-and-DataDome stacked sites or PerimeterX/CF combos:

```python
import primp

client = primp.Client(impersonate="chrome_133", verify=False)
r = client.get("https://stockx.com/")
```

`primp` profile naming uses underscores (`chrome_133`), `curl_cffi` uses no separator (`chrome133`). Don't copy-paste profile names across libraries.

### Strategy 4: `scrapling` with Safari profiles — niche but works

For Cloudflare deployments paired with PerimeterX:

```python
from scrapling.fetchers import Fetcher

f = Fetcher()
r = f.get("https://www.bloomberg.com/...", impersonate="safari2601", stealthy_headers=True)
```

## Specific paywall + Cloudflare combos

### Financial Times (Zephr)
- Cloudflare gates the edge, Zephr gates the body.
- **The trick:** UA `Googlebot-News` flips Zephr to `consent.gate: GRANTED`.
- Combined with `curl_cffi chrome145` → full article extraction.

```python
headers = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot-News/1.0; +http://www.google.com/bot.html)",
}
r = await session.get(ft_url, headers=headers, impersonate="chrome145")
```

### Investor's Business Daily (IBD)
- Cloudflare + PerimeterX layered.
- `scrapling` clears PX at the WordPress REST endpoint:

```python
from scrapling.fetchers import Fetcher
r = Fetcher().get(f"https://www.investors.com/wp-json/wp/v2/posts?slug={slug}", impersonate="chrome145")
```

### StockX
- Cloudflare with bot-management add-on.
- Hybrid `primp` / `curl_cffi` rotation with profile retry on 403/407/429/503.
- Profile name asymmetry: `primp safari_17_5` vs `curl_cffi safari18_0`.

## Headers that matter (beyond TLS)

Cloudflare also inspects:
- `User-Agent` — match the library's impersonation
- `Accept-Language` — must be present
- `Accept` — full browser value
- `Accept-Encoding` — let the library set this (`gzip, deflate, br, zstd` for modern Chrome)
- `sec-ch-ua-*` family — set automatically by `curl_cffi impersonate=`
- `sec-fetch-*` family — `dest/mode/site/user` based on context (navigate vs cors)

```python
# DON'T override Accept-Encoding manually — breaks fingerprint
session.headers["Accept-Encoding"] = "gzip"   # WRONG, real Chrome 131 sends "gzip, deflate, br, zstd"

# DO let curl_cffi set it via impersonate=
session = AsyncSession(impersonate="chrome131")
# now session.headers["accept-encoding"] is the canonical Chrome value
```

## When you genuinely cannot pass

Some Cloudflare deployments add JS challenges (`cf_chl_jschl_tk`) that require executing browser JS. If `curl_cffi firefox133`, `chrome145`, AND `scrapling safari2601` all fail with `cf-mitigated`:

1. Verify it's actually Cloudflare (not PerimeterX masquerading) — check `cf-ray` header.
2. Try residential proxy (datacenter IP may be on a blocklist independent of TLS).
3. Last resort: Camoufox (Firefox stealth). Document the cost increase and ask user before adopting.

**No-captcha-solver policy:** If Cloudflare serves a captcha, mark the URL failed and continue. Don't integrate 2captcha/anti-captcha unless user explicitly asks.

## Caveats

- **Cloudflare's TLS fingerprint blocklist updates weekly.** A profile that works today may be blocklisted next month. Maintain a smoke-test suite for top targets.
- **`cf-mitigated: challenge` vs `cf-mitigated: managed_challenge`** — the former is permanent block, the latter would be solvable by a browser (don't try; just rotate).
- **Don't add fake `cf-ipcountry` or `cf-connecting-ip` headers** — Cloudflare strips these from incoming requests. Spoofing them does nothing.
- **HTTP/3 upgrade may help OR hurt** — some Cloudflare zones fingerprint h2 specifically; h3 has less observed data. Most impersonation libs disable h3 by default; verify.
- **`http2: true` is REQUIRED** for modern Cloudflare. HTTP/1.1 requests are immediately challenged.

## Verified production matrix

| Target | Library | Profile | Extra |
| --- | --- | --- | --- |
| Capterra | curl_cffi | firefox133 | RESIDENTIAL preferred |
| FT.com | curl_cffi | chrome145 | UA Googlebot-News |
| Investing.com | primp | random | — |
| IBD | scrapling | (auto) | WP REST endpoint |
| StockX | curl_cffi / primp | safari18_0 / safari_17_5 rotate | profile rotate on 403 |
| Most news (CNBC, BBC, Guardian) | httpx | n/a | no Cloudflare protection on article path |

## See also
- [`skills/tls-fingerprinting.md`](../skills/tls-fingerprinting.md)
- [`anti-bot/datadome.md`](datadome.md) (when Cloudflare and DataDome are stacked)
- [`anti-bot/perimeterx.md`](perimeterx.md) (when CF + PX layered)
