# Diário de Notícias Scraper

Extract full article text or the newest headlines from Diário de Notícias (dn.pt), Portugal's oldest daily newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — every article's full text is delivered in the page's own structured data, even on stories the site itself marks as "premium"/subscriber content (a soft, metered paywall — see below)
- Full article text included, not just a summary — headline, description, section, author, publish/modified dates, images, and the complete body text
- A `_paywalled` flag tells you which stories dn.pt normally gates behind its subscriber metering, without ever withholding the text itself
- Also fetches the newest headlines straight from the site's RSS feed (near-real-time), which already embeds near-complete article text — no extra request per headline needed
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads dn.pt's RSS feed and returns the newest stories, including their (near-)full text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.dn.pt/cultura/morreu-aos-80-anos-a-cantora-country-dolly-parton"
  ],
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Latest headlines mode:**
```json
{
  "mode": "latest",
  "limit": 10,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (the feed itself typically carries ~17 items at a time). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real output, `articleBody` truncated here for readability):

Free article:
```json
{
  "_input": "https://www.dn.pt/cultura/morreu-aos-80-anos-a-cantora-country-dolly-parton",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T00:59:35Z",
  "_paywalled": false,
  "headline": "Morreu, aos 80 anos, a cantora country Dolly Parton",
  "description": "Dolly Parton morre aos 80 anos: relembre a trajetória da lendária cantora country, dos primeiros passos no Tennessee aos sucessos Jolene e I Will Always Love You...",
  "articleBody": "Morreu a cantora country Dolly Parton, aos 80 anos. A informação foi avançada esta terça-feira, 25 de agosto, através de uma publicação nas redes sociais... [3628 characters total]",
  "author": [
    {
      "@type": "Person",
      "givenName": "David Pereira",
      "name": "David Pereira",
      "url": "https://www.dn.pt/author/david-pereira",
      "image": "https://media.assettype.com/dn/2026-06-16/jvf2v10y/David_Pereira.png"
    }
  ],
  "keywords": "Dolly Parton,morte,cantora country,obituário,Jolene,I Will Always Love You,música country,...",
  "articleSection": "Cultura",
  "datePublished": "2026-08-25T19:25:41+01:00",
  "dateModified": "2026-08-25T19:38:52+01:00",
  "inLanguage": "pt",
  "thumbnailUrl": "https://media.assettype.com/dn/2026-08-25/a4r3i0ay/Dolly-Parton-2.jpg?w=1200&h=675&auto=format%2Ccompress&fit=max&enlarge=true",
  "image": [
    { "@type": "ImageObject", "url": "https://media.assettype.com/dn%2F2026-08-25%2Fa4r3i0ay%2FDolly-Parton-2.jpg?rect=0%2C0%2C4236%2C2383&w=1200&h=675&auto=format%2Ccompress&fit=crop", "width": "1200", "height": "675" },
    "... 2 more crop variants"
  ],
  "publisher": { "name": "Diário de Notícias", "url": "https://www.dn.pt", "...": "3 more fields" }
}
```

A "premium"-flagged article — note `_paywalled: true`, but `articleBody` is still the complete text (6,983 characters here):
```json
{
  "_input": "https://www.dn.pt/sociedade/940-mil-teleconsultas-no-ano-passado-2026-caminha-para-superar-um-milho-nos-centros-de-sade-e-hospitais",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T00:59:35Z",
  "_paywalled": true,
  "headline": "940 mil teleconsultas no ano passado. 2026 caminha para superar um milhão nos centros de saúde e hospitais",
  "description": "Teleconsultas no SNS crescem para 940 mil em 2025 e podem superar 1,1 milhões em 2026...",
  "articleBody": "O número de teleconsultas realizadas pelas unidades de cuidados primários (centros de saúde) e de cuidados hospitalares do Serviço Nacional de Saúde (SNS)... [6983 characters total, full article incl. two named-source interviews]",
  "author": [{ "@type": "Person", "givenName": "Ana Mafalda Inácio", "name": "Ana Mafalda Inácio", "url": "https://www.dn.pt/author/ana-mafalda-inacio" }],
  "articleSection": "Sociedade",
  "datePublished": "2026-08-25T22:06:41+01:00"
}
```

A not-found URL:
```json
{
  "_input": "https://www.dn.pt/sociedade/this-is-a-totally-fake-nonexistent-article-slug-xyz123",
  "_source": "none",
  "_scrapedAt": "2026-08-26T00:59:35Z",
  "_error": "not_found",
  "_errorDetail": ""
}
```

**Latest headlines mode** — one record per headline (real output, truncated):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T00:59:35Z",
  "title": "Portugal pode ajudar a trazer a ONU de 1945 para 2026",
  "link": "https://www.dn.pt/opiniao-dn/portugal-pode-ajudar-a-trazer-a-onu-de-1945-para-2026",
  "guid": "35060e0d-625e-4804-9ec2-24c35fd8c5bd",
  "pubDate": "Wed, 26 Aug 2026 00:24:56 +0000",
  "author": "Luís Vidigal",
  "keywords": "Inteligência Artificial,Opinião,Luís Vidigal,Carta das Nações Unidas,...",
  "categories": ["Opiniao DN", "colunistas"],
  "section": "opiniao-dn",
  "articleBody": "A 6 de setembro, quando a representação portuguesa subir à tribuna da 81.ª Assembleia-Geral das Nações Unidas... [6549 characters total, near-complete from the feed's own content:encoded]"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld` article mode, `S2-rss` latest mode). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `_paywalled` | boolean | Article mode only. `true` if dn.pt marks the story as premium/subscriber content. The full text is included either way — this is a soft paywall (see `CRAWLING_METHOD.md`). |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary/dek (article mode; usually empty in latest mode). |
| `articleBody` | string | Full plain-text article content — complete in both modes. |
| `author` | array/string | Article mode: array of byline objects (name, profile URL, photo). Latest mode: plain author name string. |
| `keywords` | string | Comma-separated keyword string (not an array). |
| `articleSection` / `section` | string | Section name, e.g. `"Sociedade"`, `"Cultura"`, `"Opinião DN"` / URL path segment (latest mode). |
| `datePublished` / `pubDate` | string | Publish timestamp. |
| `dateModified` | string | Last-modified timestamp (article mode only). |
| `image` / `thumbnailUrl` | array/string | Lead image(s) — dn.pt serves 3 crop variants per image (article mode only). |
| `link` | string | Article URL (latest mode). |
| `guid` | string | dn.pt's internal story UUID (latest mode). |
| `categories` | array | RSS category tags (latest mode only). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article URL).
