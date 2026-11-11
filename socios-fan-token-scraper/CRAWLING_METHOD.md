# Crawling method — socios.com / api.chiliz.com

Internal notes. The buyer-facing document is `README.md`; this one records what
was probed, what answered and what to re-check when something breaks.

Verified 2026-09-20.

## Surface map

`www.socios.com` is a **WordPress marketing site** — Yoast, WP-Rocket, WPML,
Gravity Forms. It is not the product and carries no structured data worth
taking:

| Probe | Result |
| --- | --- |
| `/wp-json/` and every `wp/v2` route | `401 socios_rc_rest_authentication_required` — locked by a custom plugin |
| `/sitemap_index.xml` | open (post / page / category sitemaps) — marketing copy only |
| `robots.txt` | `Disallow:` empty, i.e. everything allowed |

The product is `app.socios.com`, a Next.js App Router SPA whose routes all sit
inside an `(authenticated)` group. Its JS bundles live on
`capsicum-files.socios.com` and were the way in: grepping all 61 chunks for
host and path literals produced **182 hosts and 348 API paths**, and named the
gateway `api.chiliz.com`.

## The gateway

`api.chiliz.com` is Kong. It applies an **ACL per route**, not a blanket auth
check, and a useful slice answers an anonymous caller with no token at all.

### Open anonymously

| Route | Rows | Used as |
| --- | --- | --- |
| `/api/acl-service/v1/front/surveys` | 9,825 | `polls` — the flagship. Carries full results. |
| `/api/acl-service/v1/front/partners` | 231 | `partners`, and the join key for everything else |
| `/api/acl-service/v2/front/currencies` | 346 | `fanTokens` |
| `/api/acl-service/v1/front/vote-token/vote-tokens` | 106 | `voteTokens` |
| `/api/acl-service/v1/front/leagues` | 49 | `reference` |
| `/api/acl-service/v1/front/sports` | 6 | `reference` |
| `/api/acl-service/v1/front/countries` | 249 | `reference` |
| `/api/acl-service/v1/front/currencies`, `/currencies/info` | 517 | not used — v2 currencies is richer |
| `/api/acl-service/v1/front/maintenance/status` | — | health check |

### Closed — `403 {"message":"You cannot consume this service"}`

`marketplace/*` (prices, charts, markets), `fan-shop-service/*`,
`collectible-service/*`, `auction-service/*`, `gamification-service/*`
(leaderboards), `pledge-service/*`, `token-quest/*`, `fan-token-offerings`,
`vote-token-offerings`, `social-service/*`, `token-supporting-platforms`,
`v2/front/configuration/*`, `v2/front/leagues`, everything under `/me`.

**This 403 is an ACL verdict, not a WAF block.** It is instant, byte-identical
from every IP and every TLS profile, and — decisively —
`POST /front/session/auth-token`, the endpoint that would widen the anonymous
role, is itself behind the same 403. There is no HTTP-only path to these
routes. Do not spend time on fingerprints here; spend it only if Socios opens
a public read role.

### Not reachable

`/public/teams`, `/public/matches`, `/public/teams/{addr}/match-history` and
`/public/tokens/{slug}/match-history` — the "Fan Token Play" service (match
history, odds, outcomes). Its base URL comes from
`NEXT_PUBLIC_FAN_TOKEN_HUB_API_URL`, which is injected at runtime and appears
in **no** static chunk (`grep 'https://api\.chiliz\.com'` across every chunk:
zero hits — even the known host is runtime-only). Twelve plausible hostnames
all fail DNS; `api.chiliz.com/public/teams` returns Kong's
`no Route matched with those values`. Reopen this only with a fresh capture
from a logged-in session, which is out of scope here.

## No anti-bot layer

Cloudflare fronts both hosts but runs no challenge. The full ladder —
`chrome124`, `chrome131`, `chrome136`, `safari17_0`, `firefox133`, `edge101`,
`chrome99_android` — returned a byte-identical 200 on the same IP for
`www.socios.com` and for the gateway. `chrome131` is used to blend with
`app.socios.com`'s own traffic, not to get through anything. Rotating profiles
on block would be theatre: the only 403 here is the ACL verdict.

Proxy is therefore **off by default**. Residential changes nothing.

## Query-parameter traps

The single most expensive thing to get wrong. **This API accepts unknown query
parameters and silently ignores them**, returning a cheerful 200 whose
`total_items` is the unfiltered count — they look like they worked.

| Parameter | Behaviour |
| --- | --- |
| `partnerIds[]` | **works** — the only club filter. AC Milan → 272 rows |
| `partnerId[]`, `partner[]`, `partners[]` | **decoys** — 200, `total_items` still 9,825 |
| `status[]` | **works** — see casing below |
| `type[]`, `currencyId[]`, `voteTokenId[]`, `isBound[]` | **decoys** — ignored |
| `orderBy` | works: `createdAt`, `openAt`, `closeAt`, `publicationDate`, `status`. Anything else 400s |
| `sortOrder`, `direction`, `order`, `sort` | accepted and ignored — there is no ascending option |
| `limit` | works, hard-capped at 1000 with an explicit 400 above it |
| `page` | works on `surveys`, `partners`, `vote-tokens`; **ignored** on leagues/sports/countries |

`src/main.py` asserts that `partnerIds[]` actually filtered (`stray` check) so a
rename surfaces as a loud failure rather than a dataset full of the wrong club.

### Status casing

Sending `status[]=zzz` makes the gateway list its choices in a 400 — but that
list is of **PHP enum constant names** (`SCHEDULED`, `CLOSED_PENDING`, …) and
every one of them is rejected verbatim. The values that work are lower-case
with **hyphens** where the constant has underscores:

```
closed (8,119)  cancelled (1,686)  error (13)  suspended (5)
opened (1)      cancelling (1)     scheduled / created / processing (0)
closed-pending / closed-release-wallet-limit / closed-blockchain-pending (0)
```

`CLOSED` → 400. `closed` → 200. `closed_pending` → 400. `closed-pending` → 200.

## Pagination

`?limit=N&page=M`, with `metadata.last_page` and `total_items`. Page
`last_page + 1` answers 200 with `data: []`.

**Page size is capped at 250, not 1000, by choice.** A 1,000-row page of polls
serialises to 5–8 MB and the gateway then answers **500 on the heavier ones** —
`page=7&limit=1000` fails identically on every attempt. All 40 pages succeed at
`limit=250` (~3 MB each). `client.py` keeps `MAX_PAGE_SIZE = 1000` for the
metadata-less reference routes, which need a high limit and are small.

Page 1 is fetched alone to learn `last_page`; pages 2..N then run four at a
time.

### Degradation

- `PageTooHeavy` (500) and `RetriesExhausted` both fall back to `_split_page`,
  which re-fetches that page's exact row span as five smaller pages and
  recurses. One blipping page no longer costs the other 9,800 rows. A genuine
  `HTTP 288` was observed once under load and is handled this way.
- Reference routes carry **no metadata at all** and ignore `page`, so a full
  page is indistinguishable from a truncated one — `collect` raises
  `UnexpectedShape` if such a route returns exactly `page_size` rows.
- `leagues` returns only **7 of its 49 rows** when no `limit` is passed. Always
  pass one.

## Things that look like bugs and are not

- **`leadingAnswer: null` on prediction polls.** All 10 published prediction
  polls are `cancelled` with `totalVoteTokensUsed: 0` on every answer. There is
  no winner to report.
- **`partnerName: null` on some fan tokens.** 346 currencies vs 231 partners;
  `externalToken`, `fiat` and `crypto` rows have no club, and a few clubs'
  `currencyId` points elsewhere (Crystal Palace).
- **`totalVoteTokensUsed` ≠ `usedTokenCount` on open polls.** The former is
  summed from the answers, the latter is what the chain has confirmed.

## Re-check list when it breaks

1. `GET /front/maintenance/status` → `{"data":"ok"}`.
2. Confirm `partnerIds[]` still filters (the `stray` assertion catches this).
3. Confirm `status[]=closed` still 200s — if the casing convention flips,
   `POLL_STATUSES` in `constants.py` is the single place to change.
4. If 500s spread, lower `DEFAULT_PAGE_SIZE`.
5. If a previously open route starts 403ing, Socios narrowed the anonymous ACL
   role — the mode degrades to one `forbidden_by_acl` error row by design.
