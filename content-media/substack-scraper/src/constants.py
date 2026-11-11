"""Endpoints, headers -- all in one place.

Recon summary (2026-08-29): every Substack publication (both `*.substack.com`
subdomains and custom domains like `www.noahpinion.blog`) proxies the same
internal JSON API at `/api/v1/...` on its own host -- confirmed live via a
plain `curl_cffi` request with an ordinary Chrome TLS profile, no WAF
challenge, no warmup request, no cookies. See CRAWLING_METHOD.md.

- `GET /api/v1/archive?sort=new|top&offset=<n>&limit=<n>` -- paginated post
  list for a publication. Each entry's `body_html` is always `null` here --
  archive listing is metadata-only.
- `GET /api/v1/posts/<slug>` -- full post detail, including `body_html`. For
  `audience: "only_paid"` posts, `body_html` is upstream's own free-preview
  truncation (cut off mid-paragraph) -- this actor does not attempt to
  bypass that; the `content_truncated` field on the record says so plainly.
- Publication profile (name, subdomain, custom_domain, hero_text, author,
  subscriber-count order of magnitude, etc.) is not exposed as public JSON
  (`/api/v1/publication` / `/api/v1/publication/self` both 403 "Not
  authorized" -- those require an authenticated session). It IS present,
  unauthenticated, as the `pub` key inside `window._preloads` embedded in
  the publication homepage HTML -- confirmed live. Used as S2-html for
  `archive` mode's one `PUBLICATION_PROFILE` record per publication.
"""

TLS_PROFILE = "chrome131"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}

SORT_VALUES = ["new", "top"]

ARCHIVE_PAGE_SIZE = 20

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Substack-injected CTA/boilerplate elements inside `body_html` that are not
# part of the author's own writing (Subscribe/Share/Leave-a-comment buttons,
# inline subscribe widgets). Stripped before Markdown conversion so the
# output is clean prose for AI ingestion -- see extractor.clean_body_html.
STRIP_CSS_CLASSES = ["button-wrapper", "subscription-widget-wrap", "subscription-widget"]
