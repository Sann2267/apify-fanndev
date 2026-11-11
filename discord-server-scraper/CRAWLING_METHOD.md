# Recon record — discord.com, 2026-09-21

Internal notes. What was probed, what answered, and what it cost to find out.
`src/constants.py` carries the short version; this is the evidence.

## 1. Framing

The obvious Discord actor ideas — message archiver, keyword/brand monitor,
support-ticket analyser — all need a **bot token invited to the target server**.
That is a per-buyer credential, not something a scraper supplies, and the
user-token alternative is self-botting, which is a bannable ToS violation. Both
were ruled out before probing started. The question became: *what does Discord
serve to an anonymous client?*

The answer was larger than expected, and it maps onto the "Server Growth
Tracker" idea from the original brief almost exactly.

## 2. Surface map

| Endpoint | Auth | Result |
|---|---|---|
| `GET /api/v10/invites/{code}?with_counts=true&with_expiration=true` | none | **200** — full guild meta + live counts |
| `GET /api/v10/guilds/{id}/widget.json` | none | **200** when the owner enabled it, else 403 `50004` |
| `GET /api/v10/applications/{id}/rpc` | none | **200** — bot/app public metadata |
| `GET /servers`, `/servers/{category}` | none | **200** — SSR, Algolia-backed, ~53k servers |
| `GET /servers/{slug}-{id}` | none | **200** — SSR, full profile + social links |
| `GET /trending-games[/{date}][/category/{slug}]` | none | **200** — SSR weekly chart |
| `GET /game/{slug}-{id}` | none | **200** — SSR game profile |
| `GET /api/v10/guilds/{id}/preview` | — | **401** even for DISCOVERABLE guilds |
| `GET /api/v10/discoverable-guilds` | — | **401** (this is the JSON behind `/servers`) |
| `GET /api/v10/discovery/categories` | — | **401** |
| `GET /api/v10/guilds/{id}/scheduled-events` | — | **401** |
| `GET /application-directory[/{id}]` | — | **200 but empty** — client-rendered, fetches need a token |
| `GET /api/v10/guilds/templates/{code}` | none | 200 only for real template codes; a guild id is not one |

The App Directory is the trap in that list: it answers 200 with a full-looking
HTML document and ships no data at all. `/api/v10/applications/{id}/rpc` is the
supported way to the same information.

## 3. The gate is a rate limit, not a fingerprint

This nearly went into the constants file as a TLS gate. Running a 12-profile
`curl_cffi` matrix in order against `/servers?query=crypto` produced:

```
chrome110:200 chrome116:200 chrome120:200 chrome124:200 chrome131:200 chrome133a:200
safari15_5:429 safari17_0:429 safari18_0:429 firefox133:429 edge99:429 edge101:429
```

Six Chrome profiles served, six non-Chrome blocked. A clean-looking Chrome-only
gate — and wrong. Two control experiments:

1. **Safari first, after a 30s cooldown, 6s apart:**
   `safari18_0:200  firefox133:200  edge101:200  chrome131:200`.
2. **Chrome alone, no delay:** 200 ×6, then **429 on request seven**.

The limit is per-IP volume, roughly six back-to-back requests, and the
fingerprint is irrelevant. Sixteen requests at 2.5s apart drew zero 429s.
`DEFAULT_REQUEST_DELAY_SECS = 2.0` comes from that.

Everything else is unthrottled: the invites API took a 25-request burst with 25
× 200 and publishes no `x-ratelimit-*` headers at all. Hence two pacing tiers in
`client.py` — throttling the API on the directory's clock would have made every
mode needlessly slow.

**Lesson for the portfolio:** when a profile matrix splits cleanly down the
middle in the order it was run, re-run it in reverse before writing "TLS gate".

## 4. Decoys

| Looks like | Actually |
|---|---|
| `/servers?q=crypto` | **200, unfiltered home listing**, `nbHits` for the whole index. `q` is parsed and discarded. The real param is `query=`. |
| `?length=48` | Ignored. Echoed params always read `length=12`. |
| `/servers/category/gaming` | 404. Categories live at `/servers/gaming`. |
| `/servers/finance`, `/servers/memes`, … | 404. Only 5 of ~50 category ids have a page: gaming (1), music (2), entertainment (3), science & tech (5), education (6). |
| `/trending-games?week=2026-09-10` | Ignored — returns the current week. The date is a path segment. |
| `/trending-games/1999-01-01` | **200 with the CURRENT chart**, not a 404. A history walk stepping dates by 7 would silently duplicate. |

The `q=` decoy is the dangerous one: a run using it looks completely successful
and returns the same generic servers for every keyword.

## 5. SSR payload format

TanStack Router + seroval. Data lives in the largest nonce'd inline script:

```js
$_TSR.router=($R=>$R[0]={manifest:void 0,matches:$R[1]=[$R[2]={i:"__root__ ",ssr:!0}]})($R["tsr"]);
```

Not JSON: bare identifier keys, `!0`/`!1` booleans, `void 0`, and an `$R[n]=`
marker on every value. `src/serialized.py` is a proper tokenizer because server
descriptions are attacker-adjacent free text — recon found names containing
`{id:` verbatim, which derails any bracket-counting approach.

Two things the first draft got wrong, both caught by running it against live
pages rather than reasoning about the format:

* **Numeric object keys.** `aggregateFacets["categories.id"]` is
  `{0:32,1:24579,2:2394,…}` — servers per category. An identifier-only key
  parser dies on exactly the payload that carries the directory's facet totals.
* Back-references. Zero pages currently emit a bare `$R[n]` read, so the
  markers could have been stripped with a regex. They are resolved properly
  anyway: seroval emits back-references the moment a payload repeats a subtree,
  and a listing that showed the same server twice would start doing it with no
  version bump to warn anyone.

## 6. Field notes

* **Slug is cosmetic.** `/servers/{anything}-{id}` and `/servers/{id}` both
  resolve; only the trailing snowflake is keyed on. A right slug with a wrong id
  is a 404. (Opposite of Etsy, where a wrong slug is fatal.)
* **Guild ids encode their creation time** in the top 42 bits over the Discord
  epoch (1420070400000). That is how `createdAt` appears on invite and widget
  records, which do not publish it.
* **Two count sources disagree slightly and both are right.** Python's invite
  reported 431,648 members / 34,152 online while its Discovery page reported
  431,638 / 30,984 seconds apart. Different computation schedules, so
  `serverSnapshot` keeps them in separate fields rather than picking a winner.
* **Widget members are anonymised by Discord**, not by us: `id` is the index in
  the response. Publishing it as `id` would invite cross-run joins that pair up
  unrelated people.
* **`nbHits` drifts** — 52,973 then 52,579 seconds apart. Never a loop bound;
  the walk stops on an empty page.
* **Category page counts ≠ facet counts** (gaming: page says 38,543, facet says
  24,579). The page filter is `primary_category_id=N OR categories.id=N`; the
  facet counts one of the two. Both correct, different questions.
* **`name_localizations`** ships all 30 locales of every category name on every
  category of every hit — ~90% of the payload. Dropped in parsing.
* **Deep offsets work.** `offset=888` of `nbHits=896` returned the final 8 rows;
  no Algolia 1,000-result ceiling was hit. The full index is walkable at 12 per
  request (~4,400 requests for all 53k).

## 7. Verification

`python test_local.py` — 116 assertions, all passing.

* Offline: 10 tokenizer cases (escaped quotes and braces inside strings,
  surrogate-pair emoji, numeric keys, array holes, back-references) plus every
  parser against fixtures captured 2026-09-21 in `tests/fixtures/`.
* Live: all 9 modes against discord.com, asserting on behaviour rather than
  just on status — that a keyword actually filters (≥3 of 12 names contain it),
  that paging does not duplicate servers, that a dead invite yields a
  `not_found` row rather than a crash, that a widget-disabled server is
  reported as `widget_disabled`, that a 2-week history walk collects two
  *distinct* weeks, and that `serverSnapshot` really combines ≥2 surfaces.
* 17 HTTP requests for the whole live sweep, 0 rate limited at the 2s default.

## 8. Not worth a mode

* **Guild templates** — `/api/v10/guilds/templates/{code}` is open, but codes
  are rare, unlisted and undiscoverable. Nothing to enumerate.
* **`/api/v10/sticker-packs`** — open, 136 KB of Discord's own Nitro sticker
  catalogue. Static marketing data, no buyer.
* **`/api/v10/gateway`** — open, returns one WebSocket URL. Useless without a
  token.
