---
name: qa-testing
description: "Add regression QA to an Apify actor: seed a fixed input once, store a baseline, re-run, compare, report, push, and notify, to catch silent breakage when the target drifts. Use when building a QA runner for any actor or when an actor's output silently goes empty or wrong."
---

# Skill: QA Testing & Baseline Verification

## When to use
You're adding regression QA to an Apify actor (any actor — news scraper, data scraper, e-commerce, API wrapper, anything). The goal: catch silent breakage when the target site or upstream API drifts.

This skill teaches the **flow**. The implementation is always actor-specific because every actor has different input shapes, output shapes, and ways to acquire a stable test fixture. Read the actor first, then adapt.

---

## The core pattern

```
┌────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────┐    ┌──────────┐
│  SEED ONCE │──▶ │  STORE      │──▶ │  RE-RUN     │──▶ │  COMPARE │──▶ │  REPORT  │
│  (capture  │    │  baseline + │    │  with same  │    │  to      │    │  + push  │
│   input)   │    │  reference  │    │  input      │    │  baseline│    │  + notify│
└────────────┘    └─────────────┘    └─────────────┘    └──────────┘    └──────────┘
```

Key insight: **the test input is captured during seed and never changes**. That is what makes drift measurable — same input every run, only the actor's behavior varies.

Everything else (which fields to compare, how strict, how to acquire the input, how to notify) is actor-dependent.

---

## Before writing anything: scan the actor

Walk into the actor cold and answer these questions by reading code, not by guessing. Without these answers your QA runner will be wrong.

### 1. What does the actor accept as input?

Read `input_schema.json` (or the actor's docs / SDK input parsing). Identify:

- What's the **minimum input** to trigger one extraction? (a URL? a search query? a date range? an ID?)
- What "discovery" inputs does it support? (RSS feeds, sitemap, search-by-keyword, list-by-category, "latest N", etc.) — these are candidates for *acquiring* a fresh seed input
- Which inputs deterministically point at the **same record** across runs? (a fixed URL is deterministic; a "search for X, take first result" usually is not)

### 2. What does the actor output?

Run it once manually with a sample input. Look at the actual JSON. Identify:

- The **shape** — a single object? a list? nested wrapper (`{data: [...]}`)?
- The **stable fields** — title-equivalents, body-equivalents, ID-equivalents (these become fingerprint fields)
- The **volatile fields** — timestamps of *the scrape* (not of the record), random tracking tokens, ephemeral session cookies — exclude from fingerprint
- An **error signal** — does the actor put `{"error": "..."}` in output? `{"status": "error"}`? Both? Use that for the quality gate
- A **partial-success signal** — paywall preview vs full body, rate-limited vs ok, etc. — useful for `warning` field

### 3. How does the actor signal "no result"?

- Empty list? Empty object? Throws? Returns object with `error` key? Always check.

### 4. Can you reliably acquire a stable seed input?

Best to worst:
1. **Hardcoded canonical input** — the safest. Pick one record that's unlikely to disappear (a famous URL, a stable ID, etc.)
2. **Deterministic discovery** — e.g. "first result of a stable query" if the underlying list rarely changes
3. **Random-ish discovery** (`latest 1` from RSS) — works for online-news actors but creates fragile baselines; the seeded URL may go 404 in weeks

If you can only do #3, accept that baselines need periodic re-seeding.

### 5. Is the actor's CLI mode usable?

The runner spawns a subprocess. Confirm:

- Does `python main.py <input>` work outside of Apify, or does it require the Apify SDK to be running?
- Does it print **JSON only** to stdout (logs to stderr)? Or does it mix logs with output?
- Is the output JSON one record per line (NDJSON) or one big document?

If the CLI is messy, you have two options: tighten the CLI, or have the runner write input to a file and read output from a dataset folder.

---

## Build the runner: section-by-section template

The runner is one Python file at the repo root. Below is the *shape* of each section — the contents you fill in are entirely actor-driven.

### Imports & config

```python
import html, json, os, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import requests  # for the notification channel

ROOT = Path(__file__).parent
ACTORS_DIR = ROOT / "actors"
PY = sys.executable

EXTRACT_TIMEOUT = 120        # tune to your slowest actor
DISCOVERY_TIMEOUT = 60       # if you use discovery to acquire seeds
APIFY_PUSH_TIMEOUT = 300

# Force UTF-8 on child stdout. Windows defaults to cp1252 and crashes
# `print(json.dumps(...))` on unicode chars like zero-width space.
CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
```

### Actor registry

The list of actors under test. Each entry encodes everything actor-specific:

```python
ACTORS = [
    {
        "name": "<actor-dir-name>",
        "input_strategy": "fixed_url" | "discovery" | "borrow",
        # extra keys depend on strategy — see below
    },
    ...
]
```

Examples of how `input_strategy` materialises:

```python
# fixed input you typed yourself
{"name": "x", "input_strategy": "fixed_url",
 "test_input": "https://example.com/article/123"}

# actor exposes a 'latest N' or 'search' mode you can call to discover
{"name": "y", "input_strategy": "discovery",
 "discovery_args": ["latest", "1"], "input_field": "url"}

# this actor has no discovery; borrow input from another actor's discovery
{"name": "z", "input_strategy": "borrow",
 "borrow_from": "y"}
```

Whatever the strategy, the runner needs ONE function that returns `(input_value, error)` per actor.

### CLI runner

This is essentially universal — wrap subprocess and extract JSON:

```python
def run_actor_cli(actor_name, args, timeout):
    actor_dir = ACTORS_DIR / actor_name
    try:
        proc = subprocess.run(
            [PY, "main.py", *args],
            cwd=str(actor_dir),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, env=CHILD_ENV,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if proc.returncode != 0:
        return None, f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[:300]}"
    data = _extract_json(proc.stdout)
    return (data, None) if data is not None else (None, "no JSON in stdout")
```

`_extract_json()` greedily finds the first `{` or `[` in stdout and parses forward — tolerates a stray log line that leaked to stdout.

### Normalise + fingerprint

THIS is the actor-specific part. From the scan in step 2, you know the stable fields. Project to a flat dict:

```python
def normalize(data):
    # Adapt to actor's output shape. Examples:
    #   if data is a list: data = data[0] or {}
    #   if data wraps a record: data = data.get("data") or data
    #   if data has nested authors/tags: pull them flat
    return {
        "primary_key":  ...,   # the URL / ID / unique handle
        "title":        ...,   # something human-readable for the report
        "body":         ...,   # the largest free-text field
        # ... whatever else is stable + comparable
        "error":        data.get("error"),  # quality gate trigger
        "warning":      data.get("warning"),
    }
```

Fingerprint reduces the normalised dict to just the **shape** of the data — sizes, presence flags, counts. The exact keys depend on what's stable:

```python
def fingerprint(norm):
    return {
        "title_len":   len(norm["title"]),
        "body_len":    len(norm["body"]),
        "has_title":   bool(norm["title"]),
        "has_body":    bool(norm["body"]),
        # ... add counts/presence flags for every field you care about
    }
```

### Quality gate vs drift check

Two separate checks. Don't merge them.

```python
def quality_gate(fp, norm, actor_name):
    """Pre-conditions that must hold regardless of baseline."""
    if norm.get("error"):
        return False, f"actor error: {norm['error'][:120]}"
    if not fp["has_title"]:
        return False, "empty title"
    if fp["body_len"] < MIN_BODY_CHARS_OVERRIDES.get(actor_name, MIN_BODY_CHARS):
        return False, f"body too short ({fp['body_len']})"
    return True, "ok"

def compare_to_baseline(fp, baseline_fp):
    """Detect drift from previous-known-good output."""
    if baseline_fp["body_len"] > 0:
        ratio = fp["body_len"] / baseline_fp["body_len"]
        if ratio < DRIFT_MIN or ratio > DRIFT_MAX:
            return False, f"body drift {ratio:.2f}"
    for key in ("has_title", "has_body"):
        if baseline_fp.get(key) and not fp.get(key):
            return False, f"lost field: {key}"
    return True, "ok"
```

**Pick the thresholds by looking at the data.** If body length swings ±20% naturally between runs (publisher edits, currency conversions, etc.), use `[0.5, 3.0]` to leave headroom. If output is deterministic (e.g. API response), tighten to `[0.95, 1.05]`.

### Storage

One folder per actor, two files:

```
actors/<name>/storage/
├── qa_baseline.json     # written by seed, read by test
└── qa_last_result.json  # overwritten every test run (audit trail)
```

Both share the schema `{saved_at|ran_at, fingerprint, result}`. The runner auto-creates `storage/` via a `Path.mkdir(parents=True, exist_ok=True)` helper.

> Beware: the Dockerfile typically `COPY . ./` which ships `storage/` into the image. Either gitignore it, dockerignore it, or accept the small overhead.

### Apify push integration

```python
_PUSH_SUCCESS_MARKERS = (
    "Success: Actor was deployed",
    "Actor build detail",
    "ACTOR: Build finished",
)

def apify_push(actor_name):
    cmd = [shutil.which("apify") or shutil.which("apify.cmd"), "push", "-f"]
    proc = subprocess.run(cmd, cwd=str(ACTORS_DIR / actor_name),
                          capture_output=True, text=True,
                          timeout=APIFY_PUSH_TIMEOUT)
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    # apify-cli 1.5.0 on Windows+Node24 sometimes returns non-zero AFTER
    # a successful deploy. Scan for the deploy marker, ignore exit code.
    if any(m in combined for m in _PUSH_SUCCESS_MARKERS):
        return True, ""
    if proc.returncode == 0:
        return True, ""
    return False, combined.strip().splitlines()[-1][:200]
```

`-f` bypasses the "local older than remote" safety check. It does NOT reset stats, runs history, or builds history — it just stacks a new build over the existing actor.

### Notification channel

Whatever channel you use (Telegram, Slack, Discord, email), wrap it behind one function with signature `send(text: str) -> bool`. For HTML-formatted channels, escape every interpolated string — a stray `<` from a Python traceback or angle-bracketed tag will break the parser:

```python
def _esc(s): return html.escape(str(s), quote=False)
```

Chunk the message if the channel has a length limit (Telegram: 4096, Slack: 4000). Don't fail the whole notification because one chunk hit a transient 5xx — log and continue.

### Two commands

```python
python <runner>.py                  # run tests
python <runner>.py seed             # seed every actor
python <runner>.py seed <actor>     # (re)seed one actor
python <runner>.py seed <actor> <input>   # (re)seed with explicit input
```

`seed` writes baselines but does NOT push. `test` requires a baseline and pushes on PASS.

---

## What goes in the fingerprint vs what doesn't

| Output field type | Include in fingerprint? | Why |
|---|---|---|
| Stable primary content (article body, product description) | **Yes** — length, presence | Drift signal |
| Stable structured (price, rating, count, list size) | **Yes** — exact value if deterministic, value bucket if noisy | Drift signal |
| Authors / tags / categories | **Yes** — count, presence | Drift signal but not exact match |
| Published date of the record | Presence only | Editorial systems sometimes rewrite |
| **Scrape timestamp** | **No** | Different every run by design |
| Tracking IDs, session tokens | **No** | Different every run by design |
| Image CDN URL with cache-buster query string | Presence only (not the URL) | Hash changes each rebuild |
| Computed fields (word counts, paragraph counts) | **Yes** if deterministic | Catches selector/regex drift |
| `error` / `warning` | **No** in fingerprint — uses them in `quality_gate` instead | Quality signal, not drift |

---

## Common failure modes & how to read them

| Failure reason | Cause | Remedy |
|---|---|---|
| `no JSON in stdout` | Actor printed logs to stdout before JSON, or crashed | Run the actor manually with the same input; fix CLI or extractor |
| `exit N: ...` | Actor crashed | Read stderr; fix at source |
| `timeout` | Actor slower than `EXTRACT_TIMEOUT` | Profile and optimise, or bump the timeout |
| `body too short (X chars, min Y)` | Quality gate failed | Site changed schema; re-extract; OR override per-actor minimum |
| `body drift R.RR` | Drift check failed | Re-run the actor manually; inspect output vs baseline; fix or re-seed |
| `actor error: ...` | Actor reported its own error | Look at the actor's logs/upstream |
| `push failed: Actor is already on platform and modified there` | `-f` not applied, or fail before push | Confirm push command uses `-f`; check `apify_push` invocation |
| Notification 400 / parse error | Unescaped `<` or other special char in rich text | Pipe every interpolated string through `_esc()` |

---

## Safe vs unsafe extensions

**Safe** — change without invalidating existing baselines:
- Add/remove/reorder entries in `ACTORS`
- Tune `MIN_*_CHARS_OVERRIDES`, `EXTRACT_TIMEOUT`, drift ratios
- Update `_PUSH_SUCCESS_MARKERS` when apify-cli changes its success line
- Swap notification channel (Telegram → Slack)

**Unsafe** — invalidates baselines, must re-seed:
- Add or rename a fingerprint key
- Change `normalize()` to project different fields
- Change baseline file location

When you do an unsafe change, run `python <runner>.py seed` to regenerate every baseline.

---

## Quick checklist: shipping QA for a new actor

1. Read input schema → know what input is required
2. Run actor once manually → know what output looks like
3. Identify stable fields (drift signal) and volatile fields (exclude)
4. Decide seed strategy (fixed input vs discovery vs borrow)
5. Add actor to `ACTORS` registry
6. Adapt `normalize()` if the actor's output shape isn't already covered
7. Seed once: `python <runner>.py seed <actor>`
8. Inspect `qa_baseline.json` — does it look right? If not, fix and reseed
9. Run a test cycle: `python <runner>.py` → confirm PASS
10. Let it run on a schedule; investigate the first FAIL

Once those ten things are true, the actor is part of the suite.

---

## Mental model: when to use this skill

This skill describes a **regression** QA pattern — same input, same expected shape, alert on drift. It's NOT:

- **Integration testing** — for end-to-end scenarios, use Apify's run history + alerts
- **Coverage testing** — for "does the actor handle URL pattern X", maintain a separate fixture suite
- **Load testing** — for performance, use Apify's run metrics

Regression QA is the cheapest signal that "the actor still works." Everything in this skill is in service of that one thing.
