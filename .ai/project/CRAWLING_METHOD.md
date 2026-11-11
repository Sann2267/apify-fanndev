# Crawling method — cross-platform patterns

Generalized patterns. For per-actor specifics, read the
`CRAWLING_METHOD.md` inside each scraper folder.

## Transport layer

```
                            ┌─────────────────────────────────┐
  No proxy (local test) ───►│ primp.Client(impersonate=...)   │── Aliyun-friendly
                            │   chrome_146, firefox_148, ...  │
                            └─────────────────────────────────┘
                            ┌─────────────────────────────────┐
  With proxy (Apify) ──────►│ curl_cffi.requests.Session(     │── correct proxy auth
                            │   impersonate=chrome131, ...)   │
                            └─────────────────────────────────┘
```

- `primp` profile names use underscores (`chrome_146`, `firefox_148`).
- `curl_cffi` profile names use no underscore (`chrome131`, `safari18_0`).
- The `make_client()` factory in each `fingerprint.py` switches between
  them based on whether a proxy URL is passed.
- **`primp` valid names are pinned to the installed version.** On
  `primp 1.2.2` the only valid templates are `chrome_144/145/146`,
  `firefox_140/146/147/148`, `edge_144/145/146`, `safari_26`. An unknown
  name does not raise — it warns once and silently serves a `random` JA3.
  See [PROBLEMS.md](PROBLEMS.md#primp-stale-profile-names-silently-fall-back-to-random-2026-05-30).

## Data-island extraction pattern

Most modern e-commerce sites embed their initial state as a JS variable
in the HTML. The pattern is:

```python
def _walk_balanced(text, start, open_ch="{", close_ch="}"):
    """Balanced-brace walker that handles JS strings + escapes."""
    depth = 0; in_str = False; escape = False; str_char = None
    for j in range(start, len(text)):
        ch = text[j]
        if in_str:
            if escape: escape = False; continue
            if ch == "\\": escape = True; continue
            if ch == str_char: in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True; str_char = ch; continue
        if ch == open_ch: depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                try: return json.loads(text[start:j + 1])
                except (ValueError, json.JSONDecodeError): return None
    return None
```

| Platform | Variable | Path to items |
|---|---|---|
| AliExpress wholesale | `_init_data_= { data: {...} }` (data is JS, not JSON, so we skip to inner `{`) | `data.root.fields.mods.itemList.content` |
| Walmart | `__NEXT_DATA__` | `props.pageProps.initialData.searchResult.itemStacks[0].items` |
| eBay | inline JSON in `<script>` blocks | varies |
| Etsy | `__APP_INITIAL_STATE__` | varies |
| StockX | Apollo cache + REST JSON via signed GraphQL/REST hybrid | varies |

## Signed API patterns

### AliExpress MTOP (`acs.aliexpress.com/h5/<api>/<version>/`)

```
sign = md5(f"{h5_tk_token}&{timestamp_ms}&{app_key}&{data_str}")
```

- `h5_tk_token` is the 32-char hex prefix of the `_m_h5_tk` cookie value
  (cookie is `{token}_{timestamp}`).
- `app_key = 12574478` (extracted from the AliExpress React bundle).
- Response is JSONP-wrapped: `mtopjsonp1({...})` — strip the wrapper.
- **In 2026** the `acs.aliexpress.com` gateway is gated by Baxia
  (`_baxia_sec_cookie_.tfstk` is required, JS-only). Empirically blocked.

### shoprenderview.aliexpress.com (UNSIGNED — this is the win)

```
GET https://shoprenderview.aliexpress.com/async/execute
    ?componentKey=allitems_choice
    &SortType=bestmatch_sort
    &page=1&pageSize=30
    &country=US&site=glo
    &sellerId=<id>&groupId=-1
    &currency=USD&locale=en_US&buyerId=0
    &callback=jsonp_<ms>
```

- Returns `jsonp_<ms>({"code":0,"result":{"products":{"data":[...]}}})`.
- **Page 1 reliably succeeds** from residential IPs. Cold IPs sometimes
  get a Baxia `x5secdata` interstitial; retry with a fresh proxy.
- **Page 2+** flaky — proxy rotation + warm-up via `/store/{id}` recovers.
- Per-product fields include `averageStar`, `averageStarRate`,
  `feedbacks` (review COUNT, not text), `orders`, `sales`,
  `prices.piecePrice`, `prices.promotionPiecePrice`,
  `promotionDiscount`, `productTags`, `atmosphere`,
  `pcDetailUrl`, `image640Url`.

## WAF marker registry

| Marker | WAF | Sites |
|---|---|---|
| `punish.html` | Aliyun | AliExpress, Alibaba |
| `_____tmd_____` | Baxia | AliExpress, Alibaba |
| `baxia-manager` | Baxia | AliExpress, Alibaba |
| `sufei-punish` | Sufei | Alibaba |
| `x5secdata` | Baxia v5 | AliExpress |
| `window._config_ = {"action":"captcha"` | Aliyun v5 captcha | AliExpress |
| `FAIL_SYS_USER_VALIDATE` / `RGV587_ERROR` | Baxia MTOP gate | AliExpress (MTOP gateway only) |
| `FAIL_SYS_TOKEN_EMPTY` | MTOP token rejection | AliExpress (datacenter IPs) |
| `_pxhd` script + PX challenge body | PerimeterX | Walmart |
| Generic 200 + body < 5 KB + no expected marker | thin-shell challenge | all |

## SEO crawler UA escape hatch

For Aliyun-gated SEO-indexed pages (search/category results), pairing a
real Chrome TLS fingerprint with a Bingbot/Googlebot User-Agent
**bypasses** the punish.html challenge on flagged IPs.

```python
# In aliexpress-search-scraper/src/main.py:
bot_ua_index = (i // 2) if i % 2 == 1 else None  # alternate every other attempt
```

The WAF allow-lists SEO crawler UAs because Aliyun does not want to
break Alibaba's SEO ranking. **Only works on SEO-indexed surfaces**
(search, category) — does NOT work on MTOP gateway or PDP API.

## Block recovery loop

```python
for i in range(max_attempts):
    profile = PROFILES[i % len(PROFILES)]
    px = await proxy_cfg.new_url() if proxy_cfg else None  # rotate proxy IP
    try:
        r = await fetch(url, profile=profile, proxy=px)
    except Exception:
        continue
    if is_blocked(r.status_code, r.text):
        continue  # rotate
    return r
```

Critical: `proxy_cfg.new_url()` must be called inside the retry loop
to get a fresh IP. Reusing the same IP across retries defeats the
rotation.

## Output schema discipline

Every actor produces a JSON row with **stable field names**, even on
error. Pattern:

```python
{
  "url": <input_url>,
  "scrapedAt": "<iso8601>",
  ...domain_fields...,
  "error": "CSR_SHELL" | "BLOCKED_AFTER_RETRIES" | None,
  "note": "<human-readable explanation>"  # only when error is set
}
```

This makes downstream joins idempotent: every input maps to exactly
one row regardless of WAF state.
