# `.ai/` — AI Context & Project Memory for Scraping Boilerplate

> **Purpose:** Curated knowledge base of *proven* scraping techniques, anti-bot bypasses, and architecture patterns extracted from 19 production projects (~85+ actors). Drop this folder into any new scraping project — AI agents read it on session start and gain instant access to battle-tested patterns instead of rediscovering them.

## How an AI agent should use this folder

1. **Read `CLAUDE.md` first.** It's the top-level instruction file every agent must process before touching code.
2. **Consult `skills/` for HOW** — concrete extraction & request techniques that have been verified to work.
3. **Consult `anti-bot/` for WAFs** — one file per WAF vendor with diagnosis + bypass + caveats.
4. **Consult `playbooks/` for workflows** — step-by-step procedures (new scraper bootstrap, WAF triage, reverse-engineering, Apify deploy).
5. **Consult `stacks/` for boilerplate** — canonical project templates (Python Apify actor, Beanstalk+Kafka pipeline, Node.js crypto sidecar).
6. **Consult `conventions/` for output shape** — dataset envelope, error handling rules.
7. **Consult `lessons-learned.md` for "don't bother"** — patterns we tried that failed (Shopee bytecode VM, TikTok PO Token JS-only, etc.).

## Top-level structure

```
.ai/
├── README.md                       # this file
├── CLAUDE.md                       # main agent instructions (read first)
├── skills/                         # proven reusable techniques
├── anti-bot/                       # WAF-specific bypass playbooks
├── playbooks/                      # step-by-step task workflows
├── stacks/                         # boilerplate project templates
├── conventions/                    # output/error/code conventions
├── project/                        # cross-project build reports, scraper ideas, investigations
└── lessons-learned.md              # what NOT to try (saves days of effort)
```

> **Canonical `.ai` (consolidated 2026-07-10).** This is the single source-of-truth `.ai` for the whole `apify-actors/` workspace. It was merged from the 11 drifted `.ai` copies + 2 `.agents` folders across the old niche repos: this copy was already the most complete (superset), and the unique skills/context from the others were appended here. The `qa-testing` skill kept here is the canonical version (the `.agents` fork was identical apart from a weaker frontmatter description). Old per-niche `.ai`/`.agents` folders are left in place (copy-only) but are no longer authoritative — edit only this one.

## Index

### Skills (HOW — reusable mechanics)
- [TLS Fingerprinting & HTTP client selection](skills/tls-fingerprinting.md)
- [Warm-page bootstrap token harvest (Meta / Twitter / TikTok)](skills/warm-page-token-harvest.md)
- [Balanced-brace JSON-in-HTML walker](skills/balanced-brace-json.md)
- [GraphQL doc_id / queryId discovery & rotation](skills/graphql-doc-id-rotation.md)
- [Apollo state / `__NEXT_DATA__` paywall bypass](skills/apollo-state-paywall.md)
- [Multi-strategy fallback chain (S1 → S2 → S3)](skills/multi-strategy-fallback.md)
- [Session pool, sticky session, profile rotation](skills/session-pool-rotation.md)
- [Cookie warm-up bootstrap (Akamai / PerimeterX / DataDome)](skills/cookie-warmup.md)
- [Google internal APIs: batchexecute RPC + `pb=` protobuf](skills/google-internal-apis.md)
- [Alibaba family MTOP signed requests](skills/mtop-signed-requests.md)
- [Geospatial bounding-box quadtree subdivision](skills/bbox-quadtree.md)
- [Write the README.md for an Apify Actor (Store listing)](skills/apify-actor-readme/SKILL.md)
- [Browser cookie transplant (solve-once, replay-many)](skills/browser-cookie-transplant/SKILL.md)
- [QA testing & baseline verification](skills/qa-testing/SKILL.md)
- [Adding a new actor to the workspace](skills/adding-new-actor/SKILL.md)
- [Apify Store market research, category & monetization (required post-build phase)](skills/actor-store-monetization/SKILL.md)
- [Bypass anti-bot (workflow skill)](skills/bypass-antibot/SKILL.md)
- [Debugging a scraper that went empty/wrong](skills/debugging-scraper/SKILL.md)
- [Deploying actors to Apify](skills/deploying-actors/SKILL.md)
- [API capture workflow (DevTools → replay)](skills/api-capture-workflow/SKILL.md)

### Anti-Bot (WAF-specific)
- [Cloudflare Bot Management](anti-bot/cloudflare.md)
- [PerimeterX / HUMAN Security](anti-bot/perimeterx.md)
- [DataDome](anti-bot/datadome.md)
- [Akamai Bot Manager](anti-bot/akamai.md)
- [Aliyun WAF (baxia-manager / sufei-punish)](anti-bot/aliyun.md)
- [Kasada / KPSDK](anti-bot/kasada.md)
- [Fastly (Varnish edge + Bot Management — JA3 block vs JS challenge)](anti-bot/fastly.md)
- [AWS WAF (Bot Control / AwsWafIntegration JS challenge)](anti-bot/aws-waf.md)
- [TikTok webmssdk (X-Bogus / X-Gnarly)](anti-bot/tiktok-mssdk.md)

### Playbooks (step-by-step)
- [New scraper bootstrap workflow](playbooks/new-scraper-bootstrap.md)
- [WAF triage — which protection is blocking me?](playbooks/waf-triage.md)
- [Reverse-engineer an internal GraphQL/REST API](playbooks/reverse-engineer-internal-api.md)
- [Apify deploy & marketplace publishing](playbooks/apify-deploy.md)

### Stacks (boilerplate)
- [Python Apify Actor (canonical)](stacks/python-apify-actor.md)
- [Beanstalkd + Kafka production pipeline](stacks/beanstalk-kafka-pipeline.md)
- [Node.js crypto sidecar (for JS-VM tokens)](stacks/nodejs-crypto-sidecar.md)

### Conventions
- [Dataset output envelope & raw-passthrough rule](conventions/dataset-envelope.md)
- [Error handling — fail-loud over fail-silent](conventions/error-handling.md)

### Lessons Learned (do NOT try)
- [`lessons-learned.md`](lessons-learned.md)

## Convention for adding new entries

When a new project teaches a new pattern:
1. Decide which folder it belongs to (skill / anti-bot / playbook / stack / convention / lesson).
2. Create a single `.md` file with the structure used by sibling files:
   - **Problem** — what does this solve, when does it apply
   - **Solution** — the concrete pattern (code, config, headers)
   - **Where used** — back-reference to the project that proved it
   - **Caveats** — known failure modes, rotation cadence, version drift
3. Add a line in `README.md` index and (if relevant) update `CLAUDE.md`.

## Provenance

All patterns in this folder are extracted from real production code in projects under `c:\Han\portfolio\2026`. See [`MASTER_PORTFOLIO.md`](../MASTER_PORTFOLIO.md) for the full project catalog and which actor proved each technique.
