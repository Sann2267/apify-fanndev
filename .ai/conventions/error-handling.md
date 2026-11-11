# Convention: Error Handling — Fail Loud Over Fail Silent

> **A scraper that returns `{}` for a missing field is worse than one that crashes.** Silent corruption produces datasets that look valid but contain garbage. Loud failures expose bugs immediately. This convention encodes the failure-mode discipline.

## The cardinal rule

**Catch only what you can recover from. Let everything else propagate.**

```python
# ❌ Don't do this — catches genuine bugs as if they were transient
try:
    data = parse_user(raw)
except Exception:
    return None

# ✅ Catch specific recoverable failures only
try:
    data = parse_user(raw)
except (KeyError, json.JSONDecodeError) as e:
    return {"_error": "parse_failed", "_errorDetail": str(e)}
# Lets ProgrammingError, network errors, etc. propagate to the worker loop
```

## Three categories of failure

### Category 1: Expected per-input failure (emit error record, continue)

The input itself is bad or the upstream entity doesn't exist:
- HTTP 404 (entity deleted)
- HTTP 410 Gone
- Empty result set despite valid request
- Schema-stable empty (e.g. `edges: []`)
- Specific upstream error codes (`{"error": "private_account"}`)

**Action:** emit error record with `_error: "not_found"` / `_error: "private"` / etc. Continue to next input.

```python
def fetch_one(item: str) -> dict:
    try:
        r = client.get(item)
    except NotFoundError:
        return {"_input": item, "_source": "none", "_error": "not_found"}
    return {"_input": item, "_source": "S1", **r}
```

### Category 2: WAF / rate-limit / transient (retry, then escalate)

- HTTP 403/429/503 from anti-bot
- TLS handshake failure
- Connection reset / read timeout
- Empty 200 body

**Action:** retry with backoff + profile rotation. If retry budget exhausted, emit error record with diagnostic detail.

```python
try:
    r = await client.get_with_retry(url)
except BlockedByWAF as e:
    return {
        "_input": item,
        "_source": "none",
        "_error": "blocked_by_waf",
        "_errorDetail": f"profile={e.profile} ip={e.ip} body_marker={e.marker!r}",
    }
```

### Category 3: Programming error / unexpected (raise, FAIL LOUD)

Schema changed upstream:
- Required field missing
- Wrong type (expected str, got list)
- Unknown enum value
- Apollo cache ref doesn't resolve

**Action:** raise `UnexpectedShape`. Do NOT emit a record. Do NOT continue silently. Let the worker loop log it; let the actor run finish with non-zero counts in failure metric.

```python
class UnexpectedShape(Exception):
    """Upstream returned a shape we don't recognize. Investigate before next run."""

def parse_user(raw: dict) -> dict:
    if "rest_id" not in raw:
        raise UnexpectedShape(f"Missing rest_id in raw user; got keys={list(raw.keys())}")
    if not isinstance(raw["rest_id"], str):
        raise UnexpectedShape(f"rest_id expected str, got {type(raw['rest_id'])}")
    return {
        "rest_id": raw["rest_id"],
        ...
    }
```

## Pydantic validators — fail loud at the type system

For high-reliability scrapers, Pydantic `extra="forbid"` raises automatically on shape changes:

```python
from pydantic import BaseModel, ConfigDict

class UserModel(BaseModel):
    model_config = ConfigDict(extra="forbid")    # ← rejects unknown fields
    
    rest_id: str
    screen_name: str
    followers_count: int
    bio: str | None = None

# Pydantic raises ValidationError if upstream adds/removes/retypes a field
try:
    user = UserModel.model_validate(raw)
except ValidationError as e:
    raise UnexpectedShape(str(e))
```

**Note:** for raw passthrough (see [`conventions/dataset-envelope.md`](dataset-envelope.md)), Pydantic with `extra="forbid"` is the WRONG choice. Use it for *internal* validation of upstream-parsed data, not for the dataset output shape.

## The `classify_response` pattern

For multi-strategy retry logic, classify before deciding what to do:

```python
def classify_response(r) -> str:
    """Returns one of: 'ok', 'retry', 'rotate', 'kasada', 'not_found', 'fatal'."""
    if r.status_code == 200:
        body_head = r.content[:8192]
        if any(m in body_head for m in BLOCK_MARKERS):
            return "rotate"
        if body_head == b"" or len(r.content) < 256:
            return "rotate"               # suspicious empty
        return "ok"
    
    if r.status_code == 404:
        return "not_found"
    
    if r.status_code == 429:
        if r.headers.get("x-kasada-tier"):
            return "kasada"               # explicit Kasada signal — needs Googlebot UA
        return "retry"                    # standard rate limit
    
    if r.status_code in (403, 407, 503):
        return "rotate"
    
    if r.status_code in (500, 502, 504):
        return "retry"
    
    return "fatal"


# Driver decides action per verdict
verdict = classify_response(r)
match verdict:
    case "ok":         return parse(r)
    case "not_found":  raise NotFound
    case "rotate":     await rotation_pool.rotate(); continue
    case "kasada":     raise KasadaBlocked              # circuit breaker
    case "retry":      await asyncio.sleep(backoff); continue
    case "fatal":      raise FatalHttpError(r.status_code)
```

## Circuit-breaker exceptions

For "I cannot proceed; ops must investigate" signals, define distinct exception types and let them propagate to the worker loop:

```python
class KasadaBlocked(Exception):
    """Kasada returned 429 even with Googlebot UA. Investigate immediately."""

class UnexpectedShape(Exception):
    """Upstream JSON shape changed. Schema may have rotated."""

class StaleDocIdError(Exception):
    """doc_id returned 400/404; auto-refresh failed."""

class AllProfilesBurned(Exception):
    """Every TLS profile in the pool returned a block. Pool needs refresh."""
```

These should **NOT** be caught at the worker level — they should crash the run and be visible in Apify logs. That's how ops finds out.

## Don't catch `Exception` broadly

```python
# ❌ Loses stack traces, hides bugs
try:
    do_something()
except Exception:
    return None

# ✅ List the specific exceptions you expect
try:
    do_something()
except (KeyError, ValueError, RecoverableHttpError) as e:
    log.warning(f"recoverable: {e}")
    return None
# Anything else propagates
```

## Per-input vs per-batch error boundaries

A worker processing 1000 inputs should:
- Wrap **each input** in its own try/except (Category 1 + 2 = emit error record)
- Let the **batch loop** see unhandled exceptions and crash the run (Category 3)

```python
async def worker_loop(items: list, client):
    for item in items:
        try:
            record = await process_one(item, client)
            await Actor.push_data(record)
        except (NotFound, BlockedByWAF, TransientError) as e:
            # Category 1 + 2 — emit error record
            await Actor.push_data({
                "_input": item, "_source": "none",
                "_error": type(e).__name__, "_errorDetail": str(e),
            })
        # Category 3: let UnexpectedShape, KasadaBlocked, AllProfilesBurned propagate
        # Worker loop crashes; Apify marks run as FAILED; ops gets alerted.
```

## Logging discipline

- Use `logging` module, not `print`. Apify captures logger output.
- Log levels:
  - `DEBUG` — verbose per-call traces (off by default)
  - `INFO` — phase markers (started, finished, X items processed)
  - `WARNING` — recoverable failures (rotation triggered, profile burned)
  - `ERROR` — unrecoverable failures (UnexpectedShape, KasadaBlocked)
- **Don't log credentials, proxy passwords, or full cookies.** Hash them if you need correlation IDs.

```python
import logging
log = logging.getLogger(__name__)

log.info(f"Processing {len(items)} items, max_concurrency={max_concurrency}")
log.warning(f"WAF rotation triggered: profile={profile} url={url}")
log.error(f"UnexpectedShape: missing required field 'rest_id' in {raw_keys}")
```

## Healthcheck-friendly error categorization

Apify dataset filter views can show error breakdown. Useful metric:

```sql
-- pseudo-SQL over the dataset
SELECT _error, COUNT(*) FROM dataset WHERE _error IS NOT NULL GROUP BY _error;
```

When this query suddenly shows 80% `blocked_by_waf` → WAF rotation is failing. 80% `not_found` → input list is stale. 5% `validation_failed` → schema drifted.

## What does NOT work

- ❌ `try: ... except Exception: pass`  — silently swallows everything
- ❌ Returning `{}` on parse failure  — pollutes dataset
- ❌ Returning `None` and filtering downstream  — loses traceability of which input failed
- ❌ Logging error and continuing without emitting a record  — input disappears from dataset, looks like nothing happened
- ❌ Re-raising as a different exception without preserving context  — loses stack trace
- ❌ Catching at top of `main()` (worker process never crashes, dataset accumulates `_error` records but nobody notices)

## Where used

- B2B Capterra (`UnexpectedShape` on missing JSON-LD required keys)
- Real-Estate Zillow (`KasadaBlocked` circuit breaker, `classify_response` verdicts)
- Pydantic validation across most actors with internal type discipline
- TikTok crawler (per-input error records, `_error` envelope discipline)
- Online News smart-news-loader (per-source `_error: "blocked_by_X"`)

## See also
- [`conventions/dataset-envelope.md`](dataset-envelope.md)
- [`skills/multi-strategy-fallback.md`](../skills/multi-strategy-fallback.md)
