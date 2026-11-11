# Troubleshooting playbook

Look up the symptom, follow the fix. Always check
[PROBLEMS.md](PROBLEMS.md) for the root cause analysis after you
apply the fix.

## Build fails

### `Input schema is not valid (Field schema.properties.<X>.description is required)`
Add a `description` (and ideally `editor`) field to property `<X>` in
`.actor/INPUT_SCHEMA.json`. See [CONSTRAINTS.md](CONSTRAINTS.md).

### `Description must be at most 300 characters long`
Shorten `.actor/actor.json` → `description`. The hard cap is 300.

### `By launching this job you will exceed the memory limit of 8192MB`
Wait for any in-flight Apify builds to finish, then retry serially.
Free-tier accounts cap concurrent build memory at 8 GB.

### `AttributeError: module 'browserforge.download' has no attribute 'DATA_FILES'`
Pin `browserforge == 1.2.3` in `requirements.txt`. 1.2.4 broke
crawlee's workaround.

### `Error: The CLI encountered an unhandled argument parsing error!` (exit code 1) on push or call
**This is almost certainly a false error.** Grep the log output for:
- `Build finished` followed by `Success: Actor was deployed` → push succeeded
- `Actor finished` followed by `Export results:` → call succeeded

Known bug in `apify-cli 1.5.0`.

## Run fails

### stderr prints `Impersonate '<name>' does not exist, using 'random'`
The `primp` build doesn't ship that profile template, so it served a
**random** JA3 — which WAFs block. The profile name in `fingerprint.py`
is stale for the installed `primp` version. Remap to a valid name (on
`primp 1.2.2`: `chrome_144/145/146`, `firefox_140/146/147/148`,
`edge_144/145/146`, `safari_26`). The warning fires only **once per
process** — test validity with a fresh process per name. See
[PROBLEMS.md](PROBLEMS.md#primp-stale-profile-names-silently-fall-back-to-random-2026-05-30).

### Actor returns `error: "BLOCKED_AFTER_RETRIES"`
1. Check if local IP is WAF-flagged: try a different residential proxy.
2. Increase `maxRequestRetries` (default 6 is sometimes not enough on
   freshly-flagged IPs).
3. For AliExpress: verify the proxy is RESIDENTIAL — datacenter IPs
   are nearly always blocked.
4. For Walmart: PX often clears on attempt 2 — bump retries before
   investigating.

### Actor returns `error: "CSR_SHELL"` (AliExpress)
This is the documented limitation. The product HTML page is now
fully CSR; full data needs MTOP which is Baxia-gated. See
[INVESTIGATIONS/BAXIA_2026.md](INVESTIGATIONS/BAXIA_2026.md). The
productId + finalUrl are still emitted — downstream consumers can
use those.

### MTOP returns `FAIL_SYS_USER_VALIDATE` + `RGV587_ERROR`
Baxia challenged the request. `_baxia_sec_cookie_.tfstk` is missing.
No HTTP-only fix — out of scope. Pivot data source: try
shoprenderview (works for review aggregates + store products).

### MTOP returns `FAIL_SYS_TOKEN_EMPTY`
Either: (a) the `_m_h5_tk` cookie isn't being sent (curl_cffi cookie
propagation bug — plant the cookie BEFORE the first request) or (b)
the proxy IP is a datacenter IP that Baxia categorically rejects
before the token check (use RESIDENTIAL proxy).

### shoprenderview returns 1.8 KB body with `x5secdata`
Baxia challenged this specific call. Rotate proxy IP and retry. Page
1 is usually clean from a fresh residential IP; page 2+ flaky.

### `parsed 0 items` from search/category
1. Check that `_init_data_` is in the body (`grep _init_data_`).
2. Path drift — try the fallback `_extract_items_direct` (regex finds
   `"itemList":{"content":[` and walks the array).
3. Verify the body is not a Baxia challenge (length < 2 KB → almost
   certainly a challenge).

### Test_local.py prints garbled characters on Windows
Add at the top:
```python
import sys, io
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass
```

## Validation fails (`qa_actors.py`)

### Field missing from output
1. Sample the live HTML/JSON for the field (use one of the
   `sample-*.json` files in the actor folder if present).
2. Check if the upstream API removed the field (verified in 2026:
   `store`, `seller`, `shop` removed from AliExpress listings).
3. If field is path-drifted: add the new path to the fallback list
   in the parser (use `_safe(it, ["data", "root", ...])` candidates).

### `0 rows emitted`
Always means an exception ate the row OR the parser returned an
empty list. Check Actor.log for warnings around the input.

## Telegram QA notif fails

### `Forbidden: bot was blocked by the user`
The bot has been blocked by the recipient. Recipient must
`/start` the bot before it can DM them.

### `Bad Request: chat not found`
The `user_id` is wrong, or the user has never interacted with the bot.
The recipient must DM the bot once (typically `/start`) before the bot
can message them.

### `Too Many Requests: retry after N`
Telegram rate-limit. Sleep `N` seconds and retry.
