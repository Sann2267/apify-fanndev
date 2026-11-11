# LinkedIn Event Attendees Extractor

People who registered for an event about your category have already raised their hand on the topic. This actor turns a LinkedIn event URL into that list: names, headlines and profile links, ready for a connection request or a cold email that can honestly open with "I saw you signed up for…".

## Read this before you buy

**This actor requires your own `li_at` session cookie.** That is not a design preference. LinkedIn redirects `/events/{id}` straight to the login wall for anonymous visitors — there is no guest view of an event at all, let alone its attendees. Verified 2026-09-20.

**And a cookie is not always enough.** Two limits are LinkedIn's, and no scraper gets past them:

1. **Attendee lists are permissioned.** LinkedIn serves the roster only to accounts it decides may see it — typically the organiser, and attendees of events whose organiser left the list visible. A cookie for an account with no relationship to the event will often read the event fine and return **no attendees**.
2. **Many events publish a count but withhold the names.** You will see `eventAttendeeCount: 340` and get zero `ATTENDEE` rows.

When either happens, this actor writes an `attendee_list_withheld` notice explaining which case it hit, reports the count it *did* get, and **exits successfully**. It does not fail, and it does not hand you a silent empty dataset that looks like a bug.

If your use case is "scrape any event I can find a link to", this will disappoint you more often than not. If it is "extract the roster from events I organise or attend", it does exactly that.

## Getting your cookie

Sign in to LinkedIn in your browser → DevTools → Application → Cookies → `www.linkedin.com` → copy the **value** of `li_at` → paste into `sessionCookie`.

This actor never asks for your password and never signs in on your behalf. It sends the cookie you pasted, in that run, and nowhere else.

**The honest risk.** Scraping while signed in breaches LinkedIn's User Agreement, and LinkedIn does restrict accounts for it. Three things reduce the odds, and this actor does or exposes all three:

- **Use a residential proxy in your own country.** This is the default here, and it matters: LinkedIn weighs the exit IP against where your account normally signs in, and an Apify datacenter IP is exactly the mismatch that flags a session. The actor warns in the log if you turn the proxy off.
- **Keep the caps low.** `maxAttendees` defaults to 1,000 and `maxAttendeesPerEvent` to 200. Long, greedy runs are what abuse scoring reacts to.
- **Leave the delays alone.** The 3–8 second randomised gap is not padding — with a cookie in play it is also what keeps the run looking like a person rather than a script.

Use an account you would not mind losing.

## Input

```json
{
  "eventUrls": [
    "https://www.linkedin.com/events/my-webinar-7178068349686366208/",
    "7178068349686366208"
  ],
  "sessionCookie": "AQEDAT...",
  "maxAttendeesPerEvent": 200,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

Full event links and bare 19-digit event ids both work.

## Output

One `EVENT` row per event — name, description, organiser, start time and the attendee count LinkedIn reports — and one `ATTENDEE` row per person.

```json
{
  "recordType": "ATTENDEE",
  "fullName": "Jane Doe",
  "firstName": "Jane",
  "lastName": "Doe",
  "headline": "Head of Demand Generation at Acme",
  "profileUrl": "https://www.linkedin.com/in/janedoe",
  "location": "Berlin, Germany",
  "attendanceStatus": "REGISTERED",
  "eventName": "Scaling B2B Pipeline in 2026",
  "eventAttendeeCount": 340
}
```

`eventAttendeeCount` sits on every attendee row on purpose: compare it against your row count and you can always see how much of the roster LinkedIn actually gave you, rather than assuming you got all of it.

Names are split into `firstName` / `lastName` with pronouns, emoji hiring frames and credential suffixes (PhD, MBA, CFA) stripped — a mail merge that greets someone as "Hi Dr, PhD" is worse than no personalisation. Profile URLs have tracking parameters removed and country subdomains folded onto `www`, so your CRM de-duplicates correctly.

## No email addresses

This actor does not guess email addresses. A fabricated `first.last@company.com` that bounces costs you your sending domain's reputation, which is a far more expensive mistake than a missing column. Take the name and headline and put them through a verification tool that actually checks.

## Before you use this on people

These are real people, and in the EU, UK and similar jurisdictions they carry data-protection rights even though they registered for a public event. Legitimate interest is a defensible basis for B2B outreach; it is not a blank cheque. Say where you got the data when you make contact, honour opt-outs, and do not mix event attendees into a consumer marketing list. That is your obligation as the data controller, not the actor's.

## Related actors

- **LinkedIn Post Engagers Scraper** — commenters on a post, no cookie needed for most of it.
- **LinkedIn Company Employee Role Filter** — decision makers inside a target account.
