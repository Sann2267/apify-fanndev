# Problems — known issues and their roots

A catalog of every non-obvious blocker hit during development. Each
entry describes the symptom, the root cause, and the resolution (or
why none exists).

---

## primp stale profile names silently fall back to `random` (2026-05-30)

**Symptom.** All `primp`-transport actors (StockX, Alibaba, eBay, Etsy,
and the no-proxy path of AliExpress/Walmart) were WAF-blocked more often
than expected even on golden-path targets. Running any `test_local.py`
printed, once, on stderr:
`Impersonate 'chrome_131' does not exist, using 'random'`.

**Root cause.** The machine has **`primp 1.2.2`**, whose compiled
impersonation templates only cover a narrow modern range —
`chrome_144/145/146`, `firefox_140/146/147/148`, `edge_144/145/146`,
`safari_26`. Every `fingerprint.py` had been written against an older
naming era (`chrome_131`, `chrome_128`, `firefox_135`, `firefox_133`,
`safari_17_5`, `edge_131`) — **none of which exist in 1.2.2**. primp does
not raise on an unknown name; it warns **once per process** (a log-once
guard) and then serves a **random** JA3 for every request. A random
fingerprint is exactly what DataDome/Akamai/Aliyun block, so the whole
suite was effectively running with no impersonation.

The once-per-process warning is a trap: probing many names in a single
Python process makes every name after the first look valid. You must
spawn a **fresh process per name** to test validity.

**Resolution.** Remapped all stale `primp` names across 15 `fingerprint.py`
files to the valid 1.2.2 set (`safari_17_5→safari_26`,
`chrome_131→chrome_146`, `chrome_128→chrome_145`, `firefox_135→firefox_148`,
`firefox_133→firefox_146`, `edge_131→edge_146`). curl_cffi profile names
(`chrome131`, `safari18_0` — no underscore) were already correct and left
untouched. Local WAF posture is unchanged for DataDome/Akamai targets
(eBay, Etsy still need residential — they block datacenter ASN upstream
of TLS), but the proxy/Apify path now sends a real browser JA3 instead of
`random`. See the generic write-up in
[`../skills/tls-fingerprinting.md`](../skills/tls-fingerprinting.md).

**How to verify after a `primp` bump:**
```bash
for n in chrome_146 chrome_131 firefox_148; do
  python -c "import primp; primp.Client(impersonate='$n')" 2>&1 \
    | grep -q "does not exist" && echo "INVALID $n" || echo "VALID $n"
done
```

---

## Baxia WAF (AliExpress)

**Symptom.** Every signed call to `acs.aliexpress.com/h5/mtop.*` returns
either `{"ret":["FAIL_SYS_USER_VALIDATE","RGV587_ERROR::SM::*"]}` (proxy
path) or `{"ret":["FAIL_SYS_TOKEN_EMPTY::令牌为空"]}` (datacenter path),
both inside a `mtopjsonp1(...)` wrapper.

**Root cause.** AliExpress's anti-bot WAF (Baxia) checks for the
presence of `_baxia_sec_cookie_`, a JSON-encoded cookie containing a
`tfstk` field. `tfstk` is generated client-side by Baxia's obfuscated
JS SDK after browser fingerprinting + a jrecaptcha challenge. Without
JavaScript execution, the cookie is unobtainable.

**What was tried.** 10+ alternative endpoint probes (mobile site,
acs-m gateway, affiliate portal, regional TLDs, multi-step Baxia
challenge replay). Full transcript at
[INVESTIGATIONS/BAXIA_2026.md](INVESTIGATIONS/BAXIA_2026.md).

**Resolution.** None HTTP-only. Workarounds available:
- Use `shoprenderview.aliexpress.com` (different gateway, light Baxia
  gate, works for store products + review aggregates).
- For full PDP / per-buyer reviews: pivot to a browser actor or a
  CAPTCHA-solver service.

---

## AliExpress 2026 listing-API drop (seller fields removed)

**Symptom.** category-scraper and search-scraper return rows with
`storeId`, `storeName`, `storeUrl`, `aliMemberId` all `null`.

**Root cause.** Verified by dumping live `items[0].keys()` from
`/w/wholesale-*` in 2026-05-15: the per-item object no longer has a
`store`, `seller`, or `shop` key. Only `trace.utLogMap.if_store_enter`
(boolean) remains as a seller signal. This is an upstream API change,
not a parser bug.

**Resolution.** Removed the always-null seller fields from output
schemas; added a `hasStorefront` boolean. For seller data per product,
the consumer must call the review-scraper or product-scraper (the
latter is Baxia-blocked, the former works via shoprenderview).

---

## AliExpress CSR migration (product / store pages)

**Symptom.** `/item/<id>.html` and `/store/<id>` return ~60 KB of HTML
with `runParams = {};` empty and `window._d_c_.isCSR = true`. No
product fields anywhere.

**Root cause.** AliExpress migrated PDPs and storefronts to fully
client-side React rendering in late 2025. The HTML ships only a shell
with bootstrap JS. Confirmed across all regional TLDs (es, pt, de, fr,
it, ar, ru, vi, tr).

**Resolution.** Product scraper emits `error: "CSR_SHELL"` row with
`productId` + `finalUrl` (extracted from URL + redirect chain). Full
data via shoprenderview for store-context products, or browser actor
for PDP.

---

## Product-ID changes on geo-redirect

**Symptom.** Submitting `/item/1005006373553410.html` returns rows
labelled with `1005006373553410` but the actual product on the final
page is `3256806187238658`.

**Root cause.** `www.aliexpress.com` redirects US IPs to
`www.aliexpress.us`, and the `.us` TLD uses a different ID space.
The redirect chain is `1005006373553410 → 3256806187238658`.

**Resolution.** Track `final_url` after the redirect and re-extract
`productId` via `re.search(r"/item/(\d+)", final_url)`. Stored back
into `parsed["productId"]`.

---

## curl_cffi session-cookie interference (MTOP)

**Symptom.** MTOP returns `FAIL_SYS_TOKEN_EMPTY` even when the
correct `_m_h5_tk` cookie is in the session jar.

**Root cause.** `curl_cffi 0.15.x` does not reliably propagate
cookies set via `session.cookies.update()` *after* the first request
in the session. Setting the cookie via the `Cookie:` header instead
works.

**Resolution.** In `mtop.py`, plant `_m_h5_tk` in the initial
`cookies={...}` dict at session creation, AND send it explicitly via
`headers={"Cookie": "_m_h5_tk=..."}` for the PDP call. Use a fresh
`cf_requests.Session(impersonate=...)` per MTOP call to avoid session
state contamination between calls.

---

## curl_cffi proxy auth 407 on Apify URLs

**Symptom.** `primp.Client` returns HTTP 407 on every Apify proxy URL.

**Root cause.** primp builds proxy-auth headers incorrectly when the
proxy username contains commas (Apify proxy usernames are
`auto+session=xxx,proxyCountry=YYY,...`).

**Resolution.** Switched to `curl_cffi` whenever a proxy is set. primp
is reserved for local no-proxy runs (where it slips Aliyun WAF more
reliably than curl_cffi).

---

## browserforge 1.2.4 vs crawlee workaround

**Symptom.** Actor crashes at startup with
```
AttributeError: module 'browserforge.download' has no attribute 'DATA_FILES'.
Did you mean: 'DATA_DIRS'?
```

**Root cause.** crawlee's `_browserforge_workaround.py` expects the
1.2.3 API (`download.DATA_FILES`). The 1.2.4 release renamed it to
`DATA_DIRS`. Apify SDK installs whatever satisfies `apify~=2.7` which
pulls 1.2.4 by default.

**Resolution.** Pin `browserforge == 1.2.3` in every `requirements.txt`.

---

## Apify INPUT_SCHEMA missing description

**Symptom.** Build fails:
```
ACTOR: ERROR: Input schema is not valid
(Field schema.properties.country.description is required)
```

**Root cause.** Apify schema validator requires every property to have
a `description` field. Default Apify CLI does not validate this
locally; it only fails server-side at build time.

**Resolution.** Audit every `INPUT_SCHEMA.json` and add a
human-readable `description` to every property. Pattern: also add
`editor` (`textfield`, `number`, `proxy`, `requestListSources`, etc.).

---

## Apify CLI false JSON parse error

**Symptom.** Every `apify push --force` exits with code 1 and prints:
```
Error: Unknown error: Unexpected end of JSON input
```
…even though the build succeeded.

**Root cause.** Known bug in `apify-cli 1.5.0` (the version pinned on
this machine). The error fires after the build log emits
`Success: Actor was deployed`.

**Resolution.** Ignore the exit code. Grep the log for
`Build finished` + `Success: Actor was deployed` to confirm.

---

## Apify memory limit when pushing in parallel

**Symptom.** Background `apify push` for a second actor fails with
```
Error: By launching this job you will exceed the memory limit of
8192MB for all your Actor runs and builds (currently used: 5120MB,
requested: 4096MB).
```

**Root cause.** The Apify account is on the free tier — total
concurrent build memory is capped at 8 GB, and each build reserves
4 GB.

**Resolution.** Push serially, not in parallel.

---

## AliExpress wholesale search "product not found"

**Symptom.** Submitting a 16-digit product ID as `SearchText` to the
wholesale-search URL returns 200 OK but the specific product is not
in the result set.

**Root cause.** Wholesale search does a text/keyword search, not an
exact-product-ID lookup. The product may not rank in the first page
for its own ID.

**Resolution.** Don't search by product ID. For per-product data via
HTTP-only, use shoprenderview with a known sellerId (see
[INVESTIGATIONS/BAXIA_2026.md](INVESTIGATIONS/BAXIA_2026.md)).

---

## Walmart PerimeterX (legacy notes)

**Symptom.** Walmart pages return 200 OK with a 1–15 KB body that
contains `_pxhd` and `pxc4`. The actual page content is replaced
with a JS challenge.

**Resolution.** Block-detection check includes
`status == 200 and len(body) < 5000 and "__NEXT_DATA__" not in body`.
On hit, rotate `curl_cffi` impersonation profile + new proxy URL.
First attempt PX-challenges ~40% of the time; second attempt succeeds.
