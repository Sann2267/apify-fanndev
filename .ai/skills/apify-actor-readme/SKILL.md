---
name: apify-actor-readme
description: "Write (or enhance) the README.md for an Apify Actor as a Store listing — user-facing, zero internal jargon, real sample data, prefilled inputs. Use whenever you create or update an actor's README for the Apify marketplace. Enforces the forbidden-words list (curl_cffi/TLS/WAF/GraphQL/proxy/headless…), a fixed section structure, and real verbatim output captured from a live run."
---

# Skill: Write the README.md for an Apify Actor

The README is the actor's **Store listing**, read by a *buyer/operator*, not a developer. It must sell the value and show real output — never reveal how the scraping works internally.

## Hard rules

1. **No technical jargon that exposes internals.** The reader is a *user* of the actor.
   - **Forbidden words/phrases:** `curl_cffi`, `primp`, `scrapling`, `Camoufox`, `JA3`, `JA4`, `TLS fingerprint`, `impersonate`, `chrome124`/`chrome99_android`, `DataDome`, `PerimeterX`, `Imperva`, `Akamai`, `Fastly`, `AWS WAF`, `WAF`, `bypass`, `challenge`, `proxy rotation`, `session`, `cookie transplant`, `persisted query`, `GraphQL`, `doc_id`/`queryId`, `chunk`, `Apollo state`, `__NEXT_DATA__`, `JSON-LD`, `flatted`, `perseus`, `XHR`, `endpoint`, `reverse engineering`, `bundle`, `headless`, `Puppeteer`, `Playwright`, `Cloudflare`.
   - **Allowed** (user-facing): "rich detail", "automatic retries", "without managing scrapers or browsers", "stable JSON output", "no account required", "no API key needed", "residential proxy support" (fine — it's a Console feature the operator toggles).
2. **Real sample data only.** Run the actor against a live input and paste the actual output verbatim. Truncate long arrays (`"… 5 more"`) and long text (~300 chars) instead of fabricating values. Never invent field values.
3. **`prefill` in every string input field** in `input_schema.json` so the operator can hit **Run** on the Apify Console without typing anything. (Arrays use `prefill: [...]`; `default` is fine for non-string types.)
4. **Cover one canonical use-case per mode** in the sample. If the actor has `search` and `detail` modes, show one real sample for each.

## README structure

### 1. Title + one-liner
`# <Source> Scraper` — one sentence: what data it extracts and from which source.

### 2. Why use this actor
4–6 bullets, user-facing benefits only:
- No account / no login / no API key required
- The unique value (whale wallets, room prices, danmaku comments, agent contacts…)
- Any distinctive structured data it returns
- Stable JSON output suitable for pipelines / databases / spreadsheets
- Automatic retries; runs on Apify's schedule; export to JSON/CSV/Excel

### 3. How it works
3–5 numbered steps, user-facing language only — **no mention of the HTTP/anti-bot layer**. End with one sentence on what the user does **not** need to manage ("no scrapers, browsers, or blocks to babysit").

### 4. Input
A valid JSON block with **all fields filled in** (prefill values, not placeholders), then a table describing each field (Field | Type | Description). One block per mode if inputs differ by mode.

### 5. Output
A **real** JSON sample (truncate long text ~300 chars; long arrays after 2–3 items with `"… N more"`), then a table describing each output field (Field | Type | Description). Show one sample per mode.

### 6. Notes / limits (optional but honest)
Any real cap the operator must know ("returns ~25 results per search URL; use several URLs for volume"), proxy recommendation ("use Residential + the relevant country for best results"), and update cadence. Keep it user-facing.

### 7. Other actors table (optional)
Link sibling actors in the collection.

## Workflow

1. Read the actor's `input_schema.json` and `src/` to know modes, inputs, and the real output shape.
2. **Run it live once per mode** (locally or via `apify call`) and capture verbatim output — never guess field values.
3. Ensure every string input has a `prefill` (edit `input_schema.json` if missing).
4. Write the README to the structure above; scrub every forbidden word (grep the draft).
5. Self-check: could a non-developer run it from the Console and understand the output? Is every sample value real?

## Self-check grep (run before shipping)
```bash
grep -iE 'curl_cffi|primp|scrapling|camoufox|ja3|ja4|tls|impersonate|chrome1[0-9][0-9]|datadome|perimeterx|imperva|akamai|fastly|aws.?waf| waf |bypass|graphql|__next_data__|json-ld|jsonld|flatted|perseus|apollo|headless|playwright|puppeteer|cloudflare|challenge|endpoint|reverse.?engine' README.md
```
Any hit → reword for a user audience.

## When to use
Writing or updating the README for any actor in this collection — new or enhanced. Always capture real output from a live run first.
