# Crawling method - Flashscore

Recon date: **2026-09-08**. Everything below was measured, not assumed; the
numbers are what the probes actually returned.

## 1. The website itself is a dead end

`https://www.flashscore.com/` answers 200 with **739.047 bytes** of HTML - and
none of it is match data. Greps for the usual server-rendered markers came back
empty: no `__NEXT_DATA__`, no `INITIAL_STATE`, no JSON-LD block, no team names
in the markup. This is the exact trap recorded as Gotcha #1 in Babak 44 of the
market-research log: **page size is not evidence that data is present.** A probe
that stops at "200 + big HTML" would have scored this target as rich and been
wrong.

## 2. The real surface: a separate feed host

Data comes from

```
https://local-global.flashscore.ninja/2/x/feed/<feed-id>
```

with one hard requirement: the header **`x-fsign: SW9D1eZo`**.

| Request | Result |
| --- | --- |
| `GET /2/x/feed/f_1_0_3_en_1` **with** `x-fsign` | 200, 451.944 bytes, 275 match records |
| same URL **without** `x-fsign` | **401**, 323 bytes |

The value is a constant embedded in Flashscore's own bundle, not a per-session
token: the same string works across sports, days and match IDs, and across
separate sessions with no cookies at all. There is no WAF, no cookie warm-up, no
challenge and no TLS-fingerprint gate - `curl_cffi` with `chrome131` is used per
portfolio convention, not because anything forced it.

Because a missing/rotated `x-fsign` produces a deterministic 401, the client
treats 401 as a **non-retryable configuration failure** (raising
`FeedUnauthorized`) instead of burning four retries on it.

## 3. Response format

Not JSON. Flashscore's own delimited encoding:

```
record ~ record ~ record
key ÷ value ¬ key ÷ value ¬ ...
```

- `~` separates records
- `¬` separates fields inside a record
- `÷` separates a key from its value

Tournament headers arrive as their **own record, before** the matches they
contain, and are not repeated on the match rows:

```
ZA÷ARGENTINA: Liga Profesional - Clausura¬ZEE÷naYhNOaA¬ZB÷22¬ZY÷Argentina¬ZC÷lEqmiyVI¬
AA÷WSSid6OM¬AD÷1788818400¬AE÷Barracas Central¬AF÷Argentinos Jrs¬AG÷0¬AH÷0¬
```

So the parser carries the last `ZA` record forward as context. Losing that step
produces rows with teams but no competition - which is how most of the value
disappears.

## 4. Field mapping - how it was derived

Counted across the 275 football rows of one day feed.

**Present on >90% of rows** (i.e. structural):
`AA AB AC AD ADE AE AF AX BW BX CR CX FH FK GRA GRB JA JB OA OB PX PY RW WL WM WN WU WV`

**Present on <25% of rows** (i.e. state-dependent):
`AG AH AI AJ AK AM AO AS AT AU AZ BC BD BY BZ DZ HMC QQ RPA RPB`

Positively identified and given friendly names:

| Key | Meaning | Evidence |
| --- | --- | --- |
| `AA` | match ID | feeds back into every detail endpoint |
| `AD` / `ADE` | kick-off epoch | converts to the published kick-off time |
| `AB` | coarse status | 1 = scheduled, 2 = live, 3 = finished; matched against rows with/without scores |
| `AC` | fine status code | values seen: 1, 3, 4, 11, 12, 13, 38, 45 - **not** fully enumerated, ships raw |
| `AE` / `AF` | home / away name | cross-checked against the public match page |
| `AG` / `AH` | home / away score | absent entirely before kick-off, present once started |
| `AS` | winner | 0 draw, 1 home, 2 away; only on decided matches |
| `JA` / `JB` | team IDs | stable across days |
| `WU` / `WV` | team slugs | match the public team URLs |
| `OA` / `OB` | team logo files | |
| `AO` | finished-at epoch | present on finished rows |
| `ZA ZY ZEE ZC ZB` | tournament, country, tournament ID, stage ID, country ID | from the header record |

Everything else is passed through untouched under `_raw`. The upstream key set
is undocumented and grows; naming only what was verified and shipping the rest
verbatim is the only way to be both useful and honest here.

## 5. Endpoint map

| Purpose | Feed ID | Verified result |
| --- | --- | --- |
| Day fixtures/results | `f_<sport>_<dayOffset>_3_en_1` | football today 429 KB / 275 matches; tennis 901 KB / 470 |
| Live only | `f_<sport>_0_1_en_1` | carries the whole day; in-play rows filtered on `AB=2` |
| Match meta | `dc_<sport>_<matchId>_1` | 234 B |
| Incidents | `df_sui_<sport>_<matchId>_1` | 2.800 B, 15 incidents on the sample match |
| Statistics | `df_st_<sport>_<matchId>_1` | 5.030 B, 120 rows incl. **Expected goals (xG)** and possession |
| Lineups | `df_li_<sport>_<matchId>_1` | 15.116 B, formation + ratings |
| Head-to-head | `df_hh_<sport>_<matchId>_1` | 51.123 B |

### The sport segment in detail feeds is ignored - verified

The number after the prefix looks like a sport ID and Flashscore's own client
sends the real one. It makes **no difference**: the same football match fetched
with sport `1`, `2`, `3` and `99` returned **byte-identical** bodies
(234 / 2.800 / 5.030 / 15.116 B per feed), and a tennis match fetched with
sport `1` returned its tennis statistics (aces, double faults) unchanged. The
match ID alone selects the data.

Consequence for the Actor: `sportIds` in `match` mode only **labels** the output
record, and an empty detail body means *unknown match ID*, never *wrong sport*.
The first version of this Actor's error message claimed the opposite; it was
corrected after the probe above, not before.

### Endpoints that were tried and did NOT work

Recorded so the next attempt does not repeat them:

| Tried | Result |
| --- | --- |
| `dl_<sport>_<id>_1`, `df_dl_<sport>_<id>_1` (lineups) | 404 / empty - correct prefix is `df_li_` |
| `df_od_<sport>_<id>_1` (odds) | empty body |
| `df_cm_<sport>_<id>_1` (commentary) | empty body |
| `ss_1_<stageId>_table_overall`, `to_<stageId>_table_overall`, `tos_<stageId>_table_overall_1`, `ss_1_<stageId>_1` (standings) | empty or 404 |
| `tt_<stageId>_1_en_1`, `tr_<stageId>_1_1_en_1` (tournament fixtures/results) | empty |
| `tsc_<tournamentId>_<stageId>_1` (top scorers) | 404 |

Standings and odds are therefore **not** shipped. They exist on the website, so
the feed IDs presumably exist too - they were simply not found by name-guessing,
and guessing further was not worth the run cost. Documented as a known gap in
the README rather than half-implemented.

## 6. Sport IDs - enumerated, not guessed

Probed `f_<id>_0_3_en_1` for ids 1-21 and read back the tournaments returned:

| ID | Matches that day | Sample tournament | Named as |
| --- | --- | --- | --- |
| 1 | 275 | ARGENTINA: Liga Profesional | Football |
| 2 | 470 | ATP - SINGLES: US Open | Tennis |
| 3 | 23 | CHILE: LNB - Clausura | Basketball |
| 4 | 39 | DENMARK: Metal Ligaen | Ice Hockey |
| 5 | 2 | CANADA: CFL, USA: NCAA | American Football |
| 6 | 21 | JAPAN: NPB | Baseball |
| 7 | 13 | CROATIA: 1. HRL Women | Handball |
| 10 | 5 | SWEDEN: Svenska Cupen (Broberg/Soderhamn, Sandviken) | Bandy |
| 11 | 1 | WORLD: Friendly Intl, BELGIUM: Division 1 (Eisden-Dorp) | Futsal |
| 12 | 7 | ASIA: Asian Championship | Volleyball |
| 13 | 11 | ASIA: T20 Asia Cup Women, INDIA: Duleep Trophy | Cricket |
| 14 | 45 | WORLD: MODUS Super Series | Darts |
| 15 | 19 | ENGLAND: English Open | Snooker |
| 21 | 22 | BWF WORLD TOUR: Vietnam Open | Badminton |

IDs 8, 9 and 16-20 answered 200 with an empty body on the probe day and are
**not** claimed. `reference` mode re-probes every ID at run time and reports the
live count plus a sample tournament, so the user sees today's truth rather than
this table.

## 7. Gotchas worth carrying forward

1. **A global item cap silently hides sports.** With one shared `maxItems`, a
   request for football + tennis + basketball returned football only - football
   alone has ~275 rows for a single day. The cap is now divided across the
   requested sport/day combinations. Caught by asserting on the *set of sports
   present* in the local test, not on the row count.
2. **"Live" feeds are not only live.** `f_<sport>_0_1_en_1` returns the whole
   day; only `AB=2` rows are in play. Trusting the feed name would have shipped
   finished matches as live.
3. **Absent is not zero.** Pre-kick-off rows have no `AG`/`AH` keys at all.
   Defaulting them to 0 would have invented 0-0 scorelines for every scheduled
   match in the dataset.
4. **An empty body is a legitimate answer.** Sports with no fixtures that day,
   and matches with no published lineup, both return a 1-byte body with status
   200. The client normalises that to `""` and callers decide what it means -
   it is not an error path.
