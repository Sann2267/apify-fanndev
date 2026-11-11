# Crawling Method — LawRato Lawyer Directory Scraper

**Last verified:** 2026-09-08

## Target & jurisdiction choice

`lawrato.com` — India's largest consumer-facing lawyer directory.

Babak 42 of `ACTOR_MARKET_RESEARCHER_NEW.md` established the opportunity:
lawyer-directory data is proven in the US (96 actors / 49 sellers / 3,205
users; `fatihtahta/avvo-scraper` 1,250u, `jungle_synthesizer/justia-scraper`
1,023u) and **empty** in 11 other jurisdictions. The recommended build order
was Indonesia → India → Singapore/Malaysia.

**Indonesia was checked first and rejected — no data surface exists:**

| Target | Result |
|---|---|
| `hukumonline.com/pusatdata` | 200 / 532 KB, but it is a **regulations** database, not a lawyer directory |
| `hukumonline.com/klinik` | 200 / 760 KB — legal Q&A column |
| `hukumonline.com/legal-directory` | **404** |
| `peradi.or.id` | 200 / 347 KB (back up; it timed out during Babak 42) — but the bar association publishes newly-sworn advocates only as **news articles**, with no member directory or search |
| `kai.or.id` | 200 / 80 KB — association site, no member directory |

That is a legitimate negative finding and it also explains the "0 competitors"
signal for Indonesia: there is nothing to scrape, not an untapped market.
India was next on the list and does have a real directory, so this actor
targets LawRato.

## Anti-bot

Cloudflare fronts the site — its Rocket Loader rewrites inline handlers to
`window.__cfRLUnblockHandlers` — but **no challenge was served**. Listing
pages (`/lawyers`, `/lawyers/delhi`, `/divorce-lawyers`) and profile pages
returned complete markup at 400–430 KB to a plain `curl_cffi` `chrome124`
request: no cookie jar, no warmup, no login. TLS impersonation is kept
because Cloudflare is present and could tighten at any time, and
`is_blocked` stays wired so a future challenge surfaces as a retry/error
rather than as silently empty records.

## Route map

| Purpose | Route |
|---|---|
| All India | `/lawyers` (+ `?page=N`) |
| One city | `/lawyers/<city>` (+ `?page=N`) |
| One practice area | `/<area>-lawyers` (+ `?page=N`) |
| Profile | `/advocate-<slug>` |

16 cities and 30 practice areas are linked from `/lawyers`; `reference` mode
re-reads both lists live rather than trusting the copy in `constants.py`.

**There is no combined city + practice-area route** (`/lawyers/delhi/divorce`
does not exist), so the actor picks city over practice area and logs a
warning when both are supplied. `/delhi-lawyers` — the shape one would guess
by symmetry with `/divorce-lawyers` — is a **404**; cities live under
`/lawyers/<city>` only.

## Pagination

20 cards per page, identical across `/lawyers`, `?page=2`, `?page=50`,
`/lawyers/delhi` and `/divorce-lawyers`.

**Upstream never 404s past the end.** `?page=999` still returns HTTP 200 with
a near-empty 263 KB shell and zero usable cards, so the loop stops on:

1. zero cards parsed,
2. fewer cards than a full page, or
3. a page whose cards were all seen already (upstream clamping).

Status codes are not used as an end signal at all.

## Parsing

Listing cards carry schema.org `LocalBusiness` microdata, so the parse is
anchored on `itemprop=name` / `address` / `addressLocality`. Rating, rating
count and years of experience are **not** marked up and are read out of the
card's own text with narrow regexes; the whole card text is also emitted as
`cardText` so nothing visible is lost if one of those regexes stops matching.

### Gotcha: two sections, two different markups

The profile page renders Courts and Specialization with different HTML, both
inside `.panel1` containers:

```html
<h2>Courts</h2>          <ul class="list-inline list-court panel1"><li>…</li></ul>
<h2>Specialization</h2>  <div class="panel1">a<br/>b<br/>c</div>
```

A `find_next("ul")` anchored on the Specialization heading therefore runs
past its own (ul-less) section and returns the **Courts** list — which
silently duplicated Courts into `specializations` in the first build. The
fix matches the first following `ul` **or** `.panel1` div, whichever comes
first. Verified: `specializations` now yields "File for Divorce", "Reply /
Send Legal Notice for Divorce", … while `courts` yields "Delhi High Court",
"District Court, Faridabad", …

Bar council and enrolment year are parsed out of the biography prose
("Advocate Sunil enrolled with the Bar Council of Punjab and Haryana in
1987"), since upstream has no dedicated field for them.

## Known upstream quirks

- Rating counts are published as buckets ("100+ user ratings"), never exact.
  `ratingCount` therefore carries `ratingCountIsMinimum`.
- No phone number appears on public pages — contact is routed through the
  directory's own call/chat widgets. No phone field is emitted.
- The site mirrors itself on language subdomains (`hindi.`, `tamil.`,
  `bangla.`, `marathi.`, `kannada.`, `telugu.`, `malayalam.`). Only the
  English site is used; the mirrors are a possible future mode.

## Sibling jurisdictions (same vein, not built here)

Still zero-competitor and confirmed reachable in Babak 42/43 recon:
`lawsociety.org.sg/find-a-lawyer` (SG, 340 KB — but only *featured* members
are listed, verify depth first) and `malaysianbar.org.my` (MY, 86 KB).
