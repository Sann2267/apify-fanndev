# Crawling method — Facebook page reviews

Measured 2026-09-20, curl_cffi, no proxy, no login, exit IP Indonesia.

## The reviews tab is not JavaScript-only

A first pass over `/{slug}/reviews` suggests it is: grepping the 1 MB response
for `overall_star_rating`, `is_recommended` or `rating_count` returns nothing,
and `Recommend` appears 47 times — all of them JS module names like
`AdsRecommendationCompetitiveIndustryBenchmarkingTooltip.react`.

Scanning the embedded JSON for *key names* rather than values finds the data
immediately:

```
profile_rating_reviews.title.text -> "30% recommend (12,651 reviews)"
reviews_feed.edges[].node          -> the reviews themselves
```

The lesson generalises: on Facebook, grepping a payload for the field name you
expect tells you nothing, because the field you expect may not exist. Facebook
retired star ratings for pages — the rating *is* the percentage, so
`overall_star_rating` was never going to be there.

## A review is scattered across nodes, joined by post id

Within `reviews_feed`, one review is spread over several nodes:

- the recommend sentence and the reviewer:
  `{post_id, title: {text: "Mike Phipps  doesn't recommend Domino's Pizza."}, actors: [...]}`
- the written body: a node whose only identifying field is a base64 `id`
- the engagement: `i18n_reaction_count`, `comments.total_count`
- the experience tags: `attachments[].styles.attachment.tags`
  (`["Disappointing food", "Casual"]`)

The base64 ids decode to the post:

```
UzpfSTYxNTUyOTY1OTQ0MzI2OjEyMjI1ODIyNjM2ODA5ODg2NDoxMjI...
  -> "S:_I61552965944326:122258226368098864:122258226368098864"
ZmVlZGJhY2s6MTIyMjU4MjI2MzY4MDk4ODY0
  -> "feedback:122258226368098864"
```

so the parser files every field under the post id its node names.

**Gotcha that cost a test:** reading the body off the node that owns the title
returns every review with `reviewText: null`. The body is not on that node. The
live check therefore asserts on review *bodies*, not just review count.

## The vote has no boolean

Nothing in the payload says `is_recommended`. The only expression of the vote is
the rendered sentence. So it is parsed from text, with the negative tested first
— `"doesn't recommend"` also contains `"recommend"` — and left `null` when
neither pattern matches. The session requests `en-US` so the sentence is in
English; a non-English sentence yields `null` rather than a coin flip.

## Pagination: two queries, both read at runtime

- `ProfileCometReviewsFeedQuery` — id **and variables** published in the page's
  relay preloader block. Replaying it returns reviews plus a cursor whose
  `end_cursor` is itself a JSON blob
  (`{"in_progresscursor_type":"online","local_rec_pattern_cursor":"AQ...","rating_cursor":"","offline_offset":-1}`).
- `ProfileCometReviewsFeedRefetchQuery` — the pagination query. Its id is **not**
  in the HTML; it is read from the page's JS bundle
  (`27784759277868859` at time of writing), and its 25 declared argument names
  are read from the same module so the variables are built from what the query
  actually takes rather than from a guess.

Measured throughput: **3 reviews per request**. 12 reviews took 4 requests.

## Partial errors are normal here and must not fail the run

Both queries return an `errors` array alongside the data:

```
"A server error field_exception occured" … path: [... "save_info", "save_flow"]
```

`save_flow` is a signed-in-only field; a logged-out client cannot have one. The
reviews come back in the same response. Treating the envelope as a failure would
throw away every review on the page, so the error is ignored and the data is
read.

## Existence check

Facebook answers HTTP 200 for a slug that does not exist. The shell is ~330 KB
and carries no page JSON, so size is the discriminator — the same one the
`facebook-page-validator` actor is built on. `zz-not-a-real-page-98765` returns
the shell; `dominos` returns 1 MB.

## Cost shape

One request for the tab (rating summary included), then ~1 request per 3
reviews, plus a one-off bundle fetch the first time pagination is needed in a
session. No proxy, no browser.
