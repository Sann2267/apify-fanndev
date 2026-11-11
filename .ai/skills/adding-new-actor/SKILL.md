---
name: adding-new-actor
description: "Build a new reliable HTTP/TLS-only Apify scraper from scratch with no browser automation (no Playwright, Selenium, or Puppeteer). Use when creating a new actor in this monorepo or scaffolding a new scraping target."
---

# Skill: Adding a New Actor

You are an autonomous senior scraping engineer.

Objective:
Build a reliable high-success-rate crawler using ONLY raw HTTP/TLS approaches without any browser automation.

Strict Constraints:

* DO NOT use Playwright
* DO NOT use Selenium
* DO NOT use Puppeteer
* DO NOT use undetected-chromedriver
* DO NOT use browser automation of any kind
* DO NOT rely on cookies exported from a browser
* DO NOT require manual login
* DO NOT require authenticated sessions
* DO NOT solve challenges manually
* DO NOT use headless browsers
* The solution must work using direct HTTP requests only

Allowed Approaches:

* curl_cffi
* tls-client
* primp
* scrapling
* httpx
* requests
* aiohttp
* custom TLS fingerprinting
* JA3 impersonation
* HTTP/2 impersonation
* Chrome-like header emulation
* ALPN negotiation tuning
* header ordering emulation
* connection reuse
* session fingerprint tuning

Required Workflow:

1. Start with minimal HTTP requests.
2. If blocked:

   * rotate realistic Chrome User-Agents
   * emulate modern Chrome request headers
   * add sec-ch-ua headers
   * emulate fetch metadata headers
   * mimic browser header ordering
3. If still blocked:

   * test TLS impersonation
   * compare JA3 fingerprints
   * force HTTP/2
   * tune ALPN negotiation
   * emulate Chrome TLS extension ordering
4. Test alternative HTTP stacks:

   * curl_cffi
   * tls-client
   * primp
   * scrapling
5. Compare:

   * successful browser network traces
   * failed crawler traces
6. Inspect:

   * redirects
   * response headers
   * hidden anti-bot markers
   * timing behavior
   * protocol negotiation
   * compressed payload differences
7. After every failure:

   * explain the root cause hypothesis
   * modify the implementation
   * immediately retest
8. Continue iterating automatically until:

   * the crawler succeeds consistently
   * or all HTTP-only approaches are exhausted

Important:

* Never stop at 403/429 responses.
* Never assume the first implementation is correct.
* Treat every failure as diagnostic information.
* Prioritize browser-indistinguishable HTTP traffic without launching a browser.

Output Requirements:

* Show every attempted strategy
* Explain why each attempt failed or succeeded
* Provide improved code after each iteration
* Produce the final optimal architecture and recommended stack


## When to use
When adding support for a new news source to the collection.

## Steps

### 1. Copy an existing actor as template
```bash
cp -r actors/guardian-scraper actors/newsite-scraper
```
Use `guardian-scraper` as a template for easy sites, `reuters-scraper` for DataDome-protected sites, `ft-scraper` for Cloudflare-protected sites.

### 2. Update `main.py`

Set the source name and extraction logic:
```python
# At the top
SOURCE = "New Site"
DEFAULT_URL = "https://www.newsite.com/news/example-article"

# RSS feed for latest mode
LATEST_FEED = "https://www.newsite.com/rss"

async def extract_article(client, url):
    result = {"url": url, "source": SOURCE}
    # ... extraction logic ...
    return result

async def fetch_latest(client, limit=10):
    # Standard RSS pattern (copy from any existing actor)
    items = []
    try:
        resp = await client.get(LATEST_FEED, headers=HEADERS_DESKTOP, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return items
        soup = BeautifulSoup(resp.text, "xml")
        for item in soup.find_all("item")[:limit]:
            # ... parse item ...
            items.append({"url": url, "title": title, "published_date": pub_date, "source": SOURCE})
    except Exception as e:
        log.warning(f"fetch_latest error: {e}")
    return items

if __name__ == "__main__":
    asyncio.run(run_actor(extract_article, fetch_latest_fn=fetch_latest))
```

### 3. Update `input_schema.json`
Should already be correct if copied. Verify it has `url`, `urls`, `mode`, and `limit` fields.

### 4. Write `.actor/output_schema.json` and `.actor/actor_output_links.json`
Follow [`skills/actor-output-schema/SKILL.md`](../actor-output-schema/SKILL.md) — two separate files:
- `output_schema.json` (Dataset schema, the real table view): enumerate every field
  `extract_article`/`extract_error`/`extract_rss_items` (or `extract_sitemap_items`) actually returns
  for *this* site and list them for real, don't copy a generic template verbatim.
- `actor_output_links.json` (Output schema, Console quick-link button): copy the boilerplate as-is,
  just swap the `title` to match this actor.

### 5. Update `.actor/actor.json`
- Set `name`, `title`, `description`
- Wire both schemas:
  ```json
  "storages": {"dataset": "./output_schema.json"},
  "output": "./actor_output_links.json"
  ```
- Each key must point at the file shaped for it — putting the dataset-shaped file behind `"output"`
  (or vice versa) breaks the Output tab; see
  [`skills/actor-output-schema/SKILL.md`](../actor-output-schema/SKILL.md)

### 6. Update `requirements.txt`
Add only what's strictly needed.

### 7. Write README.md
Follow the skill in `.ai/skills/actor_readme.md` — no technical jargon, real data only, prefill all input fields.

Run locally first to capture real output:
```bash
python main.py latest 1
python main.py "<url-from-above>"
```
Paste the actual output into the README. Truncate long arrays (`"... N more"`) instead of fabricating.

### 8. Add to qa_test.py
Add an entry to the `ACTORS` list in `qa_test.py` at the project root:
```python
{"name": "newsite-scraper", "latest": True},
```
Place it in alphabetical order within the list. Set `"latest": False` only if the actor has no `fetch_latest` (i.e. `url_from` strategy instead).

Then seed the baseline immediately:
```bash
cd <project-root>
python qa_test.py seed newsite-scraper
```

### 9. Add to head-news-scraper
Add the new source to `actors/head-news-scraper/utils.py` in the `SOURCES` dict.

### 10. Test locally
```bash
cd actors/newsite-scraper
python main.py latest 5
python main.py "<url-from-above>"
```

### 11. Push to Apify
```bash
apify validate-schema   # expect "Input schema is valid" AND "Dataset schema is valid"
apify push -f
```

### 12. Market research, Store category & monetization (required — do not skip)
An actor isn't "done" once it builds, pushes, and runs. Before considering it complete, run
[`actor-store-monetization/SKILL.md`](../actor-store-monetization/SKILL.md): research Store
competitors, assign the Store category, and configure evidence-based pricing (pay-per-event or
pay-per-usage). This applies automatically to every new actor built with this skill — it does not
need to be requested separately each time. Only after that skill's Phase 9 checklist is satisfied
(or its blockers are explicitly documented) should you move on to the next actor.

## Extraction Strategy Selection

| Site Type | Recommended Strategy |
|---|---|
| WordPress/JSON-LD | `find_article_ld(extract_json_ld(html))` |
| Next.js | `extract_next_data(html)` + `deep_get(nd, "props.pageProps...")` |
| WordPress REST API | `GET /wp-json/wp/v2/posts?slug=<slug>` |
| Cloudflare | `curl_cffi` with `chrome145` |
| DataDome | `primp` with `chrome_126` or `firefox_133` |
| CMS API | Direct API call (MSN pattern) |
