"""Endpoints, headers, city map, constants -- all in one place.

Recon summary (2026-08-26): topcv.vn ("TopCV" -- Vietnam's largest job
board) is a classic server-rendered PHP/Laravel-style site, NOT a Next.js
SPA. Unlike its sibling `karir-com-scraper` (Indonesia), no public JSON
REST API could be found behind the search UI -- extensively tested with
every plausible query-param name (`keyword=`, `q=`, `location=`,
`locations=`, `l=`, `type_keyword=`) against several base paths
(`/tim-viec-lam-moi-nhat`, city pages); every one of them silently ignored
the parameter and returned the unfiltered result set. Confirmed live: the
site's own search form is a Vue-enhanced widget that, on submit, navigates
to a pretty "slug" URL rather than calling an XHR/JSON endpoint -- there is
no `__NEXT_DATA__`, no Apollo state, no `application/json` XHR to imitate.

So this actor's SEARCH strategy is SSR HTML with CSS selectors (S1-html
per this portfolio's tier system), using the site's own pretty-URL scheme
(reverse-engineered by testing many URL combinations live, see
CRAWLING_METHOD.md):

  keyword only:        /tim-viec-lam-{keywordSlug}
  city only (newest):  /tim-viec-lam-moi-nhat-tai-{citySlug}-l{cityId}
  keyword + city:      /tim-viec-lam-{keywordSlug}-tai-{citySlug}-kl{cityId}
  no filter (newest):  /tim-viec-lam-moi-nhat
  pagination:          ?page=N (1-based)

DETAIL pages, however, DO carry a complete public schema.org `JobPosting`
JSON-LD block (`<script type="application/ld+json">{"@type":"JobPosting"...`)
-- full description, requirements, benefits, salary, location, employer,
skills, experience, all with NO login/session required (confirmed live
with a bare `curl_cffi` GET, no cookies at all). Detail extraction is
therefore S1-jsonld, the highest-priority tier for this portfolio.

No WAF blocking was found -- topcv.vn sits behind Cloudflare (server:
cloudflare header present) but `curl_cffi chrome124` gets clean 200s with
full page content on homepage, search, and detail pages. The
`challenge-platform` string that appears in the homepage HTML is just
Cloudflare's benign passive bot-telemetry script tag
(`/cdn-cgi/challenge-platform/scripts/precursor/main.js`), not an active
JS challenge -- a real challenge page would be ~15KB, not the full
~1.2MB homepage this actor actually receives.
"""

TLS_PROFILE = "chrome124"

SITE_BASE = "https://www.topcv.vn"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Reverse-engineered live from the "-tai-{slug}-kl{id}" links present on
# every keyword search-results page (e.g. /tim-viec-lam-python -- the site
# renders a full "search by province" link list at the bottom of the
# results). This is topcv.vn's own city/province ID scheme -- id gaps
# (e.g. 41-43, 63) are real and match the site's own list, not omissions
# by this actor (likely retired/merged provinces after Vietnam's 2025
# administrative province merger). slug -> id.
CITY_IDS: dict[str, int] = {
    "ha-noi": 1,
    "ho-chi-minh": 2,
    "binh-duong": 3,
    "bac-ninh": 4,
    "dong-nai": 5,
    "hung-yen": 6,
    "hai-duong": 7,
    "da-nang": 8,
    "hai-phong": 9,
    "an-giang": 10,
    "ba-ria-vung-tau": 11,
    "bac-giang": 12,
    "bac-kan": 13,
    "bac-lieu": 14,
    "ben-tre": 15,
    "binh-dinh": 16,
    "binh-phuoc": 17,
    "binh-thuan": 18,
    "ca-mau": 19,
    "can-tho": 20,
    "cao-bang": 21,
    "cuu-long": 22,
    "dak-lak": 23,
    "dac-nong": 24,
    "dien-bien": 25,
    "dong-thap": 26,
    "gia-lai": 27,
    "ha-giang": 28,
    "ha-nam": 29,
    "ha-tinh": 30,
    "hau-giang": 31,
    "hoa-binh": 32,
    "khanh-hoa": 33,
    "kien-giang": 34,
    "kon-tum": 35,
    "lai-chau": 36,
    "lam-dong": 37,
    "lang-son": 38,
    "lao-cai": 39,
    "long-an": 40,
    "nam-dinh": 44,
    "nghe-an": 45,
    "ninh-binh": 46,
    "ninh-thuan": 47,
    "phu-tho": 48,
    "phu-yen": 49,
    "quang-binh": 50,
    "quang-nam": 51,
    "quang-ngai": 52,
    "quang-ninh": 53,
    "quang-tri": 54,
    "soc-trang": 55,
    "son-la": 56,
    "tay-ninh": 57,
    "thai-binh": 58,
    "thai-nguyen": 59,
    "thanh-hoa": 60,
    "thua-thien-hue": 61,
    "tien-giang": 62,
    "tra-vinh": 64,
    "tuyen-quang": 65,
    "vinh-long": 66,
    "vinh-phuc": 67,
    "yen-bai": 68,
}

# Human-readable Vietnamese names for a handful of cities users are most
# likely to type verbatim in `city` input (falls back to slugifying
# whatever the user typed if not found here -- see extractor.resolve_city).
CITY_NAMES: dict[str, str] = {
    "ha-noi": "Hà Nội",
    "ho-chi-minh": "Hồ Chí Minh",
    "da-nang": "Đà Nẵng",
    "hai-phong": "Hải Phòng",
    "can-tho": "Cần Thơ",
    "binh-duong": "Bình Dương",
    "dong-nai": "Đồng Nai",
    "bac-ninh": "Bắc Ninh",
}
