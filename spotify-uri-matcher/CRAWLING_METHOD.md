# How this actor gets its data

Plain HTTP against Spotify's own public web surfaces. No browser, no Spotify
account, no developer application, no API key.

---

## 1. The anonymous token

Every Spotify embed page carries a `__NEXT_DATA__` JSON blob holding an access
token marked `"isAnonymous": true`, served to anybody who loads the page:

```
GET https://open.spotify.com/embed/track/<any id>
 -> props.pageProps.state.settings.session.accessToken
```

That is the only credential used. Tokens last about an hour; a `401` mid-run
triggers one silent refresh. The web player's *other* token endpoint
(`/api/token`) is signed and is deliberately not touched.

---

## 2. Search through the web player gateway, not the Web API

This is the design decision that makes a *bulk* matcher possible.

`api.spotify.com/v1/search` accepts the anonymous token, and it is the obvious
place to search. It is also **the wrong place**, because its anonymous
allowance is tiny and the penalty is enormous. Measured on 2026-09-20: a few
dozen requests, then `429 QUOTA_EXCEEDED` with `Retry-After: 73444` — about
twenty hours — and the ban follows the **IP**, not the token, so minting a
fresh token does nothing. A five-hundred-line list would die on line forty and
take the address down with it for the rest of the day.

So searching goes through `api-partner.spotify.com/pathfinder/v1/query`
instead, using the `searchSuggestions` persisted query — the operation behind
the web player's own search box. It accepts the same anonymous token with no
`client-token` header, and has shown no comparable ceiling.

Persisted queries are addressed by an operation name plus the SHA-256 hash of
the query text, declared in the web player's JavaScript bundle. The hashes are
pinned in `src/constants.py`; when Spotify rotates them the gateway answers
HTTP **200** with `{"errors":[{"message":"PersistedQueryNotFound"}]}`, and the
client re-harvests them from the live bundle once and retries.

One quirk worth knowing: `searchSuggestions` **ignores every paging variable**.
`limit`, `offset` and the rest are accepted without error and change nothing —
it always returns the same thirty mixed-type hits. There is no second page to
ask for, so the scoring works with those thirty.

---

## 3. Scoring, and why it exists

Spotify returns something for any input. `"asdkjh qweoiu zxcvbn"` comes back
with a real track. Taking the first hit therefore yields a matcher with a
perfect apparent hit rate and no way to tell a right answer from a wrong one.

Each of the thirty candidates is scored instead:

- **Title similarity** on a folded form — lowercased, accents stripped,
  punctuation removed — computed both with and without featured-artist and
  version suffixes, keeping the better of the two.
- **Artist similarity** against every credited artist. When no artist was
  supplied, the fallback is whether a candidate artist's name appears anywhere
  in the original line.
- **Duration**, when given: within two seconds raises the score, more than
  thirty seconds out lowers it.

Both readings of the line are scored — `Title - Artist` and `Artist - Title` —
because neither can be identified from the text, and both are common in
exported setlists.

**Containment needs two guards.** A short title inside a longer one usually
means the same recording with a suffix (`sial` / `sial remix version`), so
containment lifts the score. Without guards that rescues nonsense: `zzz` is a
substring of `zzzz nonexistent song xyzq 12345`, which scored a bogus 0.88 in
testing. Containment is therefore checked on whole *words*, and the shorter
side must be at least half the length of the longer.

**A title-only match is capped below `exact`**, because many recordings share
a title and nothing in the input distinguishes them.

---

## 4. Traps this actor already handles

**An empty result set is not how a bad query fails.** It fails by returning a
confident-looking wrong answer, which is why the threshold, not the result
count, decides whether something matched.

**ISRC queries silently return garbage.** The gateway search treats an ISRC as
free text and answers with unrelated tracks — it does not error. ISRC lookup
only works through the Web API's `isrc:` filter, which is the rate-limited
endpoint above, so it is not offered rather than offered and broken.

**Inputs that are already Spotify references cost nothing.** They are detected
and passed straight through instead of being searched for.

---

## 5. Proxy

Off by default. The gateway has no WAF and no IP gate, and has shown no
request ceiling, so a default-on proxy would bill for nothing.

---

## 6. Rate and courtesy

One request per line, spaced out, with exponential backoff on `429` and `5xx`
and a small retry budget before a line is recorded as an error rather than
hammered. Only public, unauthenticated endpoints are read.
