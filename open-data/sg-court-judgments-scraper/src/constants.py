"""Endpoints, headers, constants -- all in one place.

Recon summary (2026-08-31): elitigation.sg is the Singapore Judiciary's
official "Grounds of Decision" (GD) portal -- the free, public full-text
archive of Singapore court judgments. It is a plain ASP.NET MVC app:
server-rendered HTML, GET-only pagination, **no `__VIEWSTATE`**, no WAF,
no challenge, no login, and no cookie gate. `curl_cffi` `chrome124` gets
clean 200s on the listing and every judgment page; 5 rapid sequential
requests all returned 200 in 0.10-0.32s each with no rate-limit response.

`robots.txt` returns **404** (IIS "File or directory not found") -- the
site declares no crawler restrictions at all, so there is no AI-bot
directive to honour or violate.

Two endpoints matter:
- `GET /gd/Home/Index?...` -- the judgment listing. 10 results per page,
  paginated purely by `CurrentPage`. Each result card carries catchwords
  (the court's own legal-topic tags), case title, neutral citation,
  decision date, and case number.
- `GET /gd/s/<judgmentId>` -- one judgment's full text (e.g.
  `/gd/s/2026_SGHC_175`), inside `#divJudgement`. Observed ~111k
  characters of full opinion text on a single commercial judgment.

**Coverage confirmed live:** 1,594 listing pages x 10 = ~15,900 judgments,
and page 1594 returns `/gd/s/1965_SGHC_6` -- the archive genuinely spans
**1965 to present**. Despite the filter value being named `SUPCT`, the
listing covers the whole "SG Courts Judgments" corpus (civil, criminal,
and family matters all appear in the results).

See CRAWLING_METHOD.md for full recon detail and captured examples.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.elitigation.sg"
SEARCH_URL = f"{BASE_URL}/gd/Home/Index"
JUDGMENT_URL = f"{BASE_URL}/gd/s"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-SG,en;q=0.9",
}

# The listing's own filter value. Only "SUPCT" returns results -- other
# guesses (STATECT, FAMCT, ALL) all render 0 cards, and SUPCT already
# carries the full corpus, so it is fixed rather than exposed as an input.
COURT_FILTER = "SUPCT"

RESULTS_PER_PAGE = 10

# Confirmed live: the listing's own last-page link is 1594. Kept as a
# sanity stop so a pagination bug can never spin forever.
MAX_PAGE_SANITY_CAP = 2000

SORT_FIELDS = ("DateOfDecision", "Title")

REQUEST_TIMEOUT = 45

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
