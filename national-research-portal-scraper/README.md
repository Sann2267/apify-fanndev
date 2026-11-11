# National Research Portal Scraper - Garuda, CiNii & KCI

Search the official national research indexes of **Indonesia**, **Japan** and **South Korea** from one input, and get papers back in one shared shape: title, authors, journal, year, citations and a link to the record.

These portals hold the literature that never makes it cleanly into the global indexes - Indonesian university journals, Japanese society proceedings, Korean accredited journals - and each of them publishes a full-text or publisher link alongside.

## Why use this actor

- **Three national indexes, one schema.** A paper from Garuda, CiNii and KCI comes back with the same fields, so a comparison across countries is one sort.
- **Search in the local language.** Korean and Japanese queries return their own literature; English queries work too.
- **Garuda's three indexes**, not just papers: 7,400+ documents for "machine learning", a journal directory with ISSN and publisher, and a researcher directory with affiliations and document counts.
- **Real totals.** Every row carries `totalResults`, so you know how much more is behind the page you pulled.
- **Knows what each portal offers.** Ask CiNii for an author directory and you get an explicit row saying which portal has one, not an empty dataset.
- **Handles portals that move.** Garuda changed hosts when the Indonesian ministry split; this Actor tracks the live host and checks it in `reference` mode.

## How it works

1. Pick a mode, a portal (or `all`) and a query.
2. The Actor searches each portal's public index and pages through the results.
3. Every result is mapped onto one vocabulary - title, authors, source, year, URL - with portal-specific extras kept alongside.
4. Rows stream into your dataset for JSON, CSV or Excel export.

No account, no API key, no institutional access.

## Input

```json
{
    "mode": "documents",
    "portal": "all",
    "query": "machine learning",
    "maxItems": 200,
    "maxPages": 5
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `documents`, `journals`, `authors` or `reference`. |
| `portal` / `portals` | string / array | `garuda`, `cinii`, `kci` or `all`. |
| `query` | string | What to search for. Required for everything but `reference`. |
| `maxItems` | integer | Row cap, split evenly across the selected portals. Default `200`. |
| `maxPages` | integer | How deep to page per portal. Default `5`. |
| `ciniiArticlesOnly` | boolean | Search CiNii's article index only, instead of books, dissertations and datasets too. |
| `proxyConfiguration` | object | Optional; not needed. |

### Which portal supports which mode

| Portal | documents | journals | authors |
|---|:--:|:--:|:--:|
| **Garuda** (Indonesia) | yes | yes | yes |
| **CiNii** (Japan) | yes | - | - |
| **KCI** (South Korea) | yes | - | - |

### Example inputs

Compare coverage of a topic across all three countries:

```json
{ "mode": "documents", "portal": "all", "query": "deep learning", "maxItems": 300 }
```

Korean literature on a Korean-language term:

```json
{ "mode": "documents", "portal": "kci", "query": "인공지능", "maxPages": 10 }
```

Build a directory of Indonesian journals in a field:

```json
{ "mode": "journals", "portal": "garuda", "query": "teknologi" }
```

Find Indonesian researchers by name:

```json
{ "mode": "authors", "portal": "garuda", "query": "budi" }
```

## Output

### `ARTICLE` - Garuda

```json
{
    "recordType": "ARTICLE",
    "portal": "garuda",
    "portalName": "Garuda - Garba Rujukan Digital (Indonesia)",
    "title": "Optimizing Machine Learning in Natural Language Processing to Analyze User Sentiment in the Tiktok Social Media Application",
    "url": "https://garuda.kemdiktisaintek.go.id/documents/detail/6420654",
    "documentId": "6420654",
    "authors": [
        { "name": "Fahmi Setiawan", "authorId": "10420990" },
        { "name": "Izhar Fradila", "authorId": "10420991" }
    ],
    "authorNames": "Fahmi Setiawan; Izhar Fradila; Alwi Pernando; Supina Batubara",
    "source": "Journal of Information Technology, computer science and Electrical Engineering Vol. 1 No. 2 (2024): June-September 2024",
    "publisher": "Yayasan Sinergi Multidimensi Kreatif",
    "year": 2024,
    "downloadUrl": "https://ysmk.org/ejournal/index.php/jitcse/article/download/25/33",
    "sourceUrl": "https://ysmk.org/ejournal/index.php/jitcse/article/view/25/33",
    "page": 1,
    "totalResults": 7461
}
```

### `ARTICLE` - CiNii

```json
{
    "recordType": "ARTICLE",
    "portal": "cinii",
    "title": "Reinforcement and systemic machine learning for decision making",
    "url": "https://cir.nii.ac.jp/crid/1970304959881548164",
    "authorNames": "Kulkarni, Parag",
    "source": "IEEE Press",
    "year": 2012,
    "dataUrl": "https://cir.nii.ac.jp/crid/1970304959881548164.json",
    "totalResults": 95320
}
```

### `ARTICLE` - KCI

```json
{
    "recordType": "ARTICLE",
    "portal": "kci",
    "title": "GNN을 이용한 CT 영상 기반 폐혈관의 위상학적 복원 연구",
    "url": "https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003371447",
    "documentId": "ART003371447",
    "authors": [
        { "name": "박재현", "authorId": "0009-0007-3234-0519" },
        { "name": "유리", "authorId": "0000-0002-2377-8654" }
    ],
    "authorNames": "박재현; 유리",
    "source": "한국컴퓨터그래픽스학회논문지",
    "publisher": "(사)한국컴퓨터그래픽스학회",
    "volume": "32",
    "issue": "4",
    "pages": "23~32",
    "publicationDate": "2026-09",
    "year": 2026,
    "citationCount": 0,
    "totalResults": 2432254
}
```

KCI is the only one of the three that publishes a citation count, and the author IDs it gives are **ORCIDs** where the researcher registered one.

### `JOURNAL` (Garuda)

```json
{
    "recordType": "JOURNAL",
    "portal": "garuda",
    "title": "Adi Karsa: Jurnal Teknologi Komunikasi Pendidikan",
    "publisher": "Balai Teknologi dan Komunikasi Pendidikan DIY",
    "issn": "2088186X",
    "eissn": "31237622",
    "journalId": "46905",
    "url": "https://garuda.kemdiktisaintek.go.id/journal/view/46905"
}
```

### `AUTHOR` (Garuda)

```json
{
    "recordType": "AUTHOR",
    "portal": "garuda",
    "name": "Budi Sulistyo",
    "affiliation": "Pusat Teknologi Akselerator dan Proses Bahan",
    "documentCount": 0,
    "authorId": "243754",
    "url": "https://garuda.kemdiktisaintek.go.id/author/view/243754"
}
```

### `SOURCE` (reference mode)

```json
{
    "recordType": "SOURCE",
    "portal": "cinii",
    "isAvailable": true,
    "detail": "payload parsed",
    "sample": { "rows": 3, "totalResults": 95320, "supportedModes": ["documents"] }
}
```

### Error rows

```json
{
    "recordType": "ERROR",
    "portal": "cinii",
    "_error": "unsupported_mode",
    "_errorDetail": "cinii publishes no authors index. Portals that do: garuda. cinii supports: documents."
}
```

`_error` is one of `no_results`, `unsupported_mode`, `not_found`, `service_unavailable` or `blocked_or_transient`.

## What you can build with it

- **Systematic reviews that include non-English literature** - the same query across three national indexes, in one table.
- **Country-level research trend analysis** - `totalResults` per year or per topic, per portal.
- **Journal discovery** - Garuda's directory with ISSN, publisher and cover, for building a submission shortlist.
- **Researcher mapping** - Indonesian researchers by name or field, with affiliation and output count.
- **Open-access harvesting** - Garuda publishes a direct publisher link for a large share of its records.

## Notes & limits

- **Brazil's Lattes platform is not supported.** Its search needs a session-bound POST and returns nothing to a plain query; shipping it would mean shipping an empty portal. The recon is written up in the repository notes for whoever takes it further.
- **Garuda serves 10 rows per page**, CiNii and KCI 50 - so `maxPages` means different depths per portal.
- **KCI rows come from a run-on citation line**, split on the ORCID markers in it. The untouched line is always in `_raw` if you need to re-parse.
- **CiNii's default index includes books, dissertations, projects and datasets**, not just articles. Set `ciniiArticlesOnly` if you want papers only.
- **These are government portals.** They go down for maintenance more often than commercial sites; a maintenance page returns `service_unavailable` rather than being parsed as an empty result.
- **Abstracts are not fetched.** The Actor returns list-level records plus links; opening each paper is a different, much heavier job.

## Scheduling tips

- Topic monitoring: weekly per query is plenty - national indexes update in batches.
- Run `reference` once before a new schedule and after any long gap; these portals change hosts.
- For deep harvests, raise `maxPages` rather than running many small jobs - paging is cheaper than re-querying.

## Troubleshooting / FAQ

**`no_results` for a query that works in the browser.** Try the local-language term; Garuda and KCI index mostly local-language titles.

**`service_unavailable`.** The portal is in maintenance. It is a state of the source, not a failure of the run.

**Why does KCI show a huge `totalResults`?** KCI reports its whole index size next to the result count on some pages. Trust the rows you receive and the portal's own page when the number looks too round.

**Can I get abstracts or full text?** Garuda records carry a publisher link and often a direct download link. Fetching and parsing those documents is outside this Actor.

## Legal & fair use

All three portals are public, government-funded research indexes that publish this data for open discovery. This Actor reads them as published, without an account and without circumventing any access control, and paces its requests. Respect each portal's terms and each publisher's licence before redistributing full texts.
