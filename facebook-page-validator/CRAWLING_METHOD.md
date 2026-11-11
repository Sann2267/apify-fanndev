# Crawling method

Recon date: 2026-09-20. Everything below was measured against live pages, not inferred.

## Surface

One request per slug:

```
GET https://www.facebook.com/{slug}/about
```

The `/about` tab is used rather than the page root because it is the only one carrying the category and contact sections, and it costs the same single request.

No login, no cookies, no consent handshake, no token. Plain browser navigation headers are enough.

### What is *not* gated

- **No TLS fingerprint gate.** All 16 curl_cffi profiles tested (chrome99 → chrome133a, edge, safari, firefox, iOS) returned 200 with identical payloads. This is unlike most targets, where a profile ladder is load-bearing. The ladder in `client.py` exists only as a courtesy rotation on 403/429/503.
- **No IP gate on page HTML.** The Apify platform IP works directly.

### What *is* gated, and is therefore out of scope

- **Ad Library** (`/ads/library/`) returns `403` / 481 bytes on all 16 TLS profiles, with full browser headers, and on `m.facebook.com`. That is an IP/geo gate — a different profile does not help, only a different exit IP.
- **`mbasic.facebook.com`** 302s to `/login`.
- **Post pagination, the transparency tab and reviews** are JS-rendered. The 8.7 MB transparency response is JavaScript bundle, not data. Calling `/api/graphql/` anonymously does return 200 with an LSD token harvested from the page, but **no `doc_id` appears in page HTML any more** (0 hits), and without one the response is `error 1357031 "content is no longer available"`. Recovering doc_ids means harvesting lazy-loaded JS bundles; deliberately not done here.

## Existence detection

Facebook answers **HTTP 200 for every slug**, real or not, so the status code carries no information. The discriminator is response size.

Measured over 20 pages with 3 repeats each, byte-stable across repeats:

| Tier | Size | Evidence |
|---|---|---|
| `HOLLOW` | ~330 KB | A deliberately fake control slug (`zzqq-not-a-real-page-9876543`) returns the same size as unresolvable guesses, three fetches running. |
| `REDUCED` | ~0.7–1.4 MB | Header present, feed withheld. NASA reduced on 3/3 fetches; Coca-Cola 1.4 MB with 2 posts. Sticky per page, not a random throttle. |
| `FULL` | ≥1.5 MB | Header plus ~10 posts. Nike 8.1 MB, Starbucks 19.6 MB. |

Thresholds sit in the wide empty gaps between clusters (450 KB and 1.5 MB), because sizes wobble by a few KB between fetches.

There is no cheap shortcut: `HEAD` returns 200 with **no `content-length`**, and `Range: bytes=0-120000` is ignored and returns the whole body. The full response must be downloaded.

## Parsing

Facebook ships ~230 `<script type="application/json">` blocks per page and **their order changes between requests**, so nothing is read by position. Every field is located by a marker key:

| Field | Marker |
|---|---|
| followers / following | a dict with key `profile_social_context` → `content[]` → `{text.text, uri}`; the two rows are told apart by `uri` ending in `/followers` vs `/following` |
| category, phone, website, email, address | a dict with key `field_section_type` (`category`, `about_contact_info`, `websites_and_social_links`) → `profile_fields.nodes[]` → `{title.text, field_type}` |
| pageId | base64 in the section `id`, decoding to `profile_field_section:<PAGEID>:category` |
| name | `og:title`, falling back to `<title>` |
| post count | distinct `creation_time` integers in a plausible epoch range |

**A field no marker resolves is emitted as `null`, never inferred from a nearby number.** An earlier regex-based pass reported `bukalapak` as having 124 followers and that was assumed to be a misparse; it was not. `facebook.com/bukalapak` genuinely belongs to an app page called *Eoddata beeip.com* with 124 followers. The structural parser confirms it independently via `og:description` (`"Eoddata beeip.com. 124 followers. App Page"`), and that discovery is what the brand-match feature exists to surface.

### og:description fallback

`og:description` packs a compact summary — `"<name>. <n> followers. <category>"` — and **survives on REDUCED payloads where the about sections are absent entirely**. It is applied only to fields the structural pass could not fill, so a summary value never overwrites a real profile field.

### Link unwrapping

Outbound website links are rewritten to `l.facebook.com/l.php?u=<encoded>&h=<token>`. The token is per-render, so the wrapped URL is not stable between two fetches of the same page. `unwrap_link()` recovers the real target from the `u` parameter.

## Known-good fixtures

| Slug | Tier | Expected |
|---|---|---|
| `nike` | FULL | Nike, 39M followers, Sportswear shop, phone + website |
| `tokopedia` | FULL | `Tokopedia | Jakarta`, 6.3M |
| `kopikenangan.id` | FULL | `Kopi Kenangan | South Jakarta`, 28K, phone present |
| `NASA` | REDUCED | 28M followers, 0 posts (feed withheld) |
| `bukalapak` | REDUCED | **Eoddata beeip.com**, 124 followers — brand MISMATCH |
| `zzqq-not-a-real-page-9876543` | HOLLOW | does not exist |
