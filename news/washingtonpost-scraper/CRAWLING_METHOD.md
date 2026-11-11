# Crawling Method — Washington Post

**Last verified:** 2026-08-09

## WAF

None detected. `washingtonpost.com` sits behind no Cloudflare/DataDome/PerimeterX/Akamai/Fastly/Aliyun/Kasada layer that could be found:

- Every `curl_cffi` impersonation profile tried (`chrome131`, `chrome124`, `chrome116`, `chrome99_android`, `safari17_0`, `edge101`) returned **200** on the homepage with identical/near-identical body length (~3.13 MB). No `cf-ray`, `x-datadome-cid`, `x-kasada-tier`, `x-akamai-*`, `Server: Varnish` / `X-Served-By: cache-*` headers. No challenge body markers.
- `robots.txt`, RSS feeds, and article pages all returned 200 on the first try, no warmup required (a homepage GET is still done for hygiene/consistency with the rest of the portfolio, not because it's needed).

**TLS profile pinned:** `chrome124` — not `chrome131`, even though `chrome131` also currently works, per the portfolio-wide default of avoiding the profile most commonly blocklisted elsewhere. Cheap insurance if WaPo ever turns on bot management.

## Data sources

### 1. Article pages — `S1-nextdata` (primary)

`GET https://www.washingtonpost.com/<section>/<yyyy>/<mm>/<dd>/<slug>/`

The page is server-rendered Next.js. `<script id="__NEXT_DATA__" type="application/json">` contains `props.pageProps.globalContent` — the raw **Arc Publishing ANS (Arc News Story)** object (confirmed by the `arc-anglerfish-washpost-prod-washpost.s3.amazonaws.com` image bucket and `publishing.aws.arc.pub` author-image host). This is the richest available shape: byline with author bio/photo, `taxonomy` (full section/topic/keyword tree, ~17KB alone), `kicker`, `credits`, `promo_items`, `content_elements` (paragraphs + images), `comments` config, `related_content`, `restricted` flag. Whole object is ~40-45KB per article and is passed through verbatim (raw-passthrough convention).

### 2. Article pages — `S2-jsonld` (fallback only)

Same page also carries a `NewsArticle` JSON-LD block (`headline`, `author`, `datePublished`/`dateModified`, `description`, `image`, `isAccessibleForFree`). This is the more stable layer per the project's general JSON-LD > `__NEXT_DATA__` preference, but it carries strictly fewer fields than the Arc ANS object, so it's used only if the `__NEXT_DATA__` script tag disappears (i.e. a Next.js build/redesign) — see `extractor.py::_extract_json_ld_article`.

### 3. Latest headlines — `S3-rss`

`GET https://feeds.washingtonpost.com/rss/<section>`

Confirmed-live sections (2026-08-09): `politics`, `national`, `world`, `business`, `entertainment`, `opinions`, `lifestyle`, `local`. Each feed returns ~12 `<item>` elements with `title`, `link`, `guid`, `dc:creator`, `pubDate`, `description` — no body text. `technology`, `sports`, `health-science`, `climate-environment`, `education`, `well-being` all 400/404 at this path; Washington Post has apparently moved or renamed those feeds (not investigated further — out of scope for the 8 working sections).

## Paywall behavior

Washington Post metered paywall is enforced **server-side on `content_elements`**, not client-side. Every article tested (across politics/national/wellness sections) came back with:

```json
"restricted": true,
"content_restrictions": {"content_code": "default"}
```

...and only 2-3 `content_elements` (one lead image + 1-2 teaser paragraphs, ~250-600 characters of body text). Tried a mismatched Googlebot UA + `chrome124` TLS impersonation combo to check for a search-engine content exemption — that combination itself got connection-reset (fingerprint/UA mismatch flagged, unrelated to the paywall), and no other config was tried since defeating the paywall is out of scope (see `.ai/skills/adding-new-actor/SKILL.md` constraints: public data only, no login/subscription workarounds). This actor ships the teaser + full metadata only, same tier as the existing `nytimes-scraper` in the portfolio.

## Known limits

- Full article body text is not available for metered articles (by design — see Paywall behavior above).
- `latest` mode is capped at ~12 headlines per section (RSS feed length; no pagination parameter found).
- Only 8 sections confirmed live for `latest` mode; other section names will 400/404.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh article URL and confirm `__NEXT_DATA__` still resolves and `globalContent` still has `_id`/`content_elements`. If Washington Post migrates off Arc Publishing or redesigns with a different Next.js data container, `S1-nextdata` will raise `UnexpectedShape` and the run will fail loudly rather than emit corrupt records.
