# Crawling Method — Google Maps Business Verification & Status Monitoring

Reconnaissance performed 2026-09-16, HTTP-only, no browser, no login, no API key.

---

## Summary

| Signal | Available? | Where |
| --- | --- | --- |
| **Unclaimed listing** | ✅ reliable | `tbm=map` search entry — no detail call needed |
| **No website / no phone / no hours** | ✅ reliable | same search entry |
| **Thin profile** (few reviews, low rating) | ✅ reliable | same search entry |
| **Permanently / temporarily closed** | ⚠️ limited | detail record only, and Google hides closed businesses from search |

Because every usable signal rides in the search response, an area sweep costs
**one request per twenty businesses** — the cheapest of the Maps actors in this
portfolio.

---

## Claim status is a link, not a flag

Google attaches an action to a listing **only when nobody has claimed it**:

```json
["Own this business?",
 "https://business.google.com/create?hl=en&getstarted&authuser=0&fp=3292831917685799941
  &gmbsrc=id-en-et-ip-mp-s-l~mkp%7Cclaimbz_aoc_a%7Crt_..."]
```

Detection matches `business.google.com/create`, the `claimbz` campaign tag, or
the `Own this business` label. A claimed listing carries none of them — verified
against a full record that had the other action links (`Report a legal issue`,
`Report business conduct`) but no claim link.

**It discriminates the way reality does**, which is the real test that it is
measuring claim status and not some constant artifact:

| Category (Jakarta, 20 results each) | Unclaimed | No website |
| --- | --- | --- |
| `warung` (small local eateries) | **15/20** | 17/20 |
| `wartel` (phone kiosks, a dying trade) | **11/11** | 11/11 |
| `internet cafe` | 7/20 | 12/20 |
| `salon` | 1/20 | 12/20 |
| `dentist` | **1/20** | 10/20 |
| `restaurant` (established) | 1/20 | 5/20 |

Professional practices are almost all claimed; informal micro-businesses almost
all are not. That spread is the product.

The signal also survives Google's **reduced** record — the ~30 KB response a
datacenter IP receives still carries the claim link — so unlike the sibling
popular-times actor, this one needs no residential proxy.

---

## Closure detection is genuinely limited

Google appears to **exclude permanently closed businesses from `tbm=map` search
results**. Across nine queries in two countries, including chains known to be
defunct, not one closed listing was returned:

| Query | Market | Results | Closed found |
| --- | --- | --- | --- |
| 7-Eleven, Sevel (all closed in Indonesia since 2017) | ID | 20, 16 | 0 |
| Giant supermarket, Matahari, Best Denki | ID | 12, 20, 11 | 0 |
| Toys R Us | US | **3** | 0 |
| Blockbuster, Sears | US | 20, 20 | 0 |
| Bed Bath & Beyond | US | **9** | 0 |

The unusually short result lists for Toys R Us (3) and Bed Bath & Beyond (9) are
themselves consistent with closed locations being filtered out.

So closure is reported from Google's own wording on the **detail** record, which
in practice means it only surfaces for a business supplied directly by URL or ID,
or when `verifyWithPlaceDetails` is enabled. That is stated plainly in the README
rather than implied.

### The trap: "closed" is in every record

Google's own suggest-an-edit menu contains **"Place is closed or not here"**, and
it is present on every listing, open or not — confirmed on three records where
two were trading normally. A parser that greps for `closed` marks the entire
dataset as closed. The same applies to `Report a legal issue` / `Report business
conduct`, which appear universally. All of these are stripped before the closure
wording is matched.

### What was deliberately not shipped

Diffing a suspected-closed listing against an open one showed slot `258` present
only on the suspect. It is a plausible status flag — but slot indices in this
payload have already been proven to move between responses (opening hours and
popular times both had to be found structurally), and there was no ground-truth
closed business to validate it against. Shipping it would mean guessing at a
field an SEO agency would act on, so it was left out.

---

## Opportunity scoring

Signals are weighted by what a Google Business Profile agency actually sells:

| Signal | Points |
| --- | --- |
| Unclaimed listing | 40 |
| No website | 25 |
| No phone | 10 |
| No opening hours | 10 |
| Fewer than 5 reviews | 10 |
| Rating below 4.0 | 5 |

A **permanently closed** listing is forced to 0 whatever else is wrong with it —
it is not a sales prospect, and letting it score highly would put dead businesses
at the top of a call list.

---

## Proxy posture

No proxy by default, and unlike the popular-times actor that is the right call
here: the claim signal is present even in Google's reduced record, so a
datacenter IP loses nothing. Residential is not recommended for Google — it draws
consent and CAPTCHA interstitials.
