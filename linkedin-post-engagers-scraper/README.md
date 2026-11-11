# LinkedIn Post Engagers Scraper

Turn the people who engaged with a LinkedIn post into a lead list: name, headline, profile URL and — the part that actually matters — the comment they wrote.

Someone who took the trouble to comment on a post about your category has told you what they think about it. That is a warmer opening than any list of job titles, and it is the reason this actor keeps comment text as a first-class field instead of dropping it.

## What you get, and what LinkedIn holds back

Be clear about this before you buy, because it decides whether this actor is useful to you:

| | Published to logged-out visitors | Needs your `li_at` cookie |
|---|---|---|
| **Commenters** — name, profile URL, comment text, relative time | ✅ Yes | — |
| **Commenter headline** | ⚠️ Sometimes (roughly 1 in 8) | — |
| **Reaction and comment totals**, reaction-type mix | ✅ Yes | — |
| **Reactor identities** — who liked it | ❌ No | ✅ Yes |
| Employer, location, follower count per engager | via profile enrichment | — |

LinkedIn publishes roughly the **first 8–10 comments** on a post's public page. A post with 111 comments will give you about 8 commenter rows plus the true total in `postComments`. The gap is visible in every row, on purpose: `postReactions` and `postComments` are always there so you can see exactly how much LinkedIn withheld rather than assuming you got everything.

If you need the full comment thread and the reactor list, supply a session cookie.

## Input

```json
{
  "postUrls": [
    "https://www.linkedin.com/posts/satyanadella_example-activity-7505114604155322368-bJb4",
    "urn:li:activity:7505114604155322368",
    "7505114604155322368"
  ],
  "includeCommenters": true,
  "includeReactors": false,
  "enrichProfiles": false,
  "maxEngagers": 500,
  "minDelaySeconds": 2,
  "maxDelaySeconds": 8
}
```

Post permalinks, `/feed/update/` links, `urn:li:activity:` values and bare numeric activity ids are all accepted and normalised to the same thing.

## Using a session cookie

Reactor identities are the only thing here that needs one. To get it: sign in to LinkedIn in your browser, open DevTools → Application → Cookies → `www.linkedin.com`, copy the **value** of `li_at`, and paste it into `sessionCookie`.

This actor never asks for your password and never signs in on your behalf. It sends the cookie you pasted, in that run, and nowhere else.

**The honest risk.** Scraping while signed in is against LinkedIn's User Agreement, and LinkedIn does restrict accounts for it. Three things reduce the odds, and this actor does or exposes all three:

- **Use a residential proxy in your own country.** LinkedIn weighs the exit IP against where your account normally signs in. An Apify datacenter IP is exactly the mismatch that gets a session flagged. The actor warns you in the log if you supply a cookie without a proxy.
- **Keep the caps low.** `maxEngagers` defaults to 500 for a reason. Long, greedy runs are what abuse scoring reacts to.
- **Leave the delays alone.** The 2–8 second randomised gap between page loads is not padding.

Use an account you would not mind losing.

## Rate gating, and why the delays exist

LinkedIn answers bursts with **HTTP 999** and a ~1.5 KB stub page. Measured on the guest surface: three back-to-back requests tripped it, and the same URLs answered 200 again after a four-second pause. It is per-IP and per-burst, not per-URL, and it is **not** a TLS fingerprint gate — a sweep of five browser fingerprints all returned 200 on the same page.

So the fix is patience, not evasion. The actor sleeps a random 2–8 seconds between page loads, backs off exponentially when it does meet the gate, and rotates among five browser fingerprints. If you see rate-gate warnings in the log, raise both delay bounds before you reach for anything else.

## Output

One `ENGAGER` row per person, one `POST` row per post, plus `NOTICE` rows where LinkedIn published nothing (comments disabled, very new post) and `ERROR` rows on failure. An empty result therefore always comes with a reason attached.

Names are split into `firstName` / `lastName` with pronouns, emoji hiring frames and credential suffixes (PhD, MBA, CFA) stripped — a mail merge that greets someone as "Hi Dr, PhD" is worse than no personalisation. Profile URLs have tracking parameters removed and country subdomains (`in.linkedin.com`, `id.linkedin.com`) folded onto `www`, so your CRM de-duplicates correctly.

```json
{
  "recordType": "ENGAGER",
  "fullName": "Marc Beierschoder",
  "firstName": "Marc",
  "lastName": "Beierschoder",
  "headline": "Most companies scale the wrong things",
  "profileUrl": "https://www.linkedin.com/in/marc-beierschoder",
  "engagementType": "COMMENT",
  "commentText": "One thing I'd add: observability tells us what the agent did...",
  "commentedAgo": "6d",
  "postUrl": "https://www.linkedin.com/posts/satyanadella_...",
  "postReactions": 836,
  "postComments": 111
}
```

## No email addresses

This actor does not guess email addresses. A fabricated `first.last@company.com` that bounces costs you your sending domain's reputation, which is a far more expensive mistake than a missing column. You get the name and the employer; put those through a verification tool that actually checks.

## Before you use this on people

The rows are real people, and in the EU, UK and similar jurisdictions they carry data-protection rights even though the data is public. Legitimate interest is a defensible basis for B2B outreach; it is not a blank cheque. Say where you got the data when you make contact, honour opt-outs, and do not mix this into a consumer marketing list. That is your obligation as the data controller, not the actor's.

## Related actors

- **LinkedIn Top Voice & Competitor Activity Monitor** — the content strategy behind the posts, no cookie needed.
- **LinkedIn Smart Job Description & Recruiter Extractor** — hiring signals, fully public.
