# Crawling method — Google Hotels rate comparison

Recon date: **2026-09-18**. Plain HTTP, no browser, no cookie, no login.

## Surfaces

| Surface | Method | Carries |
| --- | --- | --- |
| `/travel/search?q=<query>&hl=&gl=` | GET, SSR HTML, ~2.7 MB | 20–21 hotel cards: name, entity id, price, rating, review count, star class, deal flag, amenities, "People often mention" themes |
| `/travel/hotels/entity/<entityId>/prices?hl=&gl=` | GET, SSR HTML, ~2.6 MB | Hotel header (address, phone, star class, rating) + **17–25 OTA quotes** + 9–18 paid placements |

`/travel/hotels/entity/<id>` and `/travel/hotels/entity/<id>/prices` returned byte-identical
content during recon; the Actor uses the explicit `/prices` path.

## TLS profile matrix

Probed from a residential Indonesian IP against `/travel/search`:

| Profile | Result |
| --- | --- |
| `chrome124` | **200, 2.75 MB** — the default, and the profile that won every probe |
| `firefox133` | 200 |
| `safari15_5` | 200 |
| `safari17_0` / `chrome99_android` / `edge101` / `chrome131` | untested on this path; kept in the ladder |

The client keeps a ladder and **remembers the profile that last won**, so a single blocked
profile is a data point rather than a verdict (`.ai/CLAUDE.md` rule 2). No WAF vendor banner,
no CAPTCHA and no consent wall was seen from a residential IP.

## Structural anchors (why this survives a Google redeploy)

Google's class names are minified and rotate on every deploy, so **nothing here selects on a
class**. The anchors are semantic:

- `a[href^="/travel/hotels/entity/"]` with an `aria-label` → a hotel card. Secondary links
  inside the same card (`View prices for …`, `Photos for …`) point at the same entity and are
  skipped, which is what turns 114 anchors into 20 hotels.
- `a[href*="/travel/lodging/clk"]` → one OTA quote. `data-is-organic="true"` marks a genuine
  quote; the partner id sits on an ancestor `div[data-partner-id]`; the OTA's own deep link is
  in the `pcurl` query parameter, and its hostname is a more reliable provider identity than
  the displayed brand text, which is localised per exit country.
- `a[href*="/aclk?"]` → a paid placement **for a different hotel**.
- `aria-label="<n> out of 5 stars from <m> reviews"` → rating and review volume.
- The card container is found by **climbing until the subtree text has several segments**,
  not by matching a wrapper class.

## Gotchas found during recon

1. **Currency cannot be requested.** `curr=USD`, `currency=USD` and `gl=gb` are all accepted
   and silently ignored — every response came back in IDR from an Indonesian IP. **The proxy
   exit country is the currency control.** Each record therefore reports the currency Google
   actually returned instead of one the caller asked for.
2. **Dates cannot be requested either.** Google carries the stay window in the protobuf `ts=`
   parameter. `checkin`/`checkout` are ignored, and five hand-encoded `ts` layouts were all
   ignored too, so the quote is always Google's default window (tonight, 1 night). Every
   record carries `stayWindow` so a caller can never mistake it for a window they chose.
   Getting arbitrary dates would need a real `ts` captured from a browser — out of scope for
   an HTTP-only Actor.
3. **There is no pagination on search.** `start=20` returns the same 21 hotels. Breadth comes
   from issuing several narrower queries, not from deeper pages.
4. **An unknown entity id returns HTTP 200, not 404** — a full-size Google error page whose
   `<h1>` is "Oops, something went wrong. Please try again." A naive parser emits that as a
   hotel named "Oops, something went wrong". `parse_entity` raises `HollowEntityPage` on it,
   and the `rates`/`sponsored` modes call `parse_entity` first purely as that guard, because
   they parse fragments and would otherwise return an empty list and look like a hotel with
   no quotes.
5. **The entity page is full of other hotels' facts.** It carries 18 paid placements, a
   nearby-attractions block and (for Marina Bay Sands) a shopping-mall description — each with
   its own rating aria-label and its own postal address. A page-wide search for "the rating"
   returned **4.4 from 18,459 reviews for a hotel rated 4.7 from 64,684**, and picked a
   jewellery boutique's marketing copy as the street address. The fix is to read the header
   only from the container holding the `<h1>`. This is the same class of bug as the BCPEA
   filter-caption trap: **scope the match, don't trust document order.**
6. **The rating aria-label differs between surfaces.** On cards it ends at "reviews"; on the
   entity page Google appends a verdict ("… reviews. Excellent."). An anchored `^…$` regex
   matches the card and silently misses the hotel page, falling through to a neighbour's
   rating — so the pattern is a search, not a full match.
7. **Google serves challenges with HTTP 200.** Status code alone cannot tell content from a
   challenge, so the client enforces a 250 KB floor: a real page is 2.5 MB+, and an
   unexpectedly small 200 is treated as a block rather than parsed into empty records.
8. **A hotel's own website appears as an OTA row** (Marina Bay Sands via `derbysoftca.com`).
   That is correct, not a bug — `providerHost` is what distinguishes a direct rate from an
   intermediary's.

9. **The amenity list has two shapes and lives outside the card.** On some result pages it is
   an `aria-label`; on others it is the text of a `span[role="document"]`. In both cases the
   node sits *outside* the card's ancestor chain — climbing 12 levels up from the title link
   never reaches it — so amenities are indexed once per page by the hotel name they name
   (`Amenities for <name>, a 4-star hotel.: …`). Reading them from inside the card returned
   empty lists for 20 of 20 hotels on the Kyoto page while the data was plainly present.

## Cost shape

- `search`: **1 request per query** → ~21 hotels.
- `hotel` / `rates` / `sponsored`: **1 request per hotel**, and that one request serves all
  three modes' data.
- `search` with `fetchRates` on: 1 + 21 requests per query — off by default for that reason.
