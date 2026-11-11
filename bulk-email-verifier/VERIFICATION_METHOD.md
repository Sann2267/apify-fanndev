# Verification method

What the actor actually does, in the order it does it, and which reply codes map to which verdict. Written so a surprising row can be traced back to the rule that produced it.

## 1. Parse (`src/syntax.py`)

Accepts `jane@acme.com`, `<jane@acme.com>` and `Jane Doe <jane@acme.com>`. Rejects quoted local parts, comments and IP-literal domains — legal in RFC 5322, rejected by mailbox providers in practice, so accepting them would produce addresses that validate and then bounce.

Limits enforced: local part ≤ 64 (RFC 5321 §4.5.3.1.1), whole address ≤ 254.

**Normalisation.** Gmail and Googlemail ignore dots; twelve providers ignore everything after a `+`. Both are folded into `normalizedEmail`, and `isAlias` records that folding happened. This is what makes duplicate removal correct rather than approximate.

**Typo repair.** Levenshtein against ~30 major providers with an early-abandon cutoff. The budget is **1 edit when either domain is ≤ 8 characters, 2 otherwise** — without that guard `acme.com` resolves to `me.com` at distance 2, which is a worse outcome than staying silent.

## 2. DNS (`src/dnsmx.py`)

Per domain, once per run, with one in-flight lookup per domain (a list sorted by domain otherwise fires hundreds of identical queries before the first answer lands).

| Outcome | `domainStatus` | Verdict contribution |
|---|---|---|
| MX records returned | `ok` | proceed to SMTP |
| Only `.` as exchange (RFC 7505 null MX) | `no_mx` | `undeliverable` |
| `NoAnswer` on MX, but A/AAAA exists | `ok` + `implicitMx: true` | proceed (RFC 5321 implicit MX) |
| `NoAnswer` on MX, no A/AAAA | `no_mx` | `undeliverable` |
| `NXDOMAIN` | `nxdomain` | `undeliverable` |
| Timeout / SERVFAIL | `dns_timeout` / `dns_error` | `unknown` — a fact about the run, not the address |

The implicit-A fallback matters: plenty of small self-hosted domains publish no MX, and skipping it marks real mailboxes dead.

## 3. SMTP (`src/smtpcheck.py`)

```
> (connect to lowest-preference MX, port 25)
< 220 mx.example.com ESMTP
> EHLO <heloHostname>           (falls back to HELO on 4xx/5xx)
< 250-mx.example.com ...
> MAIL FROM:<mailFromAddress>
< 250 2.1.0 Ok
> RCPT TO:<address>
< 250 2.1.5 Ok                  <- the answer
> QUIT
```

`DATA` is never sent. Nothing is delivered to the address being checked.

### Reply code mapping

| Codes | `smtpDeliverable` | Why |
|---|---|---|
| 250, 251 | `true` | recipient accepted |
| 550, 551, 553, 554, other 5xx | `false` | recipient rejected |
| 421, 450, 451, 452, 552 | `null` | greylisting, throttling, service closing, mailbox full — "ask later", not "does not exist" |
| no reply / timeout / connection closed | `null` | nothing was established |

The asymmetry is deliberate: a false `undeliverable` deletes a real customer, while a false `unknown` costs one re-run.

### Catch-all detection

Only after an acceptance, in the same session: `RCPT TO:<16-random-chars@domain>`. Accepted too → the domain takes everything → the original acceptance proved nothing → `risky` / `catch_all`. Cached per domain, so one extra command covers every address on it.

### Politeness and rate limits

One conversation at a time per domain, enforced by a per-domain lock. `concurrency` therefore controls how many *different* domains are in flight, never how hard one server is hit. This is not only etiquette: a server that decides it is being scanned starts answering 550 to everything, which is indistinguishable from "mailbox does not exist" — the exact failure this actor exists to avoid.

### Port 25

Tested once per run against a known-good MX before the list is processed, capped at 8 seconds. If it fails, `smtpPortReachable: false` goes into the summary, every SMTP check is skipped with `smtpStage: skipped_port_blocked`, and the affected rows land on `unknown`. Without that one probe, every address on a blocked host would pay a full timeout to learn the same thing.

**Measured on the Apify platform, 2026-09-22 (build 0.0.2 and 0.0.3):**

| Route | `smtpRoute` | Result |
|---|---|---|
| Direct `open_connection(mx, 25)` | `direct` | `TimeoutError` |
| Apify proxy `CONNECT mx:25` | `proxy-connect` | `TimeoutError` |

The proxy path was added specifically to test whether a CONNECT tunnel could reach port 25 where a direct socket cannot. It cannot — the tunnel is refused the same way. On Apify, steps 1–5 are the whole product; step 6 needs a host that permits port 25 egress.

## 4. Verdict (`src/scoring.py`)

Precedence, highest first:

1. Invalid syntax → `undeliverable` (score 0)
2. `nxdomain` / `no_mx` → `undeliverable` (0–2)
3. DNS unavailable → `unknown` (50)
4. SMTP rejection → `undeliverable` (0)
5. Disposable (domain or MX host) → `risky` (15)
6. SMTP acceptance + catch-all → `risky` (55)
7. SMTP acceptance + role mailbox → `risky` (70), configurable
8. SMTP acceptance → `deliverable` (98)
9. No SMTP answer + typo-shaped domain → `risky` (30)
10. No SMTP answer + role mailbox → `risky` (45)
11. No SMTP answer, MX ok → `unknown` (65, `mx_only`)

An SMTP rejection outranks the disposable and role classifications because the server that owns the mailbox has spoken. Everything below rule 8 rests on DNS plus classification alone, which is why none of it is ever reported as `deliverable`.

## Known blind spots

- **Yahoo, AOL and some Microsoft tenants** accept every recipient. Catch-all detection turns that into `risky` rather than a confident wrong answer, but it cannot recover the real answer.
- **Aggressive greylisting** can return 450 for every first contact from an unfamiliar IP. Those rows are `unknown`; a second run from the same IP usually resolves them.
- **The disposable domain list is a curated head.** MX-host markers catch the rotating-alias long tail, but a brand-new provider can pass as an ordinary domain.
- **A hostile server can lie in both directions.** Verification lowers bounce rate; it does not make it zero.
