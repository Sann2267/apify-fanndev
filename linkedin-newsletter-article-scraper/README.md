# LinkedIn Newsletter & Article Scraper

Read LinkedIn long-form articles in full — body text, author, publish and edit dates, reactions and comments — and get reading time and a fair cross-author engagement metric computed for you.

**No login required.** LinkedIn's `/pulse/` article pages are open to anonymous visitors.

## What you get

```json
{
  "articleTitle": "How do we build a frontier intelligence ecosystem?",
  "authorName": "Satya Nadella",
  "authorFollowers": 12177036,
  "publishedAt": "2026-06-02T19:41:31.000+00:00",
  "modifiedAt": "2026-06-02T19:42:00.000+00:00",
  "wordCount": 215,
  "readingTimeMinutes": 1.0,
  "reactions": 2535,
  "comments": 140,
  "engagementPerThousand": 0.21,
  "articleText": "Great to be back at Microsoft Build today..."
}
```

**`engagementPerThousand` is the field to sort on.** Raw reaction counts just rank authors by audience size. Reactions per thousand followers tells you whether a piece actually landed — and lets you compare a 200-reaction article from a niche expert against a 2,500-reaction one from a CEO with twelve million followers.

`modifiedAt` next to `publishedAt` is quietly useful too: it shows which pieces the author went back and revised.

## Newsletters: read this before you buy

**LinkedIn newsletter *series* pages are closed to logged-out visitors.** Every request to `/newsletters/{id}` returns HTTP 500 with the same error body — tested against several ids, including real-looking ones. There is no public surface for **subscriber counts**, and no cookie option in this actor changes that.

What *does* work: **individual newsletter issues are `/pulse/` articles.** Paste those links into `articleUrls` and you get the full text and engagement for every issue, exactly like any other article.

If you pass a `/newsletters/` URL anyway, the run does not fail — it emits a `NOTICE` row telling you this. An empty dataset always comes with a reason attached.

## Discovering articles instead of listing them

Give `authorProfiles` a member handle and the actor reads the articles linked from their public profile:

```json
{
  "authorProfiles": ["satyanadella"],
  "maxArticlesPerAuthor": 20,
  "minReactions": 100
}
```

`minReactions` is the useful knob here — it turns "everything this person wrote" into "the pieces that actually worked", which is usually the question you were asking.

## Comments

`includeComments` attaches the commenters LinkedIn renders on the public page — name, profile link and comment text — at **no extra request cost**, since they arrive in the same page load.

The honest limit: LinkedIn publishes roughly the **first 8 comments** to logged-out visitors. `commentSampleSize` tells you how many you got and `comments` tells you the true total, so the gap is always visible rather than assumed away.

## Who this is for

- **Content strategists** — what topics and lengths earn engagement in your field, measured rather than guessed.
- **SEO and PR specialists** — who is publishing about your category, how often, and who they link to (`externalLinks`).
- **Industry analysts** — the `SUMMARY` row gives median reactions, median length and top hashtags across a whole run, which is a fast read on where executive attention is going.

## A parsing note

LinkedIn's article JSON-LD stores the **title** in `name` and the **opening excerpt** in `headline` — the opposite of what those field names suggest — and `articleBody` is always empty. Scrapers that trust the field names ship excerpts labelled as titles. This actor reads `name` for the title and lifts the real body from the rendered page, trimming LinkedIn's byline and "Report this article" chrome off the top.

## Rate gating

LinkedIn answers request bursts with **HTTP 999** and a ~1.5 KB stub page. It is per-IP and per-burst, not a TLS fingerprint gate. The actor sleeps a random 3–8 seconds between page loads, backs off exponentially when gated, and rotates among five browser fingerprints. Raise both delay bounds if the log shows rate-gate warnings.

Deleted articles redirect to LinkedIn's top-content hub, which answers 200 with no article on it — those produce a `not_an_article` notice rather than a silently empty row.

## Related actors

- **LinkedIn Top Voice & Competitor Activity Monitor** — posting cadence and format mix for any account.
- **LinkedIn Post Engagers Scraper** — who engaged with a specific post, with their comments.
