---
name: apollo-state-paywall
description: "Read full article text from a page's SSR JSON (Apollo state / __NEXT_DATA__) when a CSS paywall only hides the visible body. Use when scraping premium news (NYTimes, Fortune, SCMP, WSJ, Barron's, Bloomberg) and the rendered HTML shows only a 'subscribe to read' preview."
---

# Apollo State / `__NEXT_DATA__` Paywall Bypass

> **Many "paywalled" articles are not actually paywalled in the SSR payload — they're rendered with the body present and a CSS overlay hiding it.** Reading the embedded JSON gives you the full text. NYTimes, Fortune, SCMP, WSJ, Barron's, and Bloomberg all share variants of this.

## Problem

Premium news sites display "Subscribe to read" walls but ship the article content in their SSR JSON for SEO/social-preview purposes. Reading the visible HTML returns the truncated preview; reading the JSON returns the full body.

Some sites (WSJ, Barron's, IBD) instead ship a deliberate intro snippet + metadata + auto-generated summaries — still useful, still extractable without auth.

## Solution: priority extraction order

Always try these in order, fall back when one is empty:

1. **JSON-LD** (`<script type="application/ld+json">`) — most stable, schema.org typed
2. **`__NEXT_DATA__`** (Next.js SSR state) — full data, prone to surface volatility
3. **Apollo state** (`window.__APOLLO_STATE__`) — for Apollo-based sites
4. **Embedded inline JSON** (other shape) — Pinterest `__PWS_INITIAL_PROPS__`, Tokopedia `window.__cache`
5. **HTML CSS selectors** — last resort, brittle to redesigns
6. **`trafilatura`** — metadata enrichment when extraction returns sparse fields

## Site-by-site extraction map

### NYTimes (soft paywall)
- **Selector path:** `__NEXT_DATA__.props.initialState.body`
- **Body text rendered as component tree** — recurse through `type:"paragraph"`, `type:"heading"`, etc., concatenate text values.
- **Bypass:** Just read JSON. No special TLS needed (use `curl_cffi chrome131`).

### Fortune (soft paywall)
- **Body lives in `<article>` element.** The "clean_html()" approach strips the paywall wrapper but also strips the body.
- **Correct approach:** extract `<p>`, `<h2>`, `<h3>`, `<blockquote>` children of `<article>` directly. Skip wrapper.

### SCMP (soft paywall)
- **JSON path:** `props.pageProps.payload.data.article.body.text`

### WSJ / Barron's (hard paywall — Dow Jones)
- Subscriber wall is real for full body. BUT public payload still carries:
  - `pageProps.snippet` — 1–4 paragraph intro (non-subscriber visible)
  - `articleData.flattenedAltSummaries[variant=Automated Bullet Summary]` — Dow Jones auto-summary
  - SEO description meta tag
  - `articleMeta.metrics.full_word_count`, `full_paragraph_count`
- **TLS profile required:** `primp` 27-profile shuffle pool against DataDome
- **Proxy required:** US Residential (DataDome blocks datacenter + non-US residential for these)

### Investing.com (Cloudflare)
- **JSON path:** `__NEXT_DATA__.state.newsStore._article`
- Also accessible: `_relatedPairs`, `commentsStore`
- **TLS:** `primp` with random profile

### IBD (Investor's Business Daily)
- **PerimeterX-protected**
- **Bypass:** `scrapling[fetchers]` + Piano paywall handling
- **Intro paragraph + full metadata always available** (Piano partial-paywall model)

### Bloomberg (article)
1. `__NEXT_DATA__` primary — full story object
2. `__PRELOADED_STATE__` Redux-shape secondary
3. LD-JSON fallback
4. `og:` meta tags last resort
- **Body is a component tree** — recurse `{role, parts}` nodes:
  ```python
  def render_bloomberg_body(node):
      if isinstance(node, dict):
          if node.get("role") in ("p", "h1", "h2", "blockquote", "li"):
              return "".join(render_bloomberg_body(p) for p in node.get("parts", []))
          if "value" in node:
              return node["value"]
      if isinstance(node, list):
          return "".join(render_bloomberg_body(p) for p in node)
      return ""
  ```
- **TLS:** `scrapling safari2601` (PerimeterX PX8FCGYgk4)
- **Gotcha:** `story.get("credits")` returns `None` (not `[]`) when JSON says `"credits": null`. Always `(story.get("credits") or [])`.

### Tokopedia (PDP)
- `window.__cache = ` blob
- Apollo cache flat shape with `{type:"id", id:...}` refs → use `resolve_apollo_refs`
- See [`skills/balanced-brace-json.md`](../balanced-brace-json/SKILL.md) for the walker

### Medium (post)
- `window.__APOLLO_STATE__ = ` blob
- **Note:** Medium's `?format=json` endpoint now returns full HTML for post URLs (changed ~2024). Always parse Apollo from the HTML response.
- Cache fields use refs identical to standard Apollo.

### Pinterest
- Priority chain: `profile-snippet` → `__PWS_DATA__` → `__PWS_INITIAL_PROPS__` → `initial-state`
- `__PWS_INITIAL_PROPS__` block can be **500KB–507KB inline JSON**
- Regex to extract the block: `(.+?)` with `re.DOTALL` (the original `[^<]+` caps content because the JSON contains literal `<` in URLs)
- DFS-walk for user/board/pin by matching `username` / `board_id` / `pin_id`

## Pattern: tiered extraction with envelope tagging

```python
async def extract_article(url: str) -> dict:
    html = await fetch_with_tls(url)
    
    # S1 — JSON-LD
    for jsonld in find_jsonld_blocks(html):
        if jsonld.get("@type") == "NewsArticle":
            data = parse_jsonld_article(jsonld)
            if data.get("articleBody"):
                return {**data, "_source": "S1-jsonld"}
    
    # S2 — __NEXT_DATA__
    next_data = extract_json_after(html, '<script id="__NEXT_DATA__"')
    if next_data:
        data = parse_next_data_article(next_data, site=site)
        if data.get("body"):
            return {**data, "_source": "S2-nextdata"}
    
    # S3 — Apollo state
    apollo = extract_json_after(html, "window.__APOLLO_STATE__ = ")
    if apollo:
        data = parse_apollo_article(apollo)
        if data.get("body"):
            return {**data, "_source": "S3-apollo"}
    
    # S4 — HTML selectors
    data = parse_html_selectors(html)
    if data.get("body"):
        return {**data, "_source": "S4-html"}
    
    # S5 — trafilatura metadata enrichment
    data = trafilatura_extract(html, url)
    return {**data, "_source": "S5-trafilatura"}
```

## Caveats

- **Site authors do refactor.** `__NEXT_DATA__` keeps disappearing from sites that migrate to React Server Components / App Router (Capterra dropped it entirely → use JSON-LD instead). Have a fallback ready.
- **Apollo refs use `__typename` which leaks noise.** Strip during resolve.
- **`__NEXT_DATA__` can be huge (>1MB).** Parsing is fast (`json.loads`) but allocating is not. Don't keep it in memory beyond one call.
- **Body rendering varies wildly across sites.** Don't write one universal renderer — write per-site `render_body()` functions.
- **WSJ/Barron's: the snippet is not the full body.** Don't claim full extraction — document the limit and emit `full_word_count` so consumers know what they're getting.
- **For Bloomberg, the LD-JSON fallback often returns stale data** because LD-JSON is sometimes cached on CDN longer than NEXT_DATA. Prefer NEXT_DATA.
- **TLS impersonation does NOT change extraction code.** WAF bypass = transport layer; JSON walk = parsing layer. Keep them separate (different files).

## Where used

- Online News suite — NYT, Fortune, SCMP, WSJ, Barron's, Investing.com, IBD, Forbes
- Bloomberg article-scraper (NEXT_DATA + PRELOADED_STATE + LD-JSON fallback)
- Tokopedia (Apollo `__cache` with ref resolution)
- Medium post-detail (Apollo state)
- Pinterest (PWS_INITIAL_PROPS DFS walk)

## See also
- [`skills/balanced-brace-json.md`](../balanced-brace-json/SKILL.md)
- [`skills/multi-strategy-fallback.md`](../multi-strategy-fallback/SKILL.md)
- [`anti-bot/cloudflare.md`](../../anti-bot/cloudflare.md)
- [`anti-bot/datadome.md`](../../anti-bot/datadome.md)
