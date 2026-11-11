# Socios.com Fan Token & Fan Vote Scraper

Extract Socios.com fan votes **with their results already counted** — the question, every option, how many votes each option got and which one won — across 9,800+ polls from 231 partner clubs, plus the full fan token catalogue with on-chain contract addresses. No account, no login, no API key.

## Why use this actor

- **No Socios account required.** Nothing to sign up for, no keys to manage.
- **Vote results, not just questions.** Every poll comes back with each option's vote count and percentage, the winning option, the participation quorum and whether it was met — the numbers fans usually only see inside the app.
- **The whole governance history.** Roughly 9,825 polls going back to 2021, covering what clubs actually asked their token holders and how those holders voted.
- **Token data with contract addresses.** 346 tokens with their smart contract address, decimals, logo, circulating supply and the exchanges each club's token is listed on.
- **Filter by club by name.** Type `Barcelona`, `$PSG` or `Sauber` — the actor matches it to the right club for you. An ambiguous or unknown name comes back as a clearly labelled row, never a silent wrong answer.
- **Stable JSON output** ready for spreadsheets, databases or dashboards, with automatic retries and export to JSON, CSV or Excel.

## How it works

1. Pick what you want: fan votes, partner clubs, fan tokens, vote tokens, reference tables, or everything at once.
2. Optionally narrow fan votes to specific clubs, a poll status such as *closed*, or a poll type such as *integrity*.
3. The actor collects the full catalogue, paging through it for you and retrying anything that stumbles.
4. Each poll's results are tallied so the winning option and total votes sit right on the row, next to the raw per-option breakdown.
5. Results land in the dataset, ready to download or push onward.

No scrapers, browsers or blocks to babysit.

## Input

```json
{
  "mode": "polls",
  "partners": ["AC Milan", "$PSG", "Barcelona"],
  "pollStatuses": ["closed"],
  "pollTypes": ["integrity"],
  "pollOrderBy": "",
  "activePartnersOnly": false,
  "maxItems": 1000,
  "proxyConfiguration": { "useApifyProxy": false }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `mode` | string | `polls` (fan votes with results), `partners` (231 clubs), `fanTokens` (346 tokens), `voteTokens` (106 tokens with supply), `reference` (leagues, sports, countries) or `all`. Default `polls`. |
| `partners` | array | Fan votes only. Club name, token symbol, short code or id — `AC Milan`, `$ACM` and `ACM` all work, and `Barcelona` finds *FC Barcelona*. Empty means every club. |
| `pollStatuses` | array | Fan votes only. `closed` gives the ~8,100 polls with final results; `opened` is whatever is live right now. Empty means every status. |
| `pollTypes` | array | Fan votes only. `engagement` (fun polls), `integrity` (binding club decisions) or `prediction` (match forecasts). Empty means all three. |
| `pollOrderBy` | string | Newest first either way. Optionally pin the ordering to `createdAt`, `openAt`, `closeAt`, `publicationDate` or `status`. |
| `activePartnersOnly` | boolean | Partner clubs only. 88 of the 231 clubs are active; turn this on to skip the rest. |
| `maxItems` | integer | Caps fan votes and partner clubs. Default 1000; the full poll catalogue is about 9,825. |
| `proxyConfiguration` | object | Off by default and genuinely optional — see Notes. |

## Output

### Fan vote (`recordType: "POLL"`)

```json
{
  "_input": "Belgium - RBFA",
  "_source": "S1-chiliz-acl",
  "_scrapedAt": "2026-09-20T15:51:42Z",
  "recordType": "POLL",
  "id": "3d62097d-d286-4f6a-9c12-faf57a4cca55",
  "partnerName": "Belgium - RBFA",
  "partnerShortName": "BELG",
  "question": "BELG | New Corner Flags Design",
  "information": "$BELG Fan Token holders, you have the chance to choose the new design for the corner flags that the national team will use for their upcoming home matches. Your vote counts, it's up to you to decide!",
  "status": "closed",
  "type": "integrity",
  "isBound": true,
  "openAt": "2026-09-11T10:00:00+00:00",
  "closeAt": "2026-09-16T12:00:00+00:00",
  "disclosedAt": "2026-09-16T12:00:00+00:00",
  "quorum": "0.05",
  "currentQuorumPercentage": "34",
  "isQuorumReached": true,
  "usedTokenCount": "198",
  "blockchainAddress": "0xA66eBDf6E6e9d868D3D0d465c93e99e137ae403B",
  "answers": [
    { "answer": "Design #3", "totalVoteTokensUsed": 25, "votePercentage": "12.626262626262" },
    { "answer": "Design #1", "totalVoteTokensUsed": 69, "votePercentage": "34.848484848484" },
    { "answer": "Design #2", "totalVoteTokensUsed": 104, "votePercentage": "52.525252525252" }
  ],
  "answerCount": 3,
  "totalVoteTokensUsed": 198.0,
  "leadingAnswer": "Design #2",
  "leadingAnswerVotes": 104.0,
  "leadingAnswerPercentage": 52.525252525252,
  "isDisclosed": true
}
```

| Field | Type | Description |
| --- | --- | --- |
| `question` | string | The question put to fans. |
| `information` | string | The longer explanation shown alongside the vote. |
| `partnerName` / `partnerShortName` | string | The club that ran the vote. |
| `status` | string | `closed`, `opened`, `cancelled`, `error`, `suspended` or `cancelling`. |
| `type` | string | `engagement`, `integrity` (binding) or `prediction`. |
| `isBound` | boolean | Whether the club is bound by the result. |
| `openAt` / `closeAt` / `disclosedAt` | string | When voting opened, closed and when the result was published. |
| `quorum` / `currentQuorumPercentage` / `isQuorumReached` | string / boolean | The participation threshold and whether the vote cleared it. |
| `answers` | array | Every option with `totalVoteTokensUsed` and `votePercentage`. Prediction polls also carry `isCorrect` and `hasWon`. |
| `answerCount` | number | How many options were offered. |
| `totalVoteTokensUsed` | number | Votes summed across every option. |
| `leadingAnswer` / `leadingAnswerVotes` / `leadingAnswerPercentage` | string / number | The winning option and its numbers. `null` on a poll where nothing was cast. |
| `blockchainAddress` | string | Where the vote was recorded on chain. |

### Partner club (`recordType: "PARTNER"`)

```json
{
  "_input": "AC Milan",
  "recordType": "PARTNER",
  "name": "AC Milan",
  "shortName": "ACM",
  "tokenSymbol": "$ACM",
  "type": "sport_teams",
  "status": "active",
  "mainColour": "#C30405",
  "description": "“We will be a team of devils. Our colours will be red like fire and black to invoke fear in our opponents!” These were the words that Herbert Kilpin used as he founded AC Milan on 16 December 1899. AC Milan is one of the most successful football clubs of all time with over 40 titles to their name including 7 UEFA Champions Leagues and 19 Serie A titles.",
  "isSigned": true,
  "ticketCollectionType": "eTicket",
  "tokenSupportingPlatforms": [
    { "name": "Paribu", "type": "exchange" },
    { "name": "Gate.io", "type": "exchange" },
    { "name": "Binance", "type": "exchange" }
  ],
  "leagueIds": ["d6df9539-b6d7-42f9-a0ad-859dc13edfb7", "90a5b41d-ca5c-41c5-973b-bc540045685c"],
  "currencyId": "bc39a750-c299-45cf-b2b0-459b650ed5fe"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `name` / `shortName` / `tokenSymbol` | string | Club name, three-letter code and token ticker. |
| `type` | string | `sport_teams`, `esport_teams`, `brand`, `events` or `league_tokens`. |
| `status` | string | `active`, `inactive` or `created`. |
| `mainColour` | string | The club's brand colour. |
| `tokenSupportingPlatforms` | array | Exchanges listing this club's token. |
| `leagueIds` / `currencyId` | string | Join keys — run `reference` and `fanTokens` mode to resolve them. |

### Fan token (`recordType: "FAN_TOKEN"`)

```json
{
  "_input": "IBFK",
  "recordType": "FAN_TOKEN",
  "shortCode": "IBFK",
  "symbol": "$IBFK",
  "label": "İstanbul Başakşehir FK",
  "type": "voteToken",
  "smartContractAddress": "0x7B69003C404B0579F257c16E2664b4Eb4c7b2acf",
  "decimals": 18,
  "networkCount": 1,
  "logoUrl": "https://assets.chiliz.com/currency/01c05faf-f2e2-41a1-90fb-0f67c6ee3983/currency_logo/cf8cbf42-de45-4efe-9a0d-a176005095ab.png?version=1777280097",
  "partnerName": "İstanbul Başakşehir FK",
  "partnerType": "sport_teams"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `shortCode` / `symbol` / `label` | string | Token code, ticker and display name. |
| `type` | string | `voteToken`, `nonDecimalVoteToken`, `externalToken`, `fiat`, `crypto` or `polygon`. |
| `smartContractAddress` / `decimals` | string / number | Contract details on the token's primary network. |
| `logoUrl` | string | Token logo. |
| `partnerName` | string | The club that owns it, where one matches. Non-club currencies leave this `null`. |

### Vote token (`recordType: "VOTE_TOKEN"`)

```json
{
  "_input": "$ACM",
  "recordType": "VOTE_TOKEN",
  "tokenName": "AC Milan",
  "tokenSymbol": "$ACM",
  "shortCode": "ACM",
  "supply": "19920000.000000000000000000",
  "status": "minted",
  "blockchainAddress": "0xF9C0F80a6c67b1B39bdDF00ecD57f2533ef5b688",
  "processedAt": "2021-01-18T09:29:07+00:00",
  "description": "Join a global community of $ACM Fan Token holders, play fun games, impact fan-related decisions, compete in leaderboards for top prizes, and redeem incredible rewards. … 900 more characters",
  "partnerName": "AC Milan"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `tokenName` / `tokenSymbol` / `shortCode` | string | Token identity. |
| `supply` | string | Total supply. |
| `blockchainAddress` | string | Token contract address. |
| `processedAt` | string | When the token was minted. |
| `description` | string | The club's own description, often including the release schedule. |

### Reference tables (`recordType: "LEAGUE"`, `"SPORT"`, `"COUNTRY"`)

```json
{
  "_input": "Ligue 1 Uber Eats",
  "recordType": "LEAGUE",
  "name": "Ligue 1 Uber Eats",
  "status": "active",
  "sportName": "Football",
  "countryName": "France",
  "options": { "isPredictorEnabled": true },
  "partnerIds": ["c2d54ced-43c2-43e2-9d58-66684f02afb2", "6d189e7d-1af6-47ae-9c82-545b774bcb96"],
  "id": "13f963c7-6c9b-41bd-9d89-1083ec387103"
}
```

49 leagues, 6 sports and 249 countries. Leagues already carry `sportName` and `countryName` resolved for you.

### Error rows

Anything that could not be resolved is reported rather than dropped:

```json
{
  "_input": "Milan",
  "_source": "none",
  "recordType": "ERROR",
  "_error": "partner_not_found",
  "_errorDetail": "matches 3 clubs (AC Milan, FC Internazionale Milano, Milan Devils) -- name one exactly. Run the actor in partners mode to list all 231 clubs with their exact names and symbols."
}
```

## Notes and limits

- **Poll catalogue size:** about 9,825 polls, of which ~8,100 are closed with final results, ~1,690 cancelled and typically one open at any moment. A full run takes a few minutes.
- **Prediction polls** are rare and the ones published so far were cancelled with no votes cast, so their `leadingAnswer` is `null`. That is the real state of the data, not a gap.
- **Poll type filtering** happens after collection, so narrowing by type trims the dataset but not the run time. Narrowing by club or status is applied at the source and does make runs faster.
- **Not available:** token prices, market data, the fan shop, collectibles and auctions, leaderboards, pledge campaigns and token quests are restricted to signed-in users and this actor does not return them. Token contract addresses are included, so prices can be joined from any market data source.
- **Proxy** is off by default and genuinely optional — Socios' data is the same from any location. Turn on Residential only if you run this on a frequent schedule from one address.
- **Data freshness:** polls are added continuously; run on a schedule and filter `pollStatuses` to `opened` to catch live votes, or to `closed` for settled results.
