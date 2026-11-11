# LinkedIn University Alumni Career Mapper

Where do a university's graduates actually end up? This actor reads a school's alumni and maps them — employer, role, location, graduation year — then aggregates that into the picture a tracer study is trying to produce: top employers, top destinations, top roles.

It is the kind of talent-mobility data that is close to impossible to assemble by hand and that universities routinely pay survey firms for.

## Read this before you buy

**This actor requires your own `li_at` session cookie, and LinkedIn is stricter about school pages than about anything else.**

`/school/` answers **HTTP 999** to logged-out visitors on every path tried — including the `/company/` alias that redirects there — and unlike LinkedIn's ordinary rate gate, **it does not clear with delays**. Verified 2026-09-20 across repeated attempts with multi-second pauses, in the same session where company and profile pages were answering 200 normally.

So unlike this portfolio's company and profile actors, there is **no public school record to fall back on**. Without a cookie there is nothing to read at all. The run still finishes successfully and writes a `cookie_required` notice per school explaining exactly this, rather than failing or handing you a silent empty dataset.

## Treat every result as a sample, not a census

LinkedIn's people search stops serving results past roughly **1,000**, and a large university has hundreds of thousands of alumni. No scraper gets a complete alumni list — this one does not pretend to.

What that means in practice:

- `alumniAnalysed` on every `SUMMARY` row tells you the sample size the rankings are built on. Read the rankings as "among the alumni LinkedIn surfaced", never as "among all alumni".
- **Use `filterKeywords`.** Narrowing server-side — `"software engineer"`, `"Jakarta"`, `"product manager"` — is both far cheaper and far more meaningful than sampling a thousand arbitrary graduates. For a large school it is the only way to get a slice you can reason about.
- Results also depend on what your account is allowed to see. An account with more network reach surfaces more.

## Input

```json
{
  "schoolUrls": ["stanford-university", "https://www.linkedin.com/school/universitas-indonesia/"],
  "filterKeywords": "software engineer",
  "sessionCookie": "AQEDAT...",
  "maxAlumniPerSchool": 200
}
```

A bare slug is treated as a `/school/` page, not a `/company/` one.

## Output

One `ALUMNUS` row per graduate, plus a `SUMMARY` row per school:

```json
{
  "recordType": "SUMMARY",
  "schoolName": "Stanford University",
  "alumniAnalysed": 200,
  "distinctEmployers": 84,
  "withEmployerPct": 78.5,
  "topEmployers": [
    { "employer": "Google", "alumni": 21 },
    { "employer": "Meta", "alumni": 14 }
  ],
  "topLocations": [{ "location": "San Francisco Bay Area", "alumni": 96 }],
  "graduationYearRange": [1994, 2024]
}
```

**`withEmployerPct` is the field that tells you how much to trust the rest.** `currentTitle` and `currentCompany` are split out of the person's headline on "at" and its common localisations — which works well for `"Senior Engineer at Acme"` and not at all for a headline that is a slogan. When `withEmployerPct` is low, the employer ranking is built on a thin slice and should be read that way. The raw `headline` is kept on every row so you can always check the split yourself.

`graduationYear` is likewise best-effort: LinkedIn does not return a structured graduation year in search results, so it is the earliest plausible year found in the text attached to the result, and it is often null.

These caveats are in the output schema too, not just this README — the numbers carry their own limitations.

## Getting your cookie

Sign in to LinkedIn in your browser → DevTools → Application → Cookies → `www.linkedin.com` → copy the **value** of `li_at` → paste into `sessionCookie`.

This actor never asks for your password and never signs in on your behalf.

**The honest risk.** Scraping while signed in breaches LinkedIn's User Agreement and accounts do get restricted for it. Mitigations, all of which this actor does or exposes:

- **Residential proxy in your own country** — the default here. LinkedIn weighs the exit IP against where your account normally signs in; a datacenter IP is the mismatch that flags a session.
- **Low caps** — `maxAlumni` defaults to 1,000, `maxAlumniPerSchool` to 200.
- **The 3–8 second randomised delay**, which with a cookie in play is what keeps the run looking like a person rather than a script.

Use an account you would not mind losing.

## Who this is for

- **Universities** — tracer studies and employability reporting without commissioning a survey.
- **Headhunters** — which firms hire from which programmes, and where those people sit now.
- **Market researchers** — talent flows between companies, regions and sectors.

## Before you use this on people

Graduates are real people, and in the EU, UK and similar jurisdictions they carry data-protection rights even though their profiles are public. Aggregate reporting (top employers, top locations) is a much easier case to defend than contacting individuals. If you do reach out, say where you got the data, honour opt-outs, and keep it out of consumer marketing lists. That is your obligation as the data controller, not the actor's.

## Related actors

- **LinkedIn Company Employee Role Filter** — the same people search, faceted to an employer instead of a school.
- **LinkedIn Smart Job Description & Recruiter Extractor** — what employers are actually hiring for, fully public.
