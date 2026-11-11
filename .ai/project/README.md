# `project/` — Context for the 24-actor e-commerce suite

Generic, reusable scraping knowledge lives one level up in `.agents/`
(`anti-bot/`, `skills/`, `playbooks/`, `stacks/`, `conventions/`).
**This folder is the project-specific memory** for *this* codebase: the
24 Python Apify actors across 6 platforms (StockX, Alibaba, AliExpress,
Walmart, eBay, Etsy).

## Read order

1. **[SCRAPERS.md](SCRAPERS.md)** — canonical list of every actor, its
   status (working / degraded / blocked), Apify actor ID, and what each
   returns. Always start here.
2. **[CONSTRAINTS.md](CONSTRAINTS.md)** — hard rules that bind this
   codebase: HTTP-only, no browser, no exported cookies. Re-read before
   proposing architectural changes.
3. **[CRAWLING_METHOD.md](CRAWLING_METHOD.md)** — the actual patterns
   used across all six platforms (primp vs curl_cffi, when to sign, how
   to extract data islands, WAF marker registry).
4. **[PROBLEMS.md](PROBLEMS.md)** — every non-obvious blocker hit and how
   it was resolved (or why it can't be).
5. **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — symptom → fix lookup
   table. When a build/run/QA fails, start here.
6. **[BUILD_REPORT.md](BUILD_REPORT.md)** — chronological change log with
   empirical findings, sample API captures, verified output schemas.
7. **[SKILLS.md](SKILLS.md)** — competencies a future agent needs to
   maintain or extend this codebase.
8. **[INVESTIGATIONS/](INVESTIGATIONS/)** — deep technical reports for
   single complex problems (currently: AliExpress Baxia WAF).
9. **[CLOUD_REQUIREMENTS.md](CLOUD_REQUIREMENTS.md)** — which actors run
   fine locally vs which need Apify + a RESIDENTIAL proxy (the WAF blocks
   datacenter ASN). Check before scheduling or estimating proxy cost.
10. **[ACTOR_IDEAS_2026.md](ACTOR_IDEAS_2026.md)** — planning doc: high-ROI /
    low-competition new-actor ideas, filtered by the "rare data-type +
    reuse our anti-bot moat" pattern. Nothing built yet.

## Quick orientation

- **24 Python Apify actors**, every one following the same template:
  `src/{main,parser,fingerprint}.py`, `.actor/{actor,INPUT_SCHEMA}.json`,
  `test_local.py`, `requirements.txt`.
- Transport is **hybrid**: `primp` (Rust/BoringSSL) for no-proxy local
  runs, `curl_cffi` (curl-impersonate) for proxy runs. No Selenium /
  Playwright / Puppeteer anywhere — see [CONSTRAINTS.md](CONSTRAINTS.md).
- Every actor emits at least one row per input (diagnostic-error rows for
  blocked URLs). Silent failure is forbidden.
- AliExpress is the most aggressively WAF-protected and has its own
  investigation: [INVESTIGATIONS/BAXIA_2026.md](INVESTIGATIONS/BAXIA_2026.md).

## Tools to know

- **`qa_actors.py`** (project root) — runs `test_local.py` for every
  actor, validates output schemas, optionally posts a Telegram summary.
  Run after any substantive change. WAF-blocked platforms (AliExpress,
  eBay, Etsy, Alibaba product) report `waf` locally — that is the
  expected state; they pass on Apify with a RESIDENTIAL proxy.
- **`apify push --force`** is the deploy command. The CLI has a benign
  post-success exit-code bug — read the build log, not the exit status.
- **Memory** at `~/.claude/projects/c--Han-portfolio-2026-e-commerce/memory/`
  holds this agent's persistent per-conversation state.
