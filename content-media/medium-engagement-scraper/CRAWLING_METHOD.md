# Crawling method — Medium articles & engagement

Recon date: **2026-09-18**. Plain HTTP, no browser, no cookie, no login.

## Two strategies, assigned by measurement

**S1 — `window.__APOLLO_STATE__` in the server-rendered HTML.** A normalised Apollo cache, and
the only surface carrying **engagement**: `clapCount`, `postResponses.count`, `isLocked`.

**S2 — the RSS feed.** Always 10 items, no engagement figures, but it carries the article body.

Measured yields:

| Page | `Post:` entries | Usable (title + claps) | Strategy used |
| --- | ---: | ---: | --- |
| `/tag/<slug>` | 35 | **35** | S1 |
| `/tag/<slug>/archive` | 20 | **20** | S1 |
| `/tag/<slug>/recommended` | 10 | **10** | S1 |
| `/@<author>` | 10 | **10** | S1 |
| `/<publication>` | **167** | **0** | — |
| `/<publication>/archive`, `/latest` | 0 | 0 | — |
| `/feed/<publication>` | 10 items | n/a | **S2** |

TLS profile: `chrome124`, 200 on every probe. `medium.com/_/graphql` answers **403**, so the
private API is not a route. Neither surface paginates — `?limit=50` on RSS is accepted and
ignored — so breadth comes from querying more tags, authors and publications.

## Gotchas found during recon

1. **The publication-page trap.** A publication page looks like the richest surface in the
   whole source: **167 `Post:` entries**, against 35 on a tag page. Every one of them holds
   only `{"__typename": "Post", "id": "..."}`. Medium seeds the cache with references whose
   data is fetched client-side. An Actor that counted `Post:` keys would report 167 articles
   and emit 167 empty rows — the same hollow-200 shape as Blibli's bulk endpoint and Google's
   error page, arriving here as hollow *records* rather than a hollow response.
   `parse_apollo_posts` keeps only entries with a title, returns how many it dropped, and
   raises when *everything* was hollow so the failure is loud. Publication mode uses RSS
   instead, and `_source` records that.
   `/<publication>/archive` and `/latest` are worse: **zero** post entries at all.
2. **The Apollo cache is normalised and cyclic.** A post points at its author as
   `{"__ref": "User:14f8b20ac0d7"}`. Emitting that ships a pointer into the dataset, so refs
   are resolved into the entries they name — **depth-bounded**, because a post refers to its
   author whose entry refers back to posts, and an unbounded walk does not terminate.
3. **An HTML parser silently mangles the RSS feed.** The first version used `selectolax` for
   both surfaces, and every feed row came out wrong in three ways at once: `dc:creator` never
   matched so every article looked anonymous; `<![CDATA[` leaked into the title; and a per-item
   `title` lookup climbed out of the item and returned the **channel's** title, so row 1's
   title was the publication's name. The fix is `xml.etree` with an explicit namespace map.
   The smoke test now asserts all three — no CDATA in titles, every row has an author, no two
   rows share a title — because each failure produced plausible-looking output.
4. **The feed carries the full article only sometimes.** In one measured feed, 4 of 10 items
   had `content:encoded` (7,536 characters) and 6 had only a `<description>` preview (about 80
   characters). Records therefore carry `contentSource` and `isContentFull` so a preview is
   never mistaken for the article.
5. **`extendedPreviewContent.isFullContent` is not a truncation flag.** It describes the
   preview *card*, and reads `False` even on a free article served complete — using it marked
   77-paragraph articles as truncated. `isLocked` is what actually tracks whether the body was
   cut: a member-only article serves ~8 paragraphs / 1.2k characters, a free one served 77
   paragraphs / 14k characters.
6. **Timestamps are epoch milliseconds**, not seconds. Dividing by 1000 is the difference
   between 2026 and 58,000 years from now.
7. **A wrong article URL returns 200, not 404** — a page whose Apollo cache holds no post
   entry at all. `parse_post_detail` raises rather than emitting an empty article.

## Cost shape

- `tag`: **1 request per tag** → ~35 articles with engagement. The best value on this source.
- `author`: 1 request per author → ~10 articles with engagement.
- `publication`: 1 request per publication → 10 articles with text, no engagement.
- `post`: 1 request per article → full text where the article is free.
