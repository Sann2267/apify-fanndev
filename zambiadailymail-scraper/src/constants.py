"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): daily-mail.co.zm (Zambia Daily Mail, state-owned
national daily) shows NO active WAF challenge. `curl_cffi` `chrome124` gets a
clean 200 -- zero cookies set -- on the homepage, article pages, and the
WordPress REST API. Plain `nginx` reverse proxy in front of PHP, no
Cloudflare/Akamai/DataDome/PerimeterX markers. Bare `daily-mail.co.zm`
301-redirects to the canonical `www.daily-mail.co.zm` host (WordPress-issued
redirect, `X-Redirect-By: WordPress`). robots.txt has a SINGLE
`User-agent: *` group (`Disallow: /wp-admin/`, `Allow:
/wp-admin/admin-ajax.php`) -- no Babak-14 merged-Disallow-block risk. No
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai token
appears anywhere in the file.

**Critical quirk -- collection-endpoint query strings are silently ignored.**
`/wp-json/wp/v2/posts?slug=...`, `?search=...`, `?categories=...`,
`?include=...`, `?per_page=...`, and `?page=...` all return the exact same
unfiltered "latest 10" list regardless of the query string (confirmed by
requesting four different `slug` values, including nonsense strings, and
getting back identical results with `X-WP-Total: 1478` -- i.e. the whole
site's post count, meaning the filter is not applied server-side at all).
The site's default WordPress feed (`/feed/`) and `?paged=N` pagination on it
are equally broken -- `/feed/` and `/feed/?paged=2` return byte-identical
item lists. `wp-sitemap.xml` (advertised in robots.txt) 501s outright
(`Could not generate XML sitemap due to missing SimpleXML extension` --
a genuine server misconfiguration, not a bot block). See CRAWLING_METHOD.md
for the full paper trail. Because of this:
  - Article lookup by URL cannot use `?slug=`. Instead, the article's own
    HTML page carries `<link rel="alternate" type="application/json"
    href="https://www.daily-mail.co.zm/wp-json/wp/v2/posts/<id>">` in
    `<head>` (WordPress's standard REST-discovery link) -- fetch the HTML
    once to read the numeric post ID out of that link, then hit the
    **singular** `/wp-json/wp/v2/posts/<id>` endpoint, which -- unlike the
    collection endpoint -- returns the correct single post every time
    (verified against two distinct real article URLs).
  - `latest` mode cannot use the RSS feed or the REST collection endpoint at
    all (both stuck on the same static 10 items). Instead it paginates the
    **category archive page** for the "Headlines" category (id 18, present
    on every sampled post -- effectively the site's global latest-news feed,
    confirmed to match the RSS/API default-10 order), whose pagination is
    real, path-based (`/category/headlines/page/N/`), and was confirmed to
    return zero-overlap, chronologically-continuing article sets across at
    least 3 pages, with a clean 404 past the end.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.daily-mail.co.zm"
WARMUP_URL = f"{BASE_URL}/"

# WordPress REST API -- singular endpoints only (collection endpoints ignore
# all query strings on this site, see module docstring). Public,
# unauthenticated, not disallowed by robots.txt.
WP_API_POST_BY_ID = BASE_URL + "/wp-json/wp/v2/posts/{post_id}"
WP_API_USER_BY_ID = BASE_URL + "/wp-json/wp/v2/users/{user_id}"
WP_API_MEDIA_BY_ID = BASE_URL + "/wp-json/wp/v2/media/{media_id}"
WP_API_CATEGORY_BY_ID = BASE_URL + "/wp-json/wp/v2/categories/{cat_id}"
WP_API_TAG_BY_ID = BASE_URL + "/wp-json/wp/v2/tags/{tag_id}"

# "Headlines" category archive -- the site's de-facto global latest-news
# feed (RSS/REST collection are both stuck on a static top-10, see above).
# Real path-based pagination: page 1 has no suffix, page N is
# `/page/N/`.
LATEST_CATEGORY_URL = f"{BASE_URL}/category/headlines/"
LATEST_ITEMS_PER_PAGE = 10

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
