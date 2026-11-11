---
name: debugging-scraper
description: "Diagnose why an Apify actor returns errors, empty content, or wrong data via a step-by-step checklist from the raw HTTP response down to selector/parse issues. Use when an actor outputs an error, zero records, or incorrect fields."
---

# Skill: Debugging a Scraper

## When to use
When an actor returns `error`, empty content, or incorrect data.

## Debugging Checklist

### 1. Check what the site actually returns
```python
import httpx, asyncio

async def debug():
    async with httpx.AsyncClient(http2=True) as client:
        r = await client.get("URL", headers={"User-Agent": "Mozilla/5.0..."})
        print(r.status_code, r.headers.get("server"), len(r.text))
        # Save HTML for inspection
        with open("debug.html", "w") as f:
            f.write(r.text)

asyncio.run(debug())
```

### 2. Identify the response type
- **200 + HTML** → extraction issue (find correct selector)
- **200 + JSON** → CMS API or GraphQL - look for structured data
- **401/403** → anti-bot block (see bypass-antibot.md)
- **302/301** → redirect - make sure follow_redirects=True
- **Empty content** → paywall or JS-rendered content

### 3. Check for structured data first
```python
from bs4 import BeautifulSoup
import json, re

html = open("debug.html").read()
soup = BeautifulSoup(html, "lxml")

# JSON-LD
for script in soup.find_all("script", type="application/ld+json"):
    try:
        data = json.loads(script.string)
        print(data.get("@type"), list(data.keys()))
    except:
        pass

# NEXT_DATA
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if m:
    nd = json.loads(m.group(1))
    # Explore: nd["props"]["pageProps"]
```

### 4. Find the right selector
In DevTools (right-click → Inspect), find the article container and use the CSS class or data attribute:
```python
# Try common selectors
for sel in ["article", "[data-testid='article-body']", ".article-body", ".story-body", "#main-content"]:
    el = soup.select_one(sel)
    if el:
        print(f"Found: {sel} - {len(el.get_text())} chars")
        break
```

### 5. Common issues by site

| Site | Common Issue | Fix |
|---|---|---|
| BBC | body blocks nested in NEXT_DATA | Walk `model.blocks` recursively |
| CNBC | NEXT_DATA path changes | Check `props.pageProps.page` or `props.pageProps` |
| FT | httpx fails with duplicate cookie error | Use curl_cffi instead |
| Reuters | 401 on all requests | Use primp |
| Forbes | 403 on article pages | Use primp |
| SCMP | Empty content | Check `payload.data.article.body.text` in NEXT_DATA |
| Fortune | Only 1st paragraph | Extract directly from article element, not via clean_html() |
| NYTimes | Partial content | NEXT_DATA contains more than HTML renders |

### 6. Test with trafilatura as sanity check
```python
import trafilatura
text = trafilatura.extract(html, include_comments=False)
print(f"trafilatura: {len(text or '')} chars")
```
If trafilatura gets content but main.py doesn't, the extraction selector is wrong.

### 7. Verify output schema
Make sure result has these keys: `url, source, title, content`
Other fields (`description, published_date, authors, etc.`) are optional but should be filled.

### 8. Test the fetch_latest function
```bash
cd actors/<name>
python main.py latest 3
```
Should return an array of `{url, title, published_date, source}` objects.
