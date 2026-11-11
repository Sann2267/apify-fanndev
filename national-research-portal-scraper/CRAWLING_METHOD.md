# Crawling method - Garuda / CiNii / KCI

Recon date: **2026-09-18**, plain HTTP, no proxy, no account, `chrome124`.

## Host changes found (both would have failed a stale scraper)

| Portal | Old host in the research notes | Live host today |
|---|---|---|
| Garuda | `garuda.kemdikbud.go.id` | **DNS does not resolve.** Live host is `garuda.kemdiktisaintek.go.id` |
| BIT (Japan auctions, sibling recon) | `bit.courts.go.jp` | **DNS does not resolve.** Live host is `www.bit.courts.go.jp` |

Indonesian government portals moved when the ministry split - SINTA did the same
earlier. Any recon note older than that split needs its hosts re-checked before
it is trusted.

## Surfaces

| Portal | Endpoint | Result |
|---|---|---|
| Garuda documents | `/documents?q=&page=` | 200, 62 KB, `div.article-item` x10, "Found 7,461 documents" |
| Garuda journals | `/journal?q=&page=` | 200, 33 KB, table rows with `a.title-journal`, up to page 3059 |
| Garuda authors | `/author?q=&page=` | 200, 28 KB, `a.title-author`, "29,195 Authors" for "budi" |
| CiNii | `/opensearch/all` and `/opensearch/articles` | 200 JSON, `opensearch:totalResults`, 1-based `start` paging |
| KCI | `/kciportal/po/search/poArtiSearList.kci` | 200, 455 KB, `table.search-answer-tbl` |

No WAF on any of the three.

## Gotchas found (and handled in code)

1. **KCI's obvious search path is a 404.** `poSereArtiSearList.kci` - the path
   the UI's own links suggest - returns 404 with any parameters. The working
   one is **`poArtiSearList.kci`** with `poSearchBean.searchQuery`. A path that
   *looks* right is not evidence; only a 455 KB body with rows is.
2. **KCI duplicates every article link inside `<script>` handlers.** The parser
   strips script blocks first, otherwise every row appears twice.
3. **A KCI row is one run-on string**: `1 . KCI 등재 <title> <author> <ORCID>
   <author> <ORCID> (society) <journal> 32(4) pp.23~32 2026.09 <subject> 피인용
   횟수 : 0`. ORCIDs are the only unambiguous delimiter, so they anchor the
   parse: authors are the words before each ORCID, and the journal block is
   whatever follows the last one. The raw line always ships in `_raw`.
4. **KCI volume is sometimes absent**: `32(4)` and a bare `(53)` both occur, so
   the volume group is optional in the regex. The first draft dropped the
   journal name for every row of the second kind.
5. **Garuda puts its text in `<xmp>` elements** - a deprecated tag whose
   contents are literal text. It lets the portal print titles containing raw
   HTML without escaping, and it means reading the parent's text concatenates
   several values; each `<xmp>` is read individually.
6. **Garuda's "last page" is a page with no rows**, not a 404. An empty parse
   result therefore ends the walk instead of raising.
7. **CiNii's `start` is 1-based**, not 0-based - paging from 0 silently repeats
   the first record.
8. **Government portals serve maintenance pages with a 200.** The client checks
   for maintenance markers on small bodies and raises `ServiceUnavailable`, so a
   maintenance window is never parsed as "no results".

## Verified numbers (2026-09-18)

| Query | Portal | Total results |
|---|---|---:|
| machine learning | Garuda documents | 7,461 |
| machine learning | CiNii (all) | 95,320 |
| machine learning | CiNii (articles) | 50,366 |
| budi | Garuda authors | 29,195 |
| teknologi | Garuda journals | rows on every page, 3,059 pages of index |

## Lattes (Brazil): recon'd, not shipped

`buscatextual.cnpq.br/buscatextual/busca.do` answers 200 with 183 KB, and the
form exposes inputs (`acao`, `buscarBrasileiros`, `filtro0..7`). But:

* the documented-looking GET
  (`?metodo=forwardPaginaResultados&registros=0;10&query=+idx_nme_pessoa:(silva)`)
  returns 29 KB with **zero** result markers (`preview.do`, `id=K`);
* the page is ISO-8859-1 and the result list is rendered only inside an
  established session, after a POST.

Shipping it would mean shipping a portal that always returns nothing, so it is
left out. Anyone continuing should start from the POST that the form's
`buscarBrasileiros` button issues, with the session cookie from a prior GET.

## CNKI (China): not attempted

Known to require a paid institutional login for result pages. Out of scope for
an Actor that does not hold credentials.
