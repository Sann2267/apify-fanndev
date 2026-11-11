# Crawling Method — Google Maps Reviews & Sentiment Extractor

> **Correction (2026-09-16):** the claim below that free-text place search is closed is **wrong**. The sibling actor `google-maps-lead-generation-scraper` searches Google Maps successfully; the `pb` used here was malformed (it omitted the `!7i20!10b1!12m6…` result-request tail, so Google returned search metadata with no result list). This actor still takes place identifiers only, but the limitation is a design choice, not a platform restriction.


Reconnaissance performed 2026-09-16 from a plain residential ISP connection in
Indonesia, HTTP-only, no browser, no login, no API key.

---

## Summary

| Question | Answer |
| --- | --- |
| WAF? | **None** on the reviews path. 10/10 TLS profiles returned 200. |
| Residential proxy required? | **No — actively harmful.** Datacenter/no-proxy works; residential gets interstitials. |
| Live endpoint | `GET /httpservice/web/PrivateLocalSearchUiDataService/GetLocalBoqProxy` |
| Protocol | JSON `reqpld` array — **not** the `pb=` protobuf string every public guide documents |
| Pagination | opaque cursor, verified to 400 reviews / 18 pages with zero duplicates |
| Free-text place search | **Closed.** No HTTP-only surface survives. |

---

## The endpoint everyone documents is dead

Every public guide, and this repo's own `.ai/skills/google-internal-apis` note
(last verified 2026-05-12), points at `/maps/rpc/listugcposts` with a `pb=`
protobuf string. That endpoint now refuses every request:

```
GET /maps/rpc/listugcposts?...&pb=!1m6!1s<FID>!6m4!...
-> 403  )]}'\n\n[["er",null,null,null,null,403,null,null,null,7],["di",17]]
```

gRPC status 7 is PERMISSION_DENIED. It was proven to be unconditional, not a
matter of getting the request right:

| Varied | Values tried | Result |
| --- | --- | --- |
| TLS profile | chrome150/146/131/124, firefox147/135, safari2601/180, edge101, chrome99_android | all 403 |
| Country host | google.com/.fr/.co.uk/.co.id/.de | all 403 |
| Session token slot | `kEI`, `Yllh3e`, empty string | all 403, identically |
| Headers | origin, x-client-data, x-browser-validation, x-goog-api-key, referer variants, no referer | all 403 |
| pb flag blocks | `8m9`, `11m0`, `11m4`, `13m1` ablated in every combination | all 403 |

The decisive evidence that the *payload* was fine: removing the `!5m2...!7e81`
block flips the answer to **400 / gRPC 3 (INVALID_ARGUMENT)**, and `!7e81` is the
only enum value that reaches 403 at all. So the request parsed correctly and was
then refused. Token content was irrelevant — an empty string and a freshly
harvested `kEI` failed identically, which rules out "wrong token" too.

Also retired, both 404:

* `/maps/rpc/listentityreviews` — the `!1y`/`!2y` signed-int64 form
* `/async/reviewDialog` — the classic Search-side reviews surface

---

## What actually works

Reviews moved to a different service entirely, which takes a JSON payload rather
than a protobuf string:

```
GET https://www.google.com/httpservice/web/PrivateLocalSearchUiDataService/GetLocalBoqProxy
    ?msc=gwsrpc&hl=en&gl=US&reqpld=<json>
-> 200, 88 KB, )]}'-prefixed JSON
```

`reqpld` is `[null, [null ×9, INNER]]`, where `INNER` has exactly 24 slots:

| Slot | Meaning |
| --- | --- |
| 1 | sort — 1 relevant, 2 newest, 3 highest, 4 lowest (all four verified) |
| 9 | page size — first page only, **must be null when a cursor is sent** |
| 11 | `[feature_id, null, null, place_slug]` |
| 14 | `""` — a query here is silently ignored; this endpoint is reviews-only |
| 16 | `[1, 1, null, [[3],[4],[5],[6],[7]]]` — which reaction categories to return |
| 19 | **next-page cursor** |
| 23 | constant `0` |

`GetLocalBoqProxy` is the only method on that service; `GetPlaceDetails`,
`GetLocalResults`, `Search`, `GetReviews` and `GetPhotos` all 404.

### The cursor is slot 19, not 20

The only public documentation of this endpoint puts the page token at slot 20.
That is off by one and cost real debugging time:

* slot 20 → HTTP 400
* slot 19 → 200, and consecutive pages share **0 of 20** review IDs
* slots 0, 3–8, 12, 15, 17, 18, 21, 22 → **200 with the token silently ignored**,
  re-serving page 1 every time

That middle category is the trap: a token in the wrong slot looks like success.
Any change here must be validated by diffing review IDs across pages, never by
checking the status code. Verified good: 400 unique reviews over 18 pages, zero
duplicates.

### Page size caps at 60

`num=20 → 20`, `num=50 → 50`, `num=100 → 60`, `num=200 → 60`. Paginated pages
always return 20 regardless of what the first page requested.

---

## Review field map

Each review is a positional array of ~49 slots:

| Slot | Field |
| --- | --- |
| 1 | rating |
| 2 | `[relative_time, ?, epoch_millis]` |
| 3 | `[name, avatar, profile_url, review_count, photo_count, ...]` |
| **4** | **owner response** — `[null, relative_time, text, ...]` |
| 5 | review id |
| 10 / 12 | report URL / permalink |
| 14 | photos |
| 26 / 27 / 28 | language / text / displayed text |
| 30 | structured attributes ("When did you visit?" → "Weekday") |
| 36–41 | translation: source language, translated text, target language |
| 45 / 46 | rating / rating maximum |
| **47** | **reactions** — `[null, [[3,n],[4,n],[5,n],[6,n],[7,n]]]` |

**Likes** are reaction category 3. This was confirmed rather than assumed:
requesting `[[3]]` alone in slot 16 returns exactly `[[3, 3]]` for a review that
returns `[[3,3],[4,1],...]` under the full category list.

Finding slots 4 and 47 required the right test subject — landmarks and parks
(Eiffel Tower, a Sri Lankan park, Google Sydney) have neither owner replies nor
likes, and all return only 5-star reviews under sort=1. A Sydney restaurant with
an active owner surfaced both immediately (80% reply rate on its first 60).

---

## What is NOT available (and why)

### Free-text place search — closed

Every HTTP-only path was tested and none survives:

| Surface | Result |
| --- | --- |
| `/maps/search/<query>` | 210 KB SPA shell, zero results embedded |
| `/search?tbm=map&pb=...` | 200 JSON, but metadata only — result count and a location chip, `d[64]` null |
| `/search?q=...&gbv=1`, `&tbm=lcl` | JS wall: `/httpservice/retry/enablejs` |
| `maps.google.com/maps?output=json|js` | 404 |
| `/maps/preview/search`, `/maps/preview/opensearch` | 404 / 400 |
| Query in `reqpld` slot 14, 11, 2, 0, 3 | 200 with empty body |
| Public browser keys from the Maps page | staticmap-only; Places APIs return "not authorized" |
| Android/mobile UA | 810 KB JS bundle, no data |

The actor therefore accepts place **identifiers** only and returns a clear error
for anything else, rather than guessing at a place and silently returning the
wrong one.

### Place name and coordinates — mostly unavailable

Google's resolver returns the feature ID but `null` for the name, and a viewport
that is the **identical world-view default for every place** (`-95.677068,
37.0625` — the geographic centre of the USA), not the place's own point.

A caution for anyone re-running this recon: fetching
`/maps/place/Eiffel+Tower/data=...` appears to return the name, but that string
is only the name echoed back from the request URL. Google supplies nothing.

So the actor takes the name and coordinates from the URL the user pastes
(`/maps/place/<Name>/` and the `!3d`/`!4d` pair) and leaves them null otherwise.
That is also why geographic filtering can only filter supplied places, never
discover new ones.

### CID needs no lookup

Only the second half of a feature ID identifies the place. Google's own review
permalinks use `!1s0x0:0x<cid hex>`, and the reviews endpoint returns byte-identical
results for `0x0:<cid hex>` as for the full feature ID. CID input is therefore a
pure local computation with zero network calls.

---

## Anti-bot posture

* No WAF, no CAPTCHA, no challenge on any endpoint used.
* No cookie warm-up strictly required, though the actor visits `/maps/` once per
  session to seed Google's cookie jar, which matches real browser behaviour.
* `CONSENT=YES+1` is pre-set to avoid a consent-interstitial redirect.
* **Residential proxy breaks this actor.** Measured on the platform: the same
  build, same input, same minute — `DATACENTER`/no-proxy returned 42 records in
  7s, while `RESIDENTIAL` failed to resolve the place at all, because Google
  answers those exit IPs with a consent/CAPTCHA interstitial rather than the
  page. Since there is no WAF to defeat, a residential IP buys nothing here.
  Default is `DATACENTER`; the exit country is pinned to the `region` input so a
  GDPR-country IP cannot trigger the consent wall.
* `CONSENT=YES+1` and `SOCS` are both pre-set. CONSENT alone is no longer
  sufficient on current Google.
* The retry path rotates TLS profile and cookie jar on 403/429/503.
