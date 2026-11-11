# Bulk Email Verifier & Validator

Give it an email list. Get back one verdict per address — **deliverable, undeliverable, risky or unknown** — plus the exact reason, the MX host and the mail server's own words.

No API key to bring, no third-party verification service in the middle — syntax, DNS and the SMTP conversation all happen inside the run.

**On the Apify platform, read ["Port 25, stated plainly"](#port-25-stated-plainly) first:** outbound port 25 is blocked there, so hosted runs deliver everything except the live-mailbox check.

## Four statuses, and why `unknown` exists

Most verifiers report three outcomes and quietly file everything they could not establish under "valid" or "invalid". That is where a bounced campaign comes from. This one keeps a fourth:

| Status | What it means | What to do |
|---|---|---|
| `deliverable` | The mail server accepted the recipient and the domain does **not** accept everything | Send |
| `undeliverable` | Bad syntax, dead domain, no MX, or the server rejected the recipient | Remove |
| `risky` | It may accept and still hurt you: catch-all domain, disposable provider, role mailbox, typo-shaped domain | Your call — the reason says which |
| `unknown` | Greylisting, timeout, or SMTP was not available on this run | Re-run later; do not treat as valid |

`safeToSend` collapses this to one boolean, and it answers `false` for both `risky` and `unknown` on purpose.

## What proves each verdict

```json
{
  "email": "someone@example.com",
  "status": "undeliverable",
  "subStatus": "mailbox_not_found",
  "score": 0,
  "smtpCode": 550,
  "smtpMessage": "550 5.1.1 The email account that you tried to reach does not exist.",
  "mxHost": "aspmx.l.google.com",
  "reason": "The mail server rejected this recipient (SMTP 550)."
}
```

The server's reply is kept verbatim, so a surprising verdict can be audited in ten seconds instead of re-run through a second tool to see whether you believe the first one.

## The checks, cheapest first

1. **Syntax** — RFC-shaped parsing, length limits, the malformed shapes that survive CRM exports.
2. **Normalisation** — lowercased domain, plus-aliases stripped, Gmail dots removed. Two rows with the same `normalizedEmail` are one mailbox, not two sends.
3. **Classification** — role mailbox (`info@`, `sales@`), free provider, disposable provider (by domain *and* by the MX host behind it, which catches rotating alias domains a static list misses).
4. **Typo repair** — `gmial.com` → `gmail.com`. The edit budget scales with domain length, so `acme.com` is never "corrected" to `me.com`.
5. **MX lookup** — cached per domain for the run, with the RFC 5321 implicit-A fallback so small self-hosted domains are not written off. RFC 7505 null MX is read as "sends no mail".
6. **SMTP probe** — `EHLO` → `MAIL FROM` → `RCPT TO`, then `QUIT`. **`DATA` is never sent, so no mail is generated for the address being checked.**
7. **Catch-all detection** — after an acceptance, a random address on the same domain is offered. If that is accepted too, acceptance proved nothing, and the verdict drops to `risky`.

## Port 25, stated plainly

Mailbox-level verification needs outbound TCP 25, and **many hosts block it — including the Apify platform**. Measured on 2026-09-22, both routes time out:

| Route | Result |
|---|---|
| Direct connection from the run | blocked |
| Apify proxy, CONNECT tunnel to port 25 | blocked |

So on Apify this actor delivers checks 1–5 — syntax, normalisation, classification, typo repair and MX — and reports `unknown` rather than inventing a mailbox-level answer. Step 6 works when you run the image somewhere port 25 is open (your own VPS or container host), and the run says which world it was in:

```json
{ "recordType": "RUN_SUMMARY", "smtpRoute": "direct", "smtpPortReachable": false, "smtpEgressDetail": "TimeoutError" }
```

**Read `smtpPortReachable` before trusting any `unknown` in the dataset.** False means the limit was the network, not the address.

Where port 25 is open, two inputs measurably improve how often servers answer honestly: set `heloHostname` and `mailFromAddress` to a domain you actually control, with matching forward and reverse DNS.

## What you get per address

| Field | What it tells you |
|---|---|
| `status` / `subStatus` / `score` / `safeToSend` | The verdict, the machine-readable reason, 0–100 confidence, the one boolean |
| `reason` | One sentence in the terms a sender cares about |
| `normalizedEmail` / `isAlias` | The canonical mailbox behind plus-addressing and Gmail dots |
| `isRoleAccount` / `isFreeProvider` / `isDisposable` | List composition, independent of deliverability |
| `hasTypo` / `suggestedEmail` | The repaired address when a domain looks like a near-miss |
| `domainStatus` / `mxHost` / `mxRecords` / `implicitMx` | What DNS said |
| `smtpCode` / `smtpMessage` / `smtpStage` / `isCatchAll` | What the mail server said, and where the conversation ended |

One `RUN_SUMMARY` record closes every run: status breakdown, reason breakdown, deliverable rate, duplicates removed, domains resolved, and the port 25 verdict.

## Limits worth knowing

- **Yahoo, AOL and some Microsoft tenants accept every recipient at RCPT TO.** Catch-all detection flags this as `risky` rather than reporting a confident `deliverable` that is not.
- **Greylisting returns 450/451.** That is `unknown`, never `undeliverable` — re-run those rows later rather than deleting them.
- **The disposable list is a curated head, not an exhaustive one.** MX-host matching covers much of the long tail; a brand-new throwaway domain can still slip through as `unknown` or `deliverable`.
- **On Apify, `deliverable` is unreachable** — port 25 is blocked, so the best available verdict for a live mailbox is `unknown` with a good MX. Everything that removes addresses (bad syntax, dead domain, no MX, disposable, typo) still works exactly as documented.
- **One SMTP conversation at a time per domain.** A list of 10k addresses on one domain is slower than 10k addresses across 3k domains, on purpose: hammering one server turns honest answers into blanket rejections.
- Verification is for list hygiene on addresses you already hold. It is not an address-discovery tool and there is no mode that finds or guesses addresses.

## Failures are data

A DNS timeout, a closed connection or a refused probe never fails the run. Each becomes a row with its own `subStatus` and `smtpStage`, because "we could not tell, and here is why" is a fact the buyer needs — and a run that dies on row 40,000 of 50,000 wastes everything before it.

## Cost

One DNS lookup per **domain** (not per address) and at most one SMTP session per address. A 50k list of ~3k domains costs 3k lookups, not 50k. Syntax failures and dead domains never reach the network at all.

## Output shape

Dataset rows follow the repo envelope: `_input`, `_source` (`mx+smtp` or `mx-only`), `_scrapedAt`, `recordType` (`EMAIL` / `RUN_SUMMARY`). Optional JSON, NDJSON, CSV and XLSX exports land in the key-value store with the verdict columns first, ready to hand to an ESP.

## Development

```bash
python test_local.py          # syntax + scoring assertions, then MX-only over a sample list
python test_local.py --smtp   # same, plus the mailbox probe and the port 25 verdict
```

See `VERIFICATION_METHOD.md` for the protocol details and the reply codes behind each verdict.
