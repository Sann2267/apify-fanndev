# Crawling method — Blibli keyword suggestions

Recon date: **2026-09-01**. Every figure below was measured live.

## Blibli publishes no search volume

Stated first, because the honest shape of this actor depends on it.

Across **65 autocomplete suggestions from 10 different prefixes**, every
volume-shaped field came back null — `productCount`, `count` — and `dsScore`
was `0.0` on every single row. There is no volume, impression count or
frequency anywhere in the payload, and no other endpoint in the search
family exposes one.

So this actor reports no volume figure. In its place it provides two things
that are actually measured:

| Signal | What it is |
| --- | --- |
| `competingProducts` | How many products Blibli returns for the keyword (`paging.total_item`). Real, and the number that tells a merchant how hard a term is to rank for. Measured spread is wide: "laptop" 58,744 vs "laptop gaming" 6,639 vs "laptop advan" 644. |
| `suggestPosition` | Rank within Blibli's own autocomplete ordering, produced by their relevance model. An ordinal popularity signal, labelled as such — not a volume. |

A regression test asserts the no-volume claim still holds, so if Blibli ever
*adds* a volume field the test fails loudly rather than the actor silently
continuing to omit it.

## Endpoints

| Purpose | Endpoint |
| --- | --- |
| Autocomplete | `GET /backend/search/autocomplete?searchTermPrefix=<prefix>` |
| Related ("refine your search") | `GET /backend/search/refineSearchKeyword?searchTerm=<kw>` |
| Trending searches | `GET /backend/brs-api/trendingSearchTiles` |
| Curated promo keywords | `GET /backend/search/curatedKeywords` |
| Competition count | `GET /backend/search/products` (`paging.total_item`) |

**The autocomplete parameter is `searchTermPrefix`.** The obvious guesses —
`searchTerm`, `q`, `keyword` — all return
`400 Required request parameter 'searchTermPrefix' ... is not present`,
which at least names the right parameter in the error.

The response splits into several buckets; `data.suggestions` is the keyword
list. The others (`anchorStore`, `brands`, `digitalProducts`,
`recommendedProducts`, `termInCategory`, `categoryAffinitySuggestion`) carry
stores, brands and products rather than search terms and are not keyword
sources.

Endpoints that looked promising but are not usable:
`/backend/common/search/_top-keywords` returns `500`,
`/backend/search/auto-suggestion-products` returns `500`, and
`/backend/search/getSeedKeyword` returns an empty list.
`/backend/brs-api/getRelatedSearchTerms` returns `relatedTerms: []` — the
working related-terms source is `refineSearchKeyword`.

## Suffix expansion is what makes this worth running

A bare seed returns only a handful of suggestions. Appending a character
pulls a *different* slice of the suggestion index each time. Measured on
`laptop`:

| Query | Result |
| --- | --- |
| `laptop` (bare) | **6** suggestions |
| `laptop` + a–j | **67** unique keywords, in 1.6 s |
| `laptop` + a–z (full alphabet) | **147** unique keywords |

That is a 24× lift over what the search box visibly offers, and it surfaces
phrasings a merchant would never think to type: 31 of those 147 do not even
begin with the seed — `asus laptop`, `backpack laptop`, `tote bag laptop`,
`tas laptop jinjing`, `cooling fan laptop`.

Cost per seed: 1 request (`none`), 27 (`alphabet`), 37 (`alphanumeric`), 38
(`full`), plus one request per keyword when competition measurement is on.

## WAF profile

Cloudflare, `Referer` mandatory, ladder leading with `safari17_0`. Sustained
recon from a single IP drew intermittent 403s that cleared on retry with a
rotated fingerprint. With expansion plus competition measurement this actor
is the most request-heavy of the Blibli set, so residential proxy matters
here more than elsewhere.

## Known limits

- **No search volume** — see the top of this document.
- `competitionLevel` bands (LOW <1k, MEDIUM <10k, HIGH <50k, VERY_HIGH) are
  a readability convenience from this actor, not a Blibli metric. The raw
  count sits next to them.
- Autocomplete is personalised/regional to a degree; results are what an
  anonymous Indonesian visitor sees, which is the right baseline for
  marketplace SEO but may differ slightly from a logged-in shopper's box.
- Suggestions are Indonesian-language, as shoppers type them.
