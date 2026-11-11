# Crawling Method — AEO Bing Rank Tracker

**Last verified:** 2026-08-26

## What "AEO/GEO Tracker" means, and why this ships as a single-mode actor

"AEO" (Answer-Engine Optimization) and "GEO" (Generative-Engine
Optimization) is a marketing-tooling category, not a single website —
practitioners want to know "does my brand/domain show up when someone
asks an answer engine about my product category?" Three answer surfaces
were investigated for this actor. Only one — Bing's organic search
results — was HTTP-only reachable end-to-end without requiring real
JavaScript execution, which this project's constraints don't permit. The
other two (Google AI Overview, DuckDuckGo AI Chat) were investigated
thoroughly and conclusively ruled out; both investigations are kept in
full detail below because the evidence trail is valuable for anyone
revisiting either later, and because "we tried and here's exactly why it
doesn't work" is worth more than silently shipping nothing.

## Shipped: Bing organic SERP — fully verified, no proxy needed

`GET www.bing.com/search?q=<query>&count=10` — clean 200, no CAPTCHA,
confirmed across many queries both locally (plain `curl_cffi`
`chrome124`, no proxy) and via `apify call` on the deployed Actor.

### Real, mapped anti-bot behavior: leading-superlative queries get decoy results

**This is the single most important finding in this actor.** A query
whose first word is a bare superlative — `"best crm software for small
business"`, `"top project management tools 2026"`, `"best email
marketing platform"` — reliably returns a completely irrelevant decoy
result set built around just that one word:

```
q=best+crm+software+for+small+business  →  results about "BEST":
  - Yamada Best Indonesia (electronics retailer)
  - Cambridge Dictionary: "BEST" definition
  - Merriam-Webster: "BEST" definition
  - mybest (Indonesian product-recommendation site)
  - BEST (IDX ticker symbol, TradingView chart)
```

Yet the page's own `<title>` tag correctly reads `"best crm software for
small business - Search"` — the title and the body-result computation
are clearly served by different code paths that diverge specifically for
this query shape. **Confirmed fixed** by rephrasing the identical intent
as a natural question instead:

```
q=which+crm+software+is+best+for+small+business  →  real, relevant results:
  - qontak.com (CRM blog)
  - salesforce.com/crm/what-is-crm  ← real brand, correctly found (rank 2 on one run, rank 8 on a later apify call run)
  - scaleocean.com (CRM comparison, Indonesian)
  - forbes.com/advisor (Best CRM Software roundup)
```

```
q=crm+software+for+small+business  (superlative dropped entirely) → also correct
```

Tested and confirmed on 4 separate query pairs (CRM, project management,
email marketing) locally, then reconfirmed via `apify call` on the live
platform — 100% reproducible in both directions (decoy with leading
"best"/"top", correct without). This reads as a deliberate countermeasure
aimed specifically at the "best X for Y" template that rank-tracking/SEO
tools notoriously send verbatim — real users type questions, not
keyword-stuffed phrases, so requiring natural phrasing here doubles as
decent practice anyway (it's also literally how a person would ask an AI
assistant the same question, which is the actual scenario AEO/GEO
tracking is trying to approximate).

**This actor enforces nothing programmatically** (there's no reliable
way to distinguish "genuinely irrelevant results" from "decoy results"
after the fact from inside the actor) — instead the `query`/`queries`
input fields' description explicitly instructs natural-question
phrasing, with the exact before/after example from this recon.

### Also confirmed: results are capped at exactly 10, no working pagination

- `count=10`, `count=30`, and `count=50` all returned exactly 10
  `li.b_algo` items — the `count` parameter is silently ignored.
- Page 2 via `first=11` (bare) returned byte-identical content to page 1.
- Page 2 via the *real* next-page link scraped from page 1's own HTML
  (`first=11&FPIG=<session-token>&FORM=PORE` — not a guessed URL, the
  literal `href` of the `a.sb_pagN` "Next page" link) **still** returned
  identical content to page 1.

This actor therefore returns at most the first 10 organic results per
query and does not claim to paginate further — for AEO purposes this is
a reasonable scope limit anyway, since answer engines overwhelmingly
draw citations from top-ranking results, not page 3.

### Extraction

`li.b_algo` per result; `h2 > a` for title/href, `div.b_caption p` (or
one of the `p.b_lineclampN` variants) for the snippet. **Every href is a
`bing.com/ck/a?...&u=<encoded>` tracking redirect, not the real
destination** — confirmed the encoding scheme live: the `u` query param
is a fixed 2-character `"a1"` prefix followed by base64url (with padding
stripped, restored before decoding) of the real destination URL
(`a1aHR0cHM6Ly95YW1hZGFiZXN0aWQuY29tLw` → `https://yamadabestid.com/`,
verified). `decode_bing_redirect()` in `src/extractor.py` handles this;
domain matching (`isTarget`/`targetRank`) is computed against the
*decoded* real domain, never the tracking-redirect host.

## Investigated and ruled out #1: Google AI Overview

Taken through **7 full build-deploy-test iterations on the actual Apify
platform** before being conclusively ruled out.

1. **Plain request, no proxy:** `GET www.google.com/search?q=...` from
   the original dev sandbox returned HTTP 429 with a full reCAPTCHA
   Enterprise challenge page (`"Our systems have detected unusual
   traffic from your computer network"`, `g-recaptcha`,
   `recaptcha/enterprise.js`) on every attempt, regardless of query
   phrasing or headers — read at the time as an IP-reputation block.
2. **Apify's `GOOGLE_SERP` proxy group** (a group that exists on this
   account specifically for downloading Google Search pages) was tried
   next, expecting it to clear the block. Instead it failed at the
   *connection* level: `ConnectionError('Failed to perform, curl: (7)
   CONNECT tunnel failed, response 400.')` — a proxy-tunnel failure, not
   a response from Google at all. This proxy group does not work for
   this use case on this account, despite being platform-enabled.
3. **Apify's `RESIDENTIAL` proxy group** was tried as a fallback and
   *did* clear the CAPTCHA — a clean HTTP 200 was obtained. This
   initially looked like success.
4. **But the 200 response was empty of real content.** The extraction
   code (looking for an "AI Overview" heading anywhere in the document)
   correctly reported `aiOverviewPresent: false` — but repeated on a
   second, more AI-Overview-likely query (`"what is customer
   relationship management software"`) and still got `false`. This
   prompted direct inspection of the raw HTML rather than trusting the
   extractor's negative result.
5. **Debug instrumentation added** (temporarily) to log HTML length and
   presence of generic Google Search markers (`c-wiz`, `id="search"`,
   `id="rso"`, `<h3>` count, `<title>` content) directly via
   `Actor.log.info`, redeployed, re-tested via `apify call`. Result:
   **zero** of these markers were present — not just no AI Overview
   markup, no organic-result markup *at all*. The `<title>` was the
   generic, non-query-specific `"Google Search"` (not
   `"<query> - Google Search"` as a real results page would have).
6. **Two header/fingerprint variations were tried** to rule out a
   client-hints gap: (a) a full modern-Chrome header set (`Sec-Ch-Ua`,
   `Sec-Fetch-*`, `Upgrade-Insecure-Requests`) on the theory that Google
   might require richer client signals to serve the full experience; (b)
   the opposite theory — a minimal, plain Firefox user-agent with no
   client-hint headers at all, on the theory that Google might reserve
   the JS-shell experience for browsers it assumes are JS-capable. Both
   produced the **exact same ~92KB shell page**, byte-length and all —
   proving the response is invariant to header sophistication.
7. **Direct inspection of the actual page body** (dumping the first 600
   characters after `<body>`) found the answer conclusively:
   ```html
   <body><noscript><style>table,div,span,p{display:none}</style>
   <meta content="0;url=/httpservice/retry/enablejs?sei=..." http-equiv="refresh">
   <div style="display:block">Please click <a href="/httpservice/retry/enablejs?sei=...">here</a>
   if you are not redirected within a few seconds.</div></noscript>
   <script nonce="...">...</script>
   ```
   This is Google's own explicit **"JavaScript required"** gate — a
   `<noscript>` fallback meant only for browsers that can't run the page
   script, redirecting to a `enablejs` retry endpoint. Not a bot block
   (clean 200, no CAPTCHA markers) and not a header gap (invariant across
   two very different header profiles) — it's Google's search results
   page architecture itself: results are hydrated by client-side
   JavaScript from a follow-up request, not present in the initial
   document at all, for this request path.

**Conclusion:** per this project's core constraint ("never reach for a
browser until HTTP is proven exhausted"), this satisfies that bar — 7
iterations, proxy escalation (datacenter → GOOGLE_SERP → RESIDENTIAL),
two opposite header/fingerprint strategies, and direct evidence of an
explicit JS-required gate in the response body itself. Same category as
Shopee's `x-sap-sec` or pre-X-Gnarly TikTok in `.ai/lessons-learned.md`.

## Investigated and ruled out #2: DuckDuckGo AI Chat

Built first against the well-documented, widely-used anonymous
DuckDuckGo AI Chat flow (used by numerous open-source "duckduckgo chat"
wrappers): GET `duckduckgo.com/duckchat/v1/status` with `x-vqd-accept:
1` to receive an anonymous `x-vqd-4` session token in the response
headers, then POST a chat turn to `duckduckgo.com/duckchat/v1/chat`
referencing that token, streamed back as `text/event-stream`.

`duckduckgo.com` was unreachable at the raw TCP level from the original
dev sandbox (DNS resolved fine, the TCP connect itself timed out — an
ISP/network-level block specific to that sandbox, not a WAF response,
since no response was ever received to triage against). Deployed to
Apify and tested via `apify call` instead, whose network path does
reach duckduckgo.com (a real HTTP 200 came back, unlike the sandbox's
connection timeout).

**But the expected `x-vqd-4` header never arrived.** Debug
instrumentation showed the status endpoint now returns a *different*
header, `x-vqd-hash-1`, and the response body is just
`{"status":"0","secondaryStatus":"0","statusV2":0}` — no usable token in
either place. `x-vqd-hash-1`'s value, once base64-decoded, is ~5.7KB of
heavily obfuscated JavaScript (string-array + XOR-based obfuscation) that
computes and returns an object shaped like `{server_hashes: [...],
client_hashes: [...], signals: {}, meta: {v:'4', challenge_id, timestamp,
...}}` — a proof-of-work-style anti-bot challenge, not a simple static
token. This is a confirmed, live protocol change on DuckDuckGo's side,
dated after the "well-documented" `x-vqd-4`-only flow most open-source
wrappers still assume.

**The challenge script was checked for DOM dependencies before giving
up** — scanned the decoded JS for `document.`, `window.`, `navigator.`,
`localStorage`, `screen.`, `Intl.` — **none were found.** This means the
challenge is pure computation (likely hashing + string manipulation) and
is *theoretically* solvable with a lightweight JS engine (e.g. a
`PyMiniRacer`/embedded-V8 evaluation) rather than a full browser — this
project has precedent for exactly this class of solution (see
`.ai/CLAUDE.md`'s decision tree: "TikTok webmssdk → Node sidecar
X-Gnarly").

**Why this wasn't pursued further:** executing the challenge script only
gets you the *computed value* — actually using it requires knowing the
exact new wire protocol for submitting that value back to DuckDuckGo
(as a header on a retry request? in the `/chat` POST body? under what
key?), and this is undocumented, very recent, and has no publicly
available reference implementation yet. Reverse-engineering a brand-new
challenge-response protocol with zero ground truth (no real browser
available in this environment to observe a working exchange, per
`.ai/playbooks/reverse-engineer-internal-api.md`'s own workflow which
assumes DevTools access to a live session) was judged out of scope for
this build's time budget, versus a bounded, concrete Bing win already in
hand.

**Conclusion:** ruled out for now, but on different grounds than Google
— not an architectural JS-rendering wall, but an undocumented protocol
change that's plausibly reverse-engineerable with real browser
observation in a future session. Left here in detail specifically so a
future attempt doesn't have to re-discover any of this.

## Candidates considered and not attempted

- **ChatGPT / Claude / Gemini web apps**: no anonymous, no-login chat-
  completion path exists for any of the three — all require an
  authenticated session for a real query. Out of scope per this
  project's "No Login" constraint; not attempted.
- **Perplexity.ai**: reachable (confirmed homepage 200), but no public,
  no-login, no-API-key anonymous query path was identified during
  scoping (their official API requires a paid key) — not pursued
  further given the time budget already spent on the two investigations
  above; a candidate for a future round if a genuinely anonymous path is
  found.

## Known limits

- Bing results are capped at the top 10 — see above.
- Google AI Overview and DuckDuckGo AI Chat tracking are not available
  in this actor — see the two full investigations above. Don't
  re-attempt Google without a new angle (the header/proxy space is
  thoroughly exhausted); DuckDuckGo is worth revisiting if real browser
  DevTools observation of a working session becomes available.
- This actor can't distinguish "the target brand genuinely isn't the
  best fit for this query" from "the target brand isn't well-optimized
  for AEO" — that judgment call belongs to the human interpreting the
  results, not this actor.

## Diff cadence

Monthly smoke test recommended (the anti-decoy query pattern is worth
re-checking periodically in case Bing changes its heuristic).
