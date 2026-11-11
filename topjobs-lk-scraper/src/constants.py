"""Endpoints, headers, constants -- all in one place.

Recon summary (2026-08-26): topjobs.lk is Sri Lanka's leading job board, an
*old-generation* server-rendered JSP/Tomcat app (`Server: Apache-Coyote/1.1`,
`X-Powered-By: JSP/2.2`) -- not a Next.js/React SPA like most recent targets
in this portfolio. Both the search-results listing and the job detail view
are classic full-page HTML responses with no client-side JS needed to see
the data. No WAF of any kind was found -- even a bare `requests.get()` with
no TLS impersonation and no headers returns 200 with full content. This
actor still uses `curl_cffi chrome124` per portfolio convention (cheap
insurance, no measured downside).

`https://topjobs.lk/robots.txt` does not exist as a file at all -- it 302s
to `index.jsp?ErrorURL=y` (the site's generic "page not found" handler, the
same behavior as requesting `/sitemap_index.xml` or any other missing path).
Confirmed independently with a bare `curl_cffi` GET and `allow_redirects=False`
(302 Location header points at the error page, not a robots.txt body). No
robots.txt means no crawl restrictions are declared for any user agent,
Claude included -- there is nothing to honor or violate.

## Search / browse

`GET /applicant/vacancybyfunctionalarea.jsp` is both the "browse by
category" page AND the keyword-search results page -- same endpoint, driven
by query params (confirmed live; the homepage's own search form POSTs here,
and its own category links GET here with `?FA=<code>`):

    https://topjobs.lk/applicant/vacancybyfunctionalarea.jsp
        ?FA=<code>          -- functional-area code (browse mode), see FUNCTIONAL_AREAS
        &txtKeyWord=<kw>    -- free-text keyword (search mode)
        &jst=OPEN           -- job status; always sent (matches the site's own
                                 pagination links) though live testing found no
                                 measurable difference vs. omitting it
        &chkGovt=Y          -- optional checkbox filters (any combination)
        &chkNGO=Y
        &chkParttime=Y
        &chkWalkin=Y
        &chkForeign=Y
        &chkInternship=Y
        &pageNo=<n>         -- 1-indexed page number

**Confirmed quirk: `FA` and `txtKeyWord` are mutually exclusive, `FA` wins.**
Live-tested `FA=SDQ&txtKeyWord=zzznonexistentxyz123` still returned the full
176-job SDQ category count unfiltered -- when `FA` is non-empty the server
ignores `txtKeyWord` entirely (verified with both a real keyword and a
guaranteed-no-match keyword, same count both times). The checkbox filters DO
combine correctly with `txtKeyWord` (e.g. `txtKeyWord=accountant&chkWalkin=Y`
legitimately returned 0 -- a real empty intersection, not a broken query).
This actor lets the caller set both, but documents (README) that `FA`
silently overrides `keyword` server-side, matching the site's own behavior.

**Page size is 1000 results/page** (not the `blockSize` hidden form field,
which the server ignores -- tested `blockSize=18`, still got hundreds of
rows back in one response). The total-count comment
`<!-- 1 - 1000 of 5865 job(s) -->` and the `(N) Jobs` span give the true
total; this actor paginates via `pageNo` until it has fetched `maxResults`,
hit an empty page, or `pageNo * 1000 >= total`.

## Job detail

    https://topjobs.lk/employer/JobAdvertismentServlet
        ?rid=<row-index-in-search-results>   -- cosmetic, not required for the
                                                  lookup to succeed (tested rid=0
                                                  arbitrarily against every jc)
        &jc=<job-code>       -- e.g. 0001541024 -- the job's unique ID
        &ac=<agent-code>     -- e.g. DEFZZZ or 0000000375
        &ec=<employer-code>  -- e.g. DEFZZZ or 0000000492
        &pg=applicant/vacancybyfunctionalarea.jsp

**`jc` alone is not enough** -- `ac` and `ec` must be the exact values that
came with that `jc` from a search result. Confirmed live: `jc` with no
`ac`/`ec` at all, and `jc` with a mismatched `ac`/`ec` pair (`DEFZZZ`/`DEFZZZ`
against a `jc` that actually belongs to `ac=0000000385`/`ec=0000000505`),
both redirect (302) to `util/errorPage.jsp?errCode=601` rather than returning
the job. There is no shorter canonical per-job URL anywhere on the site (no
`og:url`, no canonical link) -- the `JobAdvertismentServlet?...` URL *is*
the canonical link, matching what a person would copy out of their browser's
address bar after clicking a listing. This actor's `detail` mode therefore
takes that exact URL (or the jc/ac/ec triple) as input, and `search` mode's
own output includes a ready-to-reuse `detailUrl` for every record.

**The "job description" is a raster image, not text.** Every one of 6
sampled detail pages across different employers/categories rendered the job
ad as `<img src="/logo/<employer-code>/<file>.png|jpg">` inside `#remark`
-- this is topjobs.lk's actual publishing model (employers upload a
designed ad graphic rather than filling in a text field), not a login gate.
The image itself is fully public -- no session/cookie/auth needed to fetch
it (confirmed: a bare `curl_cffi` GET with no cookies returns the same page).
A `<script type="application/ld+json">` `JobPosting` block is present on
*some* (not all -- roughly half of sampled pages) detail pages with a
placeholder `description` string pointing back at the image
("Please refer the full details of the job posting..."); it is captured
raw as a bonus field when present, but the HTML fields below (title,
employer, location, closing date, job ref, job-type badges, description
image URL) are the primary/reliable source used on every record.

Confirmed structured fields available on every detail page (BeautifulSoup
id selectors): `#position` (title), `#employer` (company name, also its
`title` attr), `#endDate` (closing date), `#jobRefNum`,
`#adview-job-location` (town/country), `.lbl_fulltime` labels (0-3 dynamic
badges -- confirmed varies per job: e.g. "Part Time" alone vs.
"Full Time"/"Permanent"/"Onsite" together), `#remark img[src]` (description
image), `#logo[src]` (employer logo), `#url[href]` (employer website, often
empty), `#txtAVECompanyEmail[value]` (employer contact email, often present
even though the "Apply by email" form itself needs no login to view).

**Not-found behavior:** an invalid/mismatched `jc`+`ac`+`ec` triple 302s to
`util/errorPage.jsp?errCode=601` (not a 404). `src/main.py` detects this via
the final response URL after following redirects.
"""

TLS_PROFILE = "chrome124"

SITE_BASE = "https://topjobs.lk"
SEARCH_URL = f"{SITE_BASE}/applicant/vacancybyfunctionalarea.jsp"
DETAIL_URL = f"{SITE_BASE}/employer/JobAdvertismentServlet"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# The site's own listing-page size -- confirmed live via the
# "<!-- 1 - 1000 of 5865 job(s) -->" HTML comment on an unfiltered browse.
# The `blockSize` hidden form field (18 in the site's own UI) has no effect
# on the server response -- tested and ignored.
PAGE_SIZE = 1000

# Functional-area codes -- scraped directly from the homepage's own
# category panel (`applicant/vacancybyfunctionalarea.jsp?FA=<code>` links).
# Setting FA overrides/ignores `keyword` server-side -- see module docstring.
FUNCTIONAL_AREAS = {
    "SDQ": "IT-Sware/DB/QA/Web/Graphics/GIS",
    "HNS": "IT-HWare/Networks/Systems",
    "ACA": "Accounting/Auditing/Finance",
    "BAF": "Banking & Finance/Insurance",
    "SMM": "Sales/Marketing/Merchandising",
    "HAT": "HR/Training",
    "COM": "Corporate Management/Analysts",
    "OAS": "Office Admin/Secretary/Receptionist",
    "CCE": "Civil Eng/Interior Design/Architecture",
    "ITT": "IT-Telecoms",
    "CUR": "Customer Relations/Public Relations",
    "LWT": "Logistics/Warehouse/Transport",
    "MAE": "Eng-Mech/Auto/Elec",
    "POS": "Manufacturing/Operations",
    "MAC": "Media/Advert/Communication",
    "HRF": "Hotel/Restaurant/Hospitality",
    "HOT": "Travel/Tourism",
    "SRF": "Sports/Fitness/Recreation",
    "MHN": "Medical/Nursing/Healthcare",
    "LEL": "Legal/Law",
    "SQC": "Supervision/Quality Control",
    "APC": "Apparel/Clothing",
    "AIM": "Ticketing/Airline/Marine",
    "TAL": "Education",
    "RLT": "R&D/Science/Research",
    "AGD": "Agriculture/Dairy/Environment",
    "SEC": "Security",
    "BEC": "Fashion/Design/Beauty",
    "IDV": "International Development",
    "KPO": "KPO/BPO",
    "IME": "Imports/Exports",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
