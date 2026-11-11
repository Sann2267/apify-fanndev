# Constraints — what this codebase does and does not do

These are hard architectural rules. Treat them as non-negotiable unless
the user explicitly relaxes them.

## ✅ DO

- Use **`curl_cffi`** (TLS impersonation) when a proxy is configured.
- Use **`primp`** (Rust/BoringSSL) when no proxy is configured.
- Rotate impersonation profiles (`chrome131`, `safari17_0`, etc.) on
  WAF-block markers, not just status codes.
- Pre-plant locale cookies (`aep_usuc_f`, `xman_us_f`, `intl_locale`)
  before the first request — many gateways will redirect or 404 if
  these are missing.
- Detect blocks by **body markers** (`punish.html`, `_____tmd_____`,
  `baxia-manager`, `x5secdata`, `FAIL_SYS_*`, `RGV587_ERROR`,
  PerimeterX `_pxhd` script), not only HTTP status — many WAFs return
  200 with a challenge body.
- Emit at least one row per input. Diagnostic-error rows
  (`error: "CSR_SHELL"`, `error: "BLOCKED_AFTER_RETRIES"`,
  `error: "NOT_FOUND"`, `error: "EMPTY_PAYLOAD"`) are preferred over
  silent skip — downstream consumers must always see a row.
- Pin `browserforge == 1.2.3` in `requirements.txt`. 1.2.4 broke the
  `crawlee._browserforge_workaround` shim with `module 'browserforge.download'
  has no attribute 'DATA_FILES'`.
- Every `INPUT_SCHEMA.json` property MUST have a `description` field.
  Apify rejects schemas without it (`Field schema.properties.<name>.description is required`).

## ❌ DO NOT

- **DO NOT** use Playwright / Selenium / Puppeteer /
  undetected-chromedriver / any browser automation. The constraint is
  HTTP-only.
- **DO NOT** require login / authenticated sessions / manual CAPTCHA
  solving.
- **DO NOT** invest more time in reverse-engineering the Baxia
  `tfstk` token. It rotates monthly and has been empirically
  unobtainable HTTP-only across 10+ probe rounds (see
  [INVESTIGATIONS/BAXIA_2026.md](INVESTIGATIONS/BAXIA_2026.md)).
- **DO NOT** silently swallow exceptions in parsers. Wrap in
  try/except and emit a diagnostic row.
- **DO NOT** use `--no-verify` or skip pre-commit hooks. Fix the
  underlying issue.
- **DO NOT** treat `Error: The CLI encountered an unhandled argument
  parsing error!` from `apify push` as a real failure — the CLI has a
  known JSON-input parse bug that fires *after* a successful deploy.
  Always check the log for `Build finished` + the `Success: Actor was
  deployed` line.

## Why these matter (incident history)

| Rule | Triggered by |
|---|---|
| Pin browserforge 1.2.3 | aliexpress-review-scraper build 0.1.1 crashed on `AttributeError: module 'browserforge.download' has no attribute 'DATA_FILES'` (2026-05-16) |
| INPUT_SCHEMA description required | aliexpress-store-scraper build 0.1.1 rejected for missing `country.description` (2026-05-15) |
| Don't pursue Baxia HTTP bypass | Builds 1.0.12 → 1.0.20 of the product-scraper iterated on Baxia token tricks; all proved Baxia structurally requires JS execution |
| Body-marker block detection | Walmart PerimeterX returns 200 with 15 KB challenge body; status-only detection passed bad data silently |
| Diagnostic-error rows | User complained "data null semua" — downstream joins broke when scraper silently returned empty datasets |
