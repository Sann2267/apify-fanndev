---
name: actor-store-monetization
description: "Mandatory Phase 4-9 that runs after adding-new-actor's build/test/push workflow (Phase 1-3) confirms an actor works: research Apify Store competitors, assign the Store category, and configure evidence-based pay-per-event/pay-per-usage pricing. Use immediately after an actor is built, tested locally, pushed, and verified remotely — before marking that actor 'completed'. Do not run this on an actor that hasn't cleared Phase 1-3 yet, and never invent competitor stats, pricing, or user counts that weren't actually retrieved."
---

# Skill: Apify Store Market Research, Category & Monetization

This is the required continuation of [`adding-new-actor/SKILL.md`](../adding-new-actor/SKILL.md).
It does not modify, remove, reorder, or weaken anything in that build/test/push workflow — it only
starts once that workflow has produced a verified working actor, and it is what turns "builds and
runs" into "actually completed." Complete every phase below for one actor before starting the next
actor in the queue.

**Trigger condition — do not skip this skill.** The moment an actor from `adding-new-actor` has:
built successfully, passed local testing (`python main.py latest N` + `python main.py "<url>"`),
been pushed (`apify push -f`), been run remotely (`apify call`), and had its remote dataset output
verified — treat Phase 4-9 below as the next mandatory steps, not an optional add-on the user has to
ask for again. Never configure monetization on an actor that hasn't cleared that bar, and never
publish a broken actor merely to test monetization.

---

## Phase 4 — Competitive analysis

Before touching Store settings, find the actors that already compete with the one you just built.

1. Pull your own inventory (if not already fresh from earlier in the session):
   ```bash
   python apify-my-store.py <your-username>
   ```
2. Search the Store for the same platform/data-type using `api-search-actors.py` (see
   [`apify-store-research/SKILL.md`](../apify-store-research/SKILL.md) for full flag reference) —
   query by keyword/platform name rather than broad category browsing, since you're now checking one
   specific niche, not discovering new ideas:
   ```bash
   python api-search-actors.py --query "<platform or data-type keyword>" --length 20
   # then re-run WITHOUT --max-users to confirm nothing dominant is hiding outside the band
   ```
3. For every genuinely comparable competitor (same platform + same data-type — see the
   "concept, not name" matching rule in `apify-store-research/SKILL.md`), record what's actually
   retrievable from the Algolia hit / Store listing:
   - Actor name and developer/seller.
   - Main functionality and target use case.
   - Store category/categories.
   - Pricing model (`currentPricingInfo.pricingModel`: `PAY_PER_EVENT`, `FLAT_PRICE_PER_MONTH`,
     `FREE`, `PRICE_PER_DATASET_ITEM`, etc.) and starting price/unit if visible.
   - Whether it's PPE or usage-based, and its chargeable events if PPE.
   - `stats.totalUsers`, `stats.totalRuns`, `actorReviewRating`, `actorReviewCount`,
     `bookmarkCount` — whichever fields the API actually returns; never estimate a number that
     wasn't in the response.
   - Main features / input-output shape (open the listing if the Algolia hit doesn't carry enough).
   - Competitive strengths and weaknesses relative to the actor you built.
4. Prioritize competitors with real activity (non-zero users/runs) and true functional overlap.
   Ignore unrelated actors that only share a category.
5. Conclude with:
   - Market saturation for this niche (how many distinct sellers, not just one actor's stats — reuse
     the "check seller count, not just one actor" verification from `apify-store-research/SKILL.md`).
   - Gaps or underserved angles your actor could fill.
   - Where your actor sits relative to what exists (cheaper, more complete fields, better coverage,
     first-mover, etc.).
6. If a required metric simply isn't available from the API/listing, write "unavailable" — never
   fabricate a number to fill the table.

## Phase 5 — Store category

1. Refresh the live category taxonomy before picking anything — it drifts:
   ```bash
   python api-search-actors.py --list-categories
   ```
2. Pick the single most accurate primary category based on what the actor actually does (data type +
   source), not the category with the most traffic.
3. Add a secondary category only if the actor genuinely spans two functions (e.g. a scraper that also
   does SEO analysis). Do not add categories just to be found more often.
4. Configuring the category itself happens on the actor's Store listing — check whether the installed
   `apify` CLI version exposes this (`apify actors --help` / check for a Store-metadata or `publish`
   subcommand) or whether it requires the Apify API (`PUT /v2/acts/{actorId}` with a `categories`
   field — verify the current shape against `docs.apify.com` before calling it, since API surfaces
   change). If neither CLI nor a verified API call is available in this environment, do not claim it
   was configured — state plainly: "Category must be set manually in Apify Console → Actor →
   Publication → Category."
5. Record the reasoning (why this category, why any secondary category) in the actor's own
   `README.md` or a short note in its folder — this repo has no separate per-actor status tracker, so
   the actor's own docs are the place this lives. If the actor came from a candidate row in
   `ACTOR_MARKET_RESEARCH.md` or `ACTOR_MARKET_RESEARCHER_NEW.md` at the repo root, mark that row as
   built there too.

## Phase 6 — Pricing model selection

Before picking a number, pick the *model*. Re-verify current Apify monetization rules against
`docs.apify.com` (they change) rather than relying on stale training knowledge — this repo has no
local doc for Apify's monetization program, so treat the live docs as the source of truth every time.

- **Pay-per-event (PPE)** — default candidate whenever the actor's value is the structured records it
  produces. For this repo's scraper actors (news articles, tenders, registry records, etc.), the
  primary paid event should almost always be `apify-default-dataset-item` (or a custom event only if
  it materially improves billing clarity — e.g. charging per successfully-extracted article but not
  per failed URL).
- **Pay-per-usage** — evaluate when compute/resource consumption (not the item count) is what actually
  varies run-to-run, e.g. an actor whose cost is dominated by residential-proxy-heavy pagination rather
  than by how many records come out.
- Never use Rental pricing on a newly created actor.
- Never invent a paid event beyond what's needed — one clear chargeable event beats several confusing
  ones. The user must be able to estimate their cost without ambiguity.
- Consider `apify-actor-start` as an additional/alternative event only when a fixed per-run cost is
  economically justified (e.g. heavy warmup/auth cost regardless of result count).

## Phase 7 — Competitive price calculation

Work through this sequence and show the arithmetic, don't skip to a number:

1. List the comparable prices gathered in Phase 4 (per 1,000 results / per run / per month —
   normalize units where possible).
2. Estimate this actor's own operating cost: Apify compute units per run, proxy tier (datacenter vs
   residential — see `.ai/CLAUDE.md` point 8 for when residential is required), and expected average
   run duration/result count based on what you observed during Phase 1-3 testing.
3. Estimate the value of one result to the target user (a news article, a tender listing, a registry
   record) relative to what comparable data is worth in the competitor set.
4. Determine a competitive price range from steps 1-3, then a recommended default price inside it.
5. Decide whether BRONZE/SILVER/GOLD discount tiers are worth configuring (only if it materially
   improves competitiveness/margin — see Phase 8).
6. Sanity-check margin after platform + proxy costs at the recommended price and expected volume.
7. Sanity-check the FREE tier isn't priced so high it discourages first-time evaluation.
8. Re-check the final number against the Phase 4 competitor range one more time before configuring
   anything.

Write the justification in this shape, filling in only what was actually retrieved:

> Competitor range: $X-$Y per 1,000 results (source: `<actor names>`). Estimated operating cost:
> $Z per 1,000 results (compute + proxy). Recommended price: $P per 1,000 results because `<reason
> tied to margin/positioning/data value>`.

Mark any input as "unavailable" rather than fabricating it. Never present a made-up statistic as if it
came from the Store.

## Phase 8 — Configure monetization

**Default to automating this via `apify api` — do not jump to "manual step" without trying it first.**
Confirmed working 2026-08-28: even an old/outdated `apify-cli` (1.7.1, no dedicated
monetization/pricing/category subcommand) exposes a generic `apify api` subcommand that makes an
authenticated request to the Apify API *using the CLI's own already-logged-in session* — you never
touch the raw API token, so this does not require extracting anything from the OS keyring or asking
the user for a token. Use it in this order:

1. **`apify api`** (preferred, almost always available): `apify api PUT actors/{actorId} -d '<json>'`
   (pipe the body via `-d -` reading stdin, or `-d '<inline JSON>'`). Set categories with
   `{"categories": ["LEAD_GENERATION", "BUSINESS"]}` — this one is simple, no quirks. Set pricing per
   the `pricingInfos` recipe below — it has two non-obvious quirks, follow them exactly:
   1. **`pricingInfos` is an append-only history, not a "set current state" field.** A `PUT` must send
      an array that starts with an *exact* copy of whatever the server currently has stored for that
      actor (fetch it fresh with `apify api GET actors/{actorId}` first — its own `createdAt` will
      differ from whatever you originally sent, so always re-GET rather than reusing your own copy),
      plus at most one new entry appended at the end. Sending a full replacement array (or a prefix
      that doesn't byte-match) throws `400 incorrect-pricing-modifier-prefix`.
   2. **A brand-new, never-priced actor's *first* `pricingInfos` entry must be flat
      (`eventPriceUsd`), not tiered.** Attempting `eventTieredPricingUsd` on the very first entry
      throws `400 schema-validation: "Charged event must contain price, title, and description"` even
      though the request body matches the documented/OpenAPI schema exactly (verified against
      `https://api.apify.com/v2/openapi.json`, not just the prose docs — the prose docs' example
      bodies can be paraphrased/wrong, fetch the raw OpenAPI JSON and grep its `components.schemas`
      for ground truth when a request is rejected and the error message doesn't clearly explain why).
      Workaround: PUT a flat entry first (`eventPriceUsd` = your FREE-tier price), GET it back, then
      PUT `existingArray + [tieredEntry]` as the second entry — the tiered entry needs `FREE`,
      `BRONZE`, `SILVER`, `GOLD`, `PLATINUM`, `DIAMOND` all present (mirror `GOLD`'s price into
      `PLATINUM`/`DIAMOND` if you don't want to price those tiers separately). Both `pricingInfos`
      entries also require `apifyMarginPercentage` (use `0.2`, matching what real Store listings show),
      `startedAt`, and `createdAt` (ISO 8601, current time) even though the field description says
      "set by the platform."
   3. **`startedAt` MUST be the actual current real-world timestamp (server UTC "now"), not a
      rounded/midnight value derived from "today's date."** Confirmed live (2026-08-28, luma-scraper):
      using `"2026-08-29T00:00:00.000Z"` for the first entry when the real server clock was still
      `2026-08-28T19:04Z` silently succeeded (it's a valid *future* timestamp) but then permanently
      blocked adding the tiered second entry — any `startedAt` after it is *also* in the future
      (`400 cannot-add-second-future-pricing-info`), while any `startedAt` before it violates
      ordering (`400 cannot-add-pricing-info-that-alters-past`). There is no valid second-entry
      timestamp until real time actually passes the first entry's `startedAt` — pricingInfos entries
      cannot be edited or deleted once submitted, only appended to. Get the real current UTC time
      first (e.g. shell `date -u +"%Y-%m-%dT%H:%M:%S.000Z"`, not a hand-typed date) and use that
      exact value — not midnight, not "today" — for `startedAt`/`createdAt` on every entry, especially
      the first one, so a same-session tiering follow-up isn't locked out for hours.
2. **Manual Console step** — only if `apify api` genuinely isn't available (e.g. CLI not installed/not
   logged in) or a specific mutation keeps failing after checking the raw OpenAPI schema. Do not claim
   monetization was configured; write the exact remaining action, e.g.: "Manual step required: Apify
   Console → Actor → Publication → Monetization → set Pay-per-event → add event
   `apify-default-dataset-item` → price $P → description `<...>`."

**Publishing to the Store (`isPublic: true`) is a separate mutation from categories/pricing, and is
subject to a platform-wide rate limit this session confirmed: 5 Actor publications per account per
day** (`429 daily-publication-limit-exceeded`). This is unrelated to whether `apify api` "works" —
categories and pricing can (and should) still be configured immediately via `apify api` even when the
publish quota is exhausted; only the final `isPublic: true` toggle needs to wait for the daily reset
and be spread across batches of ≤5/day if there are more than 5 actors pending publication. Tell the
user this exact number so they know it's a platform limit, not a missed step.

Whichever path is used, the configuration to reach (automated or documented as manual) is:
- Pricing model (PPE vs pay-per-usage, per Phase 6).
- Primary paid event name + description + price (per Phase 7).
- Discount tiers, only if Phase 7 step 5 concluded they're worth it, with progressively better unit
  economics at higher tiers.
- Store category/categories (per Phase 5).
- Any free-trial framing the Store supports, if relevant to the acquisition strategy from Phase 4/6.

Never configure a price that makes the actor unsustainable at expected volume, and never skip straight
to configuration without the Phase 7 arithmetic behind the number.

## Phase 9 — Final verification before marking an actor "completed"

Check every item below. Anything unchecked is either a real blocker (document it and move to the next
actor) or a manual step still owed (name it exactly):

- [ ] Actor builds successfully.
- [ ] Local execution succeeds (`python main.py latest N` and `python main.py "<url>"`).
- [ ] Apify execution succeeds (`apify call ...`).
- [ ] Dataset schema matches what's actually returned.
- [ ] Pagination / `latest` mode works correctly.
- [ ] Error handling and retry/backoff behave as expected.
- [ ] Proxy configuration is valid where the target requires residential.
- [ ] No login or private data is required.
- [ ] Implementation stayed Python + HTTP-only (no browser automation), per `adding-new-actor`.
- [ ] Store category assigned (or exact manual step documented).
- [ ] Pricing strategy is evidence-based per Phase 7 (or marked blocked/unavailable with reason).
- [ ] Monetization configured where automation permitted, otherwise exact manual step documented.
- [ ] The primary paid event is simple enough for a user to estimate cost from.
- [ ] Price is competitive against the Phase 4 competitor set.
- [ ] Price doesn't unnecessarily discourage first-time evaluation.
- [ ] No fabricated competitor claims, stats, or pricing anywhere in the writeup.

Then update the actor's own `README.md` (and the originating candidate row in
`ACTOR_MARKET_RESEARCH.md` / `ACTOR_MARKET_RESEARCHER_NEW.md`, if it came from one) to mark it built,
tested, pushed, and monetization-configured — or blocked, with the exact blocker. Only then move to
the next actor.

## End-of-session report

When wrapping up a build session that used this skill, summarize per actor: built / tested locally /
pushed / tested remotely / dataset verified / Store category / pricing model / recommended price /
monetization config status (configured vs manual-step-remaining, named exactly) / skipped-or-blocked
actors with the exact reason. Don't fold this into a generic "done" message — the point is that
someone could act on the manual-step list without re-deriving it.
