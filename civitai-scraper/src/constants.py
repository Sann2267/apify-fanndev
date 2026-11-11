"""Endpoints, headers, enum whitelists -- all in one place.

Recon summary (2026-08-26): civitai.com/api/v1 is Civitai's own OFFICIAL,
documented, public REST API (models/model-versions/images/creators/tags)
-- unlike most targets in this portfolio, this is not a reverse-engineered
internal API. It has NO WAF challenge of any kind: `curl_cffi` `chrome124`
(no special headers beyond `Accept: application/json`) gets clean 200s on
every endpoint, no login/API key needed for public data, no rate-limit hit
across 15 rapid sequential requests. Zod validation errors on bad
query-param values are extremely well-behaved -- they list every valid
enum member directly in the 400 response body, which is how every enum
whitelist below was confirmed (not guessed).

One deliberate, documented restriction found: the public/unauthenticated
`/images` endpoint always returns `meta: null` (generation
prompt/sampler/seed/etc.) regardless of the image's own `hasMeta: true`
flag seen elsewhere -- this is Civitai's own privacy choice, not
something to route around. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://civitai.com/api/v1"

DEFAULT_HEADERS = {
    "Accept": "application/json",
}

# Hard platform ceiling confirmed live: `limit` > 100 returns a 400
# ZodError on both /models and /images.
MAX_LIMIT = 100

# Confirmed live via Zod validation-error probing (each 400 response lists
# every valid enum member directly -- no guessing needed).
MODEL_SORT_VALUES = [
    "Highest Rated",
    "Most Downloaded",
    "Most Liked",
    "Most Discussed",
    "Most Collected",
    "Most Images",
    "Newest",
    "Oldest",
]
MODEL_PERIOD_VALUES = ["Day", "Week", "Month", "Year", "AllTime"]
MODEL_TYPE_VALUES = [
    "Checkpoint",
    "TextualInversion",
    "Hypernetwork",
    "AestheticGradient",
    "LORA",
    "LoCon",
    "DoRA",
    "Controlnet",
    "Upscaler",
    "MotionModule",
    "VAE",
    "TextEncoder",
    "UNet",
    "CLIPVision",
    "Poses",
    "Wildcards",
    "Workflows",
    "ComfyWorkflows",
    "Detection",
    "VisionLanguage",
    "CLIP",
    "LLM",
    "Other",
]
IMAGE_SORT_VALUES = ["Most Reactions", "Most Comments", "Most Collected", "Newest", "Oldest", "Random"]
IMAGE_NSFW_VALUES = ["None", "Soft", "Mature", "X", "Blocked"]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
