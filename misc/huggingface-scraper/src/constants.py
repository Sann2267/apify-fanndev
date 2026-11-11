"""Endpoints, headers, enum whitelists -- all in one place.

Recon summary (2026-08-26): huggingface.co/api is Hugging Face's own
OFFICIAL, documented, public REST API (models/datasets/spaces/users/
organizations) -- like Civitai, not a reverse-engineered internal API.
It has NO WAF challenge of any kind: `curl_cffi` `chrome124` (just
`Accept: application/json`) gets clean 200s on every endpoint, no login/
API key needed for public repos.

Two real, confirmed platform behaviors (not bugs on our end):
1. **Pagination is a standard HTTP `Link` header** (`<url>; rel="next"`),
   same mechanism GitHub's API uses -- NOT a JSON `metadata`/`nextPage`
   field like Civitai. `src/client.py` parses this header directly.
2. **A nonexistent model/dataset repo returns HTTP 401** ("Invalid
   username or password"), not 404 -- confirmed on a real namespace with
   a fake model name, a fully-fake single-segment name, and a fake
   dataset name, all three returning the identical 401 body. This is a
   deliberate privacy-preserving ambiguity (indistinguishable from "repo
   exists but is private and you're not authorized") -- since this actor
   never sends credentials, every 401 on a repo-detail lookup is treated
   as `repo_not_found`, not a real auth failure. Genuine "not found" for
   a user/organization overview, by contrast, DOES return a clean 404
   with `{"error":"This user does not exist"}`.

Also confirmed: organizations and individual users are two DIFFERENT
endpoints (`/api/organizations/{name}/overview` vs
`/api/users/{username}/overview`) -- there is no single unified
"account" lookup. See CRAWLING_METHOD.md.

Rate limit (from response headers, anonymous/no-API-key): fixed window,
500 requests per 300 seconds (`ratelimit-policy: "fixed window";
q=500;w=300`). Retry/backoff on 429 respects this.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://huggingface.co/api"

DEFAULT_HEADERS = {
    "Accept": "application/json",
}

# Confirmed live via a bogus-value 400 ZodError-style response:
# {"error":"Invalid sort parameter: bogusSortValue"} -- these five are
# the only values that returned 200.
SORT_VALUES = ["downloads", "likes", "createdAt", "lastModified", "trendingScore"]
# Sent as a string on the wire (query params are always strings anyway,
# and the input schema uses a string enum since Apify's integer editor
# doesn't support "select" -- see input_schema.json).
DIRECTION_VALUES = ["-1", "1"]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
