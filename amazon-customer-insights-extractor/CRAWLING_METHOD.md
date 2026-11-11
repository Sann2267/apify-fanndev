# Crawling method — Amazon Customer Insights

Recon date: **2026-09-02**. Every figure below was measured live.

## First finding: Amazon Q&A is gone

This actor was commissioned as a **Customer Questions & Answers** scraper.
That surface no longer exists for anonymous clients, which was established
before any code was written:

| Probe | Result |
| --- | --- |
| `/ask/questions/asin/<ASIN>/1` | 200, but the final URL is **`/ap/signin`** |
| `/ask/questions/asin/<ASIN>/ref=…` | same sign-in redirect |
| `/ask/questions/inline/<ASIN>/1` | same sign-in redirect |
| `/ask/questions/search?asin=…` | same sign-in redirect |
| `/askvideo/questions/asin/<ASIN>` | **404** |
| `/askwidget/questions/asin/<ASIN>` | **404** |
| `hz/reviews-render/ask-questions?asin=…` | **404** |
| Product page, 4 ASINs | **0** Q&A content |
| Mobile page `/gp/aw/d/<ASIN>` + mobile UA | **0** Q&A markers |

Two details make this conclusive rather than a parsing miss:

- A regex for **any** URL containing `ask` or `question` in the product
  page's markup and JS returned **0 matches**. The feature is not lazily
  loaded; it is not referenced at all.
- The three `ask-btf` hits that do appear are layout configuration strings
  (`btf-sub-nav-desktop-questions`), not content.

Meanwhile `Rufus` appears 5 times on the same page — Amazon's AI assistant,
which is what the Q&A feature was folded into.

A Q&A actor would therefore have returned zero rows for every ASIN. The
scope was moved to the surface that replaced it.

## The replacement: the "Customers say" widget

Three independent signals carry it.

### 1. Aspect + sentiment + volume, in aria-labels

```
aria-label="Positive aspect, quality, 2185 mentions"
aria-label="Mixed aspect, mixability, 847 mentions"
aria-label="Negative aspect, texture, 389 mentions"
```

Sentiment, name and total mentions, which is what makes the data rankable.
What it does **not** carry is the split behind that total.

### 2. `aspectsFlattened`, the widget's own JSON

The richest signal, and the one that was missed on the first pass. Buried in
a base64 payload (see §4) sits the object the widget actually renders from:

```json
{"label": "texture", "sentiment": "negative", "mentions": 392,
 "sentimentMentions": 91, "mentionsPercentage": 23,
 "summary": "Customers dislike the texture…", "snippets": [ … ]}
```

**`sentimentMentions` is the POSITIVE count for every aspect, including the
negative ones.** Texture above is sentiment `negative` with 392 mentions and
`sentimentMentions` 91, and the page reads "91 positive, 301 negative". Read
the field as "mentions matching the aspect's sentiment" — which is what the
name suggests — and the split inverts on exactly the gap aspects this actor
exists for. Negative is therefore derived as `mentions - sentimentMentions`,
and `mentionsPercentage` is just `sentimentMentions / mentions` rounded.

`summary` is a per-aspect sentence, one per chip, distinct from the
product-level paragraph in §4. It is **never rendered as page text** — the
widget shows it only after a chip is clicked — so it is invisible to any
HTML-text scrape that does not decode the payload.

A dozen components embed the byte-identical list (`MainView`, `AspectList`,
one `AspectButtonRender` per chip); the parser keeps the first.

Being JSON with an English sentiment enum, this signal also survives
localization, so it now carries counts where the English aria regex cannot
match at all.

### 3. The screen-reader line, as a split fallback

```
>634 customers mention writing quality, 617 positive, 17 negative<
```

Both numbers stated outright, in a `white-space: pre-line` span under each
chip. Used to fill `positive` / `negative` when the payload is absent. It
carries no summary, so a page reduced to this signal returns the split with
`aspectSummary: null` rather than a guess.

### 4. Click-tracking ids, as a last resort

```
cr-product-insights-detail-page_button_0_POSITIVE_quality
cr-product-insights-detail-page_button_5_MIXED_mixability
```

No counts at all. The parser merges every signal, aria first, and
de-duplicates case-insensitively — a test asserts that a product carrying
both aria and tracking ids yields 3 aspects, not 6.

When a count arrives from no signal, it stays **null**. Defaulting it to 0
would make the aspect look like something nobody mentioned.

### 5. The payload format

Neither the product paragraph nor `aspectsFlattened` is in the HTML as
readable text. Both live in injected comments:

```
<!-- k-injected k+b64 eyJrLW9ic2VydmUiOiIiLCJrLWNvbXBvbmVudCI6IlN1bW1hcnlG… -->
```

which base64-decode to JSON:

```json
{"k-component": "SummaryFragments-…",
 "k-data": {"fragments": [{"inertText": "Customers love this whey protein powder for…"}]}}
```

A page carries ~635 such blobs; the parser decodes them and keeps the first
carrying `k-data.fragments[].inertText` (the paragraph) and the first
carrying `k-data.aspectsFlattened` (the aspects). Padding is repaired before
decoding (`+ "=" * (-len(b) % 4)`) and malformed blobs are skipped rather
than raised — a test feeds it 100 `!` characters.

Sibling components named after the data are decoys: `AspectButton` decodes
to `{"isDisabled": false}` and the standalone `SnippetList` to `{}`. The
real snippets — roughly four short review excerpts per aspect, each with its
review id — are nested inside `aspectsFlattened[].snippets`. They are
present in the HTML, contrary to the first pass's reading of those empty
components; this actor does not emit them yet.

## The reduced page, which is not a block

`is_blocked()` catches the ~3.8 KB bot wall. It cannot catch the other
failure mode, because that one is not a failure by any measurable property:
a **full-size product page, served HTTP 200, that parses completely** —
title, rating, review count, everything — with the insight widget simply
absent.

Measured on `0061120081` (To Kill a Mockingbird): one residential exit
returned 149,157 ratings and **zero aspects**; the next exit, minutes later,
returned all 8. Same ASIN, same build, same marketplace. This is the same
exit-IP-tracked withholding the sibling Buy Box actor documents.

The consequence is that `hasInsights: false` carries two incompatible
meanings, and no property of the response separates them. **The review count
does**: the reduced page still publishes it. Above
`INSIGHT_RETRY_MIN_REVIEWS` (100) an empty widget is not credible and the
actor rotates the proxy session and refetches; below it, empty is the honest
answer and no request is wasted. A product with no reviews publishes no
count at all, so it is never retried.

A retry that comes back blocked keeps the first response rather than
downgrading a real product row to a diagnostic.

## Structure of the widget

Exactly **8 aspects** on every one of 10 ASINs tested, no duplicates,
ordered by button index and grouped by sentiment — positives first, then
mixed, then negative:

```
button_0 POSITIVE quality          2185
button_1 POSITIVE taste            1663
button_2 POSITIVE ingredients       595
button_3 POSITIVE protein quality   431
button_4 POSITIVE consistency       313
button_5 MIXED    mixability        847
button_6 MIXED    digestibility     296
button_7 NEGATIVE texture           389
```

Counts descend *within* a sentiment group but not across the whole list, so
the actor re-ranks by mentions globally and asserts that ordering in a test.

## Coverage

| ASIN sample (10, mixed categories) | Result |
| --- | --- |
| Aspect list | **10/10** |
| AI summary | **10/10** |

Categories spanned supplements, a renewed iPhone, a paperback and a yoga
mat, so this is not a single-category artefact. This is a far more reliable
surface than the Buy Box data in the sibling ASIN actor (~50% without
session rotation).

## Fingerprints and blocks

Same `/dp/` surface as the sibling Buy Box actor, so the same measured
ladder applies: **chrome131, chrome133a, chrome150, chrome136**. This is
*not* the Amazon search ladder — safari184 passes on search and fails here.
A test asserts the list.

The block is an HTTP **200** of ~3,781 bytes ("Click the button below to
continue shopping"), so status is useless as a signal; anything under 250 KB
is treated as blocked (a real page is ~2.5 MB).

## Marketplaces: verified vs unverified

`amazon.com` and `amazon.ca` both returned full pages with English aria
labels and 8 aspects.

`amazon.co.uk` and `amazon.de` returned the **3,805-byte bot wall on all 10
TLS profiles tried** — including profiles that work on `.com`. That is an IP
block from the development location, **not** evidence the widget is absent
there. The honest position is that their behaviour is unknown, so they are
offered in the input with an explicit warning in the log and the README,
rather than being silently promised or silently removed.
