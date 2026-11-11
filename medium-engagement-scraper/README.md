# Medium Article & Engagement Scraper

Scrape Medium articles **with their clap counts** — the number that tells you which posts
actually landed. Pull a whole topic, an author's back catalogue, a publication's latest
articles with their full text, or a single article end to end.

## Why use this actor

- **Engagement, not just headlines.** Claps and response counts per article, so you can rank a
  topic by what readers actually responded to rather than by what was published most recently.
- **35 articles per topic in a single request** — the richest slice this source gives out.
- **Paywall status on every article**, so you know which ones your readers can open.
- **Full article text** where Medium publishes it, in HTML and plain text.
- **Author and publication resolved**, not left as internal references: name, handle, and the
  publication each article ran in.
- **No account, no login, no API key.**
- **Honest about what each surface gives.** Where a figure is not published, the field is
  explicitly empty and a flag tells you why — no zeros standing in for missing data.

## How it works

1. You pick a mode and give it a topic, author, publication or article URL.
2. The actor reads Medium's public pages and pulls out each article with its engagement figures.
3. Results stream into your dataset — download as JSON, CSV or Excel, or load into a database.

Run it on a schedule against the topics you care about and you have a record of what performs.

## Modes

| Mode | What you get | Per request |
| --- | --- | --- |
| `tag` | Articles for a topic, **with claps** | ~35 articles |
| `author` | An author's recent articles, **with claps** | ~10 articles |
| `publication` | A publication's latest articles **with the article text** (no claps) | 10 articles |
| `post` | One article with its full text | 1 article |
| `reference` | Check the source is live and what each surface returns | — |

**Which modes give claps, and which give text, is a property of the source, not a choice.**
Topic and author pages publish engagement but only a preview; publication feeds publish the
article text but no engagement. Every record's `_source` field says which you got.

## Input

```json
{
  "mode": "tag",
  "tags": ["artificial-intelligence", "programming"],
  "tagSection": "top",
  "maxItems": 200,
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | `tag` (default), `author`, `publication`, `post` or `reference`. |
| `tag` / `tags` | string / array | Topics. A name, slug or `/tag/` URL all work. |
| `tagSection` | string | `top` (~35 articles), `archive` (newest, ~20) or `recommended` (~10). |
| `author` / `authors` | string / array | Medium handles or profile URLs, e.g. `@medium`. |
| `publication` / `publications` | string / array | Publication slugs or URLs, e.g. `better-programming`. |
| `postUrl` / `postUrls` | string / array | Full Medium article URLs. |
| `maxItems` | integer | Maximum records per run. Default 200. |
| `maxConcurrency` | integer | Pages fetched in parallel. Default 3. |
| `proxyConfiguration` | object | Residential proxy, on by default. Keep it on for scheduled runs. |

## Output

Real output from `mode: "tag"`:

```json
{
  "postId": "adf87621fb4a",
  "title": "The End of Patterns",
  "subtitle": "On recovery of a practice",
  "url": "https://medium.com/design-bootcamp/the-end-of-patterns-adf87621fb4a",
  "slug": "the-end-of-patterns-adf87621fb4a",
  "clapCount": 77,
  "responseCount": 1,
  "isPaywalled": true,
  "visibility": "LOCKED",
  "isSeries": false,
  "publishedAt": "2026-09-16T07:26:39Z",
  "updatedAt": "2026-09-16T07:26:39Z",
  "publishedAtEpochMs": 1789543599243,
  "authorName": "Joe Alterio",
  "authorUsername": "joealterio_7106",
  "authorId": "14f8b20ac0d7",
  "authorBio": null,
  "authorFollowers": null,
  "publicationName": "Bootcamp",
  "publicationSlug": "design-bootcamp",
  "publicationId": "48e972f5c24e",
  "tags": ["ai", "design", "product-design", "creativity", "patterns"],
  "previewImageAlt": "Antique game of Go Fish, with duos of matching cards.",
  "previewImageId": "1*JRC2jcK0mhRmAprJfaEimw.jpeg",
  "hasFullContent": false,
  "tagQueried": "artificial-intelligence",
  "tagSection": "top",
  "recordType": "POST",
  "_query": "artificial-intelligence",
  "_input": "artificial-intelligence",
  "_source": "medium-tag-apollo-top",
  "_scrapedAt": "2026-09-18T05:32:16Z"
}
```

Real output from `mode: "publication"` (content truncated here):

```json
{
  "postId": "3f456a51ff99",
  "title": "Calling AWS Bedrock from code",
  "url": "https://medium.com/better-programming/calling-aws-bedrock-from-code-3f456a51ff99?source=rss----d0b105d10f0a---4",
  "authorName": "Thomas Reid",
  "publishedAtRaw": "Fri, 10 Nov 2023 17:35:02 GMT",
  "updatedAtRaw": "2023-11-10T17:35:02.467Z",
  "tags": ["bedrock", "python", "llm", "boto3", "ai"],
  "contentHtml": "<div class=\"medium-feed-item\"><p class=\"medium-feed-image\"><a href=\"https://medium.com/bet ... (truncated)",
  "contentText": "Using Python in a Jupyter notebook   Continue reading on Better Programming » ... (truncated)",
  "contentSource": "description",
  "isContentFull": false,
  "clapCount": null,
  "responseCount": null,
  "publicationSlug": "better-programming",
  "recordType": "POST",
  "_query": "better-programming",
  "_input": "better-programming",
  "_source": "medium-publication-rss",
  "_scrapedAt": "2026-09-18T05:33:06Z"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `title` / `subtitle` / `url` / `slug` | string | The article and where to read it. |
| `clapCount` / `responseCount` | integer | Engagement. Present in `tag`, `author` and `post` modes; always `null` in `publication` mode, because the feed publishes none. |
| `isPaywalled` / `visibility` | boolean / string | Whether the article is member-only. |
| `publishedAt` / `updatedAt` / `publishedAtEpochMs` | string / number | When it went up, as ISO 8601 and as the source's own epoch milliseconds. |
| `authorName` / `authorUsername` / `authorId` / `authorBio` / `authorFollowers` | string / integer | The author. |
| `publicationName` / `publicationSlug` / `publicationId` | string | The publication it ran in, if any. |
| `tags` | array | Topics the article is filed under. |
| `tagQueried` / `tagSection` / `authorQueried` | string | What you asked for, kept alongside what came back. |
| `contentHtml` / `contentText` | string | Publication mode: the article body, as HTML and plain text. |
| `contentSource` / `isContentFull` | string / boolean | Whether that body is the full article or just a preview. |
| `bodyText` / `paragraphs` / `paragraphCount` / `isTruncated` | string / array / integer / boolean | Post mode: the article text, paragraph by paragraph, and whether the source cut it short. |
| `recordType` | string | `POST`, `SURFACE` or `ERROR`. |
| `error` / `errorDetail` | string | Present only on failure rows, so a problem is never a silently missing article. |

## Limits worth knowing before you run it

- **Claps and full text come from different places, and never together.** Topic and author
  pages carry engagement; publication feeds carry article text. If you want both for the same
  article, run `tag` to find it and then `post` to read it.
- **No pagination anywhere.** A topic gives about 35 articles, an author or publication about
  10, and there is no page 2. Cover more ground by querying more topics, more authors and the
  three different tag sections (`top`, `archive`, `recommended`), which return different sets.
- **Member-only articles are truncated at the source** — roughly 8 paragraphs instead of 70+.
  `isPaywalled` and `isTruncated` tell you when that has happened, and no attempt is made to
  get past it.
- **A publication's web page cannot be used.** It advertises 167 articles but carries no
  readable article behind any of them, so publication mode reads the feed instead — which is
  why publication records have no clap counts. `reference` mode re-checks this every run and
  will say if it ever changes.
- **Publication feeds carry the full article only sometimes.** In one measured feed, 4 of 10
  articles came through complete and 6 came as short previews. `isContentFull` tells you which
  is which per article.
