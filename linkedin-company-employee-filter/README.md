# LinkedIn Company Employee Role Filter

Account-based marketing runs on one question: *who inside this company can say yes?* This actor answers it — scrape a target company's people and keep only the titles you care about: CMO, Marketing Director, Head of HR.

It is the cheap alternative to a Sales Navigator seat for the narrow job of finding decision makers at a named list of accounts.

## Read this before you buy

**The employee list requires your own `li_at` session cookie.** LinkedIn publishes no employee directory to logged-out visitors at all: `/company/{slug}/people/` redirects to the login wall and the private API answers HTTP 403. Verified 2026-09-20. There is no workaround, in this actor or any other.

**Without a cookie the run still succeeds** and returns each company's public record — name, follower count, headcount on LinkedIn, website, **web domain** and LinkedIn's internal company id — plus a `NOTICE` row stating plainly why no people came back. That is genuinely useful for account research on its own, and it means an empty people list always arrives with a reason attached rather than looking like a bug.

## Getting your cookie

Sign in to LinkedIn in your browser → DevTools → Application → Cookies → `www.linkedin.com` → copy the **value** of `li_at` → paste into `sessionCookie`.

This actor never asks for your password and never signs in on your behalf.

**The honest risk.** Scraping while signed in breaches LinkedIn's User Agreement and accounts do get restricted for it. Three mitigations, all of which this actor does or exposes:

- **Residential proxy in your own country** — the default here. LinkedIn weighs the exit IP against where your account normally signs in; an Apify datacenter IP is exactly the mismatch that flags a session. The actor warns in the log if you turn it off.
- **Low caps** — `maxEmployees` defaults to 500, `maxEmployeesPerCompany` to 100. Long, greedy runs are what abuse scoring reacts to.
- **The 3–8 second randomised delay** — with a cookie in play it keeps the run looking like a person, not a script.

Use an account you would not mind losing.

## Role matching, and why it is whole-word

```json
{
  "companyUrls": ["anthropicresearch", "openai"],
  "roleKeywords": ["CMO", "Marketing Director", "Head of Marketing"],
  "excludeKeywords": ["Assistant", "Intern", "Former"],
  "sessionCookie": "AQEDAT..."
}
```

Keywords are matched as **whole words** against the headline. That distinction matters more than it looks: a substring search for `HR` pulls in every **Chris** and every **Thread**, and a substring search for `CEO` matches nothing useful in `CEO's office`. Multi-word entries like `Marketing Director` match as a phrase. `excludeKeywords` is applied after, on the same whole-word basis.

**One keyword is cheaper than several.** With exactly one, it is handed to LinkedIn's own search and narrows results server-side, so fewer pages are fetched. With several, the search runs unfiltered and matching happens locally — because LinkedIn treats multiple search terms as AND and would return almost nothing.

`matchedKeyword` on each row tells you which term the person matched, and is null when no include filter was set — so you can always tell "matched everything" from "matched nothing in particular".

## The company id

LinkedIn's internal numeric company id is the key the people search facets on, and it is never rendered on the page. This actor lifts it out of the "see all employees" call-to-action link, where it leaks double-percent-encoded. You get it on every `COMPANY` row as `companyId`, which is useful in its own right if you build anything else against LinkedIn.

If a page does not carry one — some showcase and redirected pages do not — the run writes a `company_id_not_found` notice rather than silently skipping the company.

## Output

`COMPANY` rows always; `EMPLOYEE` rows when a cookie was supplied.

```json
{
  "recordType": "COMPANY",
  "companyName": "Anthropic",
  "companyId": "74126343",
  "website": "https://www.anthropic.com/",
  "companyDomain": "anthropic.com",
  "followers": 4913113,
  "employeeCount": 5979
}
```

`employeeCount` is a useful sanity check: it tells you how large the organisation is on LinkedIn, so you can see what fraction of it any single run could ever reach.

## No email addresses

`companyDomain` gives you the employer's web domain. This actor does **not** invent `first.last@domain.com`. A guessed address that bounces costs you your sending domain's reputation, which is far more expensive than a missing column — put the name and domain through a verification tool that actually checks.

## Universities do not work here

LinkedIn blocks `/school/` pages entirely for logged-out visitors (HTTP 999 on every path, including the `/company/` alias that redirects there). Use the **LinkedIn University Alumni Career Mapper** for schools.

## Before you use this on people

These are real people, and in the EU, UK and similar jurisdictions they carry data-protection rights even though their profiles are public. Legitimate interest is a defensible basis for B2B outreach; it is not a blank cheque. Say where you got the data when you make contact, honour opt-outs, and keep it out of consumer marketing lists. That is your obligation as the data controller, not the actor's.

## Related actors

- **LinkedIn Event Attendees Extractor** — an audience that already self-selected on your topic.
- **LinkedIn Post Engagers Scraper** — warm leads from a competitor's post, mostly without a cookie.
- **LinkedIn Smart Job Description & Recruiter Extractor** — which accounts are hiring, and for what.
