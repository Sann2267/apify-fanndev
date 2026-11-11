# Guardian Scraper

Extract public article metadata and latest headlines from The Guardian without any login or browser automation.

## Why use this actor

- Public data only: reads article pages and RSS feeds that are already visible to the general web.
- Simple, stable output: article metadata, authors, publication date, and summary fields.
- Good fit for news monitoring pipelines, media monitoring, and research automation.
- HTTP-only and lightweight, no headless browser required.

## Input

### Article mode (default)

```json
{
  "mode": "article",
  "urls": [
    "https://www.theguardian.com/world/2024/aug/02/uk-rainfall-flooding-weather"
  ],
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

### Latest headlines mode

```json
{
  "mode": "latest",
  "section": "world",
  "limit": 10,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

## Output

Each item contains the article metadata returned by the page’s JSON-LD or the Guardian RSS feed.

```json
{
  "_input": "https://www.theguardian.com/world/2024/aug/02/uk-rainfall-flooding-weather",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-24T00:00:00Z",
  "@type": "NewsArticle",
  "headline": "Rainfall warnings issued as flooding hits parts of the UK",
  "author": [{ "@type": "Person", "name": "Guardian staff" }],
  "datePublished": "2024-08-02T12:00:00+01:00",
  "description": "Heavy rainfall and flooding affecting communities across the country."
}
```

## Notes

- The Guardian publicly exposes article metadata in JSON-LD. This actor reads it directly.
- The actor does not bypass paywalls or log in.
- For newest headlines, it reads the Guardian RSS feed for the chosen section.
