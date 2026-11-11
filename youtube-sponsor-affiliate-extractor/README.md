# YouTube Sponsor & Affiliate Link Extractor

Find out which YouTube creators are being paid, by whom, and with what offer.

Give it videos or channel handles. It reads each video's **full description** and
returns the affiliate links, promo codes, discount percentages, sponsor mentions
and `#ad`-style disclosures inside it — as structured fields, not as a wall of text.

No login, no cookies, no API key.

## What you get

```json
{
  "recordType": "VIDEO",
  "title": "I Tried All The Best (and Worst) Doorbell Cameras",
  "channelName": "Linus Tech Tips",
  "isMonetisedDescription": true,
  "monetisationSignals": ["affiliate-link", "promo-code", "disclosure-marker"],
  "affiliateNetworks": ["genius-link"],
  "affiliateLinkCount": 6,
  "promoCodes": ["LTT"],
  "discountPercents": [20],
  "disclosureMarkers": ["affiliate link", "affiliate links"],
  "sponsorMentions": [],
  "viewCount": 1284993,
  "captionLanguages": ["en", "es"]
}
```

`isMonetisedDescription` is never a bare verdict. Every record carries
`monetisationSignals` listing exactly which rules fired, so you can filter on the
signal *you* trust — say, only videos with a promo code — instead of on ours.

## Modes

| Mode | Input | What it does |
| --- | --- | --- |
| `video` | `videos` — IDs, `watch?v=`, `youtu.be/`, `/shorts/`, `/live/`, `/embed/` | One record per video |
| `channel` | `channels` — `@handle` or channel URL | Takes each channel's newest `videosPerChannel` uploads, then as above |
| `reference` | — | Probes the surface and reports what it actually yielded. Run this first if a result looks wrong |

## How links are classified

This is where most description scrapers get it wrong, so the buckets are narrow
and separate:

| Kind | Meaning | Counts as sponsorship? |
| --- | --- | --- |
| `affiliate` | A real commission network: Amazon Associates, Impact, ShareASale, Awin, CJ, Rakuten, ClickBank, Genius Link, Partnerize, Skimlinks, MagicLinks, ShopMy, LTK | **Yes** |
| `sponsor-landing` | Hosts that routinely run creator campaigns (Squarespace, NordVPN, Brilliant, HelloFresh, AG1…) | **Yes** |
| `smart-link` | The creator's *own* release routing: Linkfire `lnk.to`, `smarturl.it`, Linktree, Beacons | No |
| `shortened` | `bit.ly`, `tinyurl`, `cutt.ly` — destination unknown until resolved | No, flagged for follow-up |
| `creator-platform` | Patreon, Ko-fi, merch stores | No |
| `social`, `tracked`, `other` | Everything else | No |

An Amazon link is only `affiliate` when it actually carries an associate tag
(`tag=`, `ascsubtag`, `linkcode`) — the tag is returned in `amazonTag`.

**Why this matters:** an earlier build of this Actor treated `lnk.to` and
`smarturl.it` as affiliate networks. It then reported Rick Astley, PSY and Luis
Fonsi as running sponsored content. An agency filtering on "monetised" would have
received three music videos and zero brand deals.

## The one thing to know before you run it

YouTube sometimes serves a **reduced watch page**: a real 1.1–1.3 MB page,
HTTP 200, with the player response simply missing. Measured over three attempts
per video on 2026-09-20, hit rates ranged from 3/3 down to 0/3 on the *same*
video. Neither consent cookies, `bpctr`/`has_verified`, nor `m.youtube.com`
improved it.

So this Actor **retries each video up to six times, rotating TLS profile**, and
only then emits a `REDUCED` record. That distinction is the point:

- `recordType: "VIDEO"` — parsed; `_attempts` tells you how hard it was.
- `recordType: "REDUCED"` — YouTube would not serve us the payload. **This is not
  proof the video has no description.** Retry later or use a proxy.
- `recordType: "ERROR"` — a genuine failure (no such video, challenge page).

If many records come back `REDUCED`, that is an IP-shaped symptom — switch on
`proxyConfiguration`.

## What this Actor does not do

**It does not read transcripts.** The description is the surface; the caption
track is not. `captionLanguages` tells you which subtitle tracks exist, because
the language list *is* public — but every signed caption URL answers HTTP 200
with a **zero-byte body**, and the InnerTube player endpoint answers 400
(ANDROID/IOS) or `UNPLAYABLE` (WEB). Rather than ship a transcript field that is
empty most of the time, this Actor reports what it can actually get. Details and
the full list of variants tested are in [`CRAWLING_METHOD.md`](CRAWLING_METHOD.md).

## Cost

One request per video, plus one per channel in `channel` mode — times however
many retries the reduced page forces. A channel sweep of 15 videos is typically
16–25 requests.

## Input example

```json
{
  "mode": "channel",
  "channels": ["@mkbhd", "@LinusTechTips"],
  "videosPerChannel": 20,
  "concurrency": 4
}
```
