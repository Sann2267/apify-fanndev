# Skill: Write the README.md for an Apify Actor

## Hard rules

1. **No technical jargon** that exposes how the scraper works internally. The reader is a *user* of the actor, not a developer.
   - **Forbidden words/phrases**: `curl_cffi`, `primp`, `JA3`, `TLS fingerprint`, `DataDome`, `PerimeterX`, `Imperva`, `Akamai`, `WAF`, `bypass`, `proxy rotation`, `persisted query`, `GraphQL`, `preRegisteredQueryId`, `operationId`, `chunk`, `Apollo state`, `JSON-LD`, `XHR`, `endpoint`, `reverse engineering`, `bundle`, `headless`, `Puppeteer`, `Playwright`, `Cloudflare`.
   - **Allowed** (user-facing language): "rich detail", "automatic retries", "without managing scrapers or browsers", "stable JSON output", "no account required", "no API key needed".
2. **Real sample data only** — run the actor against a live URL and paste the actual output verbatim. Truncate long arrays (`"... 5 more"`) instead of fabricating values.
3. **`prefill` in every string input field** in `input_schema.json` so the operator can hit Run on Apify Console without typing anything.
4. **Cover one canonical use-case per mode** in the sample. If the actor supports both `article` and `latest` modes, show one sample for each.

---

## README structure

### 1. Title + one-liner
`# <Source> Scraper`
One sentence: what data it extracts and from which source.

### 2. Why use this actor
4–6 bullet points, user-facing benefits only. Sample:
- No account / no login required
- Full article text (not just headlines)
- Any unique structured data (tickers, comments, images…)
- Stable JSON output suitable for pipelines / databases
- Automatic retries if applicable

### 3. How it works
A short numbered list (3–5 steps), user-facing language only. No mention of the HTTP/TLS layer.

Example:
> 1. You give the actor an article URL (or `mode: "latest"` to fetch fresh headlines automatically).
> 2. The actor fetches the full article — headline, body text, byline, and publication date.
> 3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

End with one sentence about what the user does **not** need to manage.

### 4. Input

Show a valid JSON block with **all fields filled in** (prefill values, not placeholders).
Then a markdown table describing each field:

| Field | Type | Description |
|---|---|---|
| `url` | string | Single article URL to extract. |
| `urls` | array | Multiple article URLs to extract in one run. |
| `mode` | string | `"article"` (default) — extract a single URL. `"latest"` — fetch newest headlines. |
| `limit` | integer | Max articles returned in `latest` mode. Default: 10. |

### 5. Output

Show a real JSON sample (truncate `content` after ~300 chars, truncate long arrays after 2–3 items with `"... N more"`).

Then a markdown table describing each output field:

| Field | Type | Description |
|---|---|---|
| `url` | string | The scraped article URL. |
| `source` | string | Publication name. |
| `title` | string | Article headline. |
| …     | …    | …              |



### 6. Other Socmed Actors table

---

## When to use
When writing the README for any actor in this collection — new or updated. Always run `python main.py latest 1` and `python main.py <url>` locally to capture real output before writing.
