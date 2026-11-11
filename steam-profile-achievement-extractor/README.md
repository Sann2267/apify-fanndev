# Steam Profile & Achievement Extractor

Extract public Steam Community data: user profiles, every achievement a player unlocked (with unlock time and global rarity), full achievement lists of any game, friends lists, badges and Steam group members. No Steam account and no API key needed.

## Why use this actor

- **Six data types in one actor.** Profiles, player achievements, game achievements, friends, badges and group members.
- **Achievement data you can trust.** When a player hides their game details, Steam still shows every achievement as "locked" for that player. This actor detects it and reports the profile as private instead of returning false 0% results.
- **Rarity built in.** Every achievement comes with the share of all players who unlocked it, and every player/game row carries completion %, perfect-game flag, first/last unlock time and the rarest achievement unlocked.
- **Any ID format.** SteamID64, profile URL, custom URL name, `STEAM_0:X:Y`, `[U:1:N]` or account id.
- **30 languages** for achievement names and descriptions.
- **No login, no API key.** Only public data is read; private profiles are reported as such, never guessed.

## How it works

1. Pick a mode and list the Steam users, games or groups you want.
2. The actor reads each public profile, achievement list, friends list, badge page or group member list.
3. For achievements, it adds the global unlock % and completion statistics.
4. Results stream into the dataset as clean JSON rows, ready to export as JSON, CSV or Excel. Every failed input gets its own row explaining why (private profile, unknown user, game without achievements...).

You do not need to manage Steam accounts, API keys or rate limits. The actor paces itself and retries automatically.

## Modes

| Mode | Input | One row per |
|---|---|---|
| `profiles` | `profiles` | user: name, avatar, Steam level, VAC & trade ban flags, member since, location, counts (games, badges, friends, reviews, screenshots...), recent games with hours and achievement progress, showcase stats, groups, optional equipped profile items |
| `userAchievements` | `profiles` + `appIds` (optional) | user × game: completion stats + every achievement with unlock time and global % (or one row per achievement with **One row per achievement**) |
| `gameAchievements` | `appIds` | game: every achievement with global unlock %, hidden flag, icons, rarest and most common achievement |
| `friends` | `profiles` | friend of each user: SteamID, name, avatar, online state (optionally full profile) |
| `badges` | `profiles` | badge: title, level, XP, unlock date, game, foil flag, plus the user's Steam level and XP |
| `groupMembers` | `groups` | group member: SteamID and profile link (optionally full profile) |

## Input

```json
{
    "mode": "userAchievements",
    "profiles": ["https://steamcommunity.com/id/robinwalker/", "76561198025320595"],
    "appIds": ["1245620"],
    "groups": ["https://steamcommunity.com/groups/Valve"],
    "maxItems": 1000,
    "maxGamesPerProfile": 10,
    "flattenAchievements": false,
    "onlyUnlocked": false,
    "includeProfilePage": true,
    "includeEquippedItems": false,
    "enrichProfiles": false,
    "language": "english",
    "maxConcurrency": 8,
    "maxRetries": 6,
    "proxyConfiguration": {"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `profiles`, `userAchievements`, `gameAchievements`, `friends`, `badges` or `groupMembers`. |
| `profiles` | array | Steam users in any format: SteamID64, profile URL, custom URL name, `STEAM_0:X:Y`, `[U:1:N]`, account id. |
| `appIds` | array | Steam appids or store URLs. In `userAchievements`, leave empty to use each user's recently played games. |
| `groups` | array | Group URLs, group URL names or 18-digit group ids. |
| `maxItems` | integer | Max friends / badges / members per user or group. Default 1000. |
| `maxGamesPerProfile` | integer | `userAchievements` without `appIds`: how many recent games per user. Default 10. |
| `flattenAchievements` | boolean | One row per achievement instead of one row per game. |
| `onlyUnlocked` | boolean | `userAchievements`: keep only unlocked achievements (stats still count all). |
| `includeProfilePage` | boolean | `profiles`: add Steam level, counts, recent games and showcase stats. Turn off for a very fast run over thousands of users. |
| `includeEquippedItems` | boolean | `profiles`: add equipped background, avatar frame and animated avatar. |
| `enrichProfiles` | boolean | `friends` / `groupMembers`: add each person's profile (privacy, VAC flag, member since, location...). |
| `language` | string | Language for achievement names and descriptions. |
| `maxConcurrency` | integer | Parallel requests. Default 8. |
| `maxRetries` | integer | Retries per request before an input is reported as failed. |
| `proxyConfiguration` | object | Recommended for large `profiles`, `friends` and `badges` runs: Steam limits how many profile pages one connection may open per minute. |

## Output

Each row has `recordType`, `_input` (what you asked for), `_source` and `_scrapedAt`.

### Profile (`profiles`)

```json
{
    "_input": "robinwalker",
    "_source": "S1-community-profile-xml+S1-community-profile-html+S1-api-profile-items",
    "_scrapedAt": "2026-10-11T06:46:47Z",
    "recordType": "PROFILE",
    "steamId64": "76561197960435530",
    "accountId": 169802,
    "steamId2": "STEAM_1:0:84901",
    "steamId3": "[U:1:169802]",
    "personaName": "Robin",
    "customURL": "robinwalker",
    "profileUrl": "https://steamcommunity.com/id/robinwalker/",
    "privacyState": "public",
    "visibilityState": 3,
    "isPublic": true,
    "onlineState": "offline",
    "stateMessage": "Offline",
    "avatarIcon": "https://avatars.fastly.steamstatic.com/81b5478529dce13bf24b55ac42c1af7058aaf7a9.jpg",
    "avatarMedium": "https://avatars.fastly.steamstatic.com/81b5478529dce13bf24b55ac42c1af7058aaf7a9_medium.jpg",
    "avatarFull": "https://avatars.fastly.steamstatic.com/81b5478529dce13bf24b55ac42c1af7058aaf7a9_full.jpg",
    "vacBanned": false,
    "tradeBanState": "None",
    "isLimitedAccount": false,
    "memberSince": "September 12, 2003",
    "memberSinceDate": "2003-09-12",
    "realname": "Robin Walker",
    "location": "Bellevue, Washington, United States",
    "headline": null,
    "summary": "If there's someone on Discord claiming to be me, they're trying to scam you. No one from Valve or Steam Support will ever contact you over Discord, or any other...",
    "hoursPlayedLast2Weeks": null,
    "recentGamesXml": [],
    "groups": [
        {
            "groupId64": "103582791429521412",
            "isPrimary": true,
            "name": "Valve",
            "groupUrl": "https://steamcommunity.com/groups/Valve",
            "headline": "VALVE",
            "avatarFull": "https://avatars.fastly.steamstatic.com/7ba781b5f0b8a99d4cc0b0b0dcaa22df73db7db2_full.jpg",
            "memberCount": 151,
            "membersOnline": 72,
            "membersInGame": 4,
            "membersInChat": 53
        },
        {
            "groupId64": "103582791429521478",
            "isPrimary": false,
            "name": "Dota 2 Internal",
            "groupUrl": "https://steamcommunity.com/groups/DotA",
            "headline": null,
            "avatarFull": "https://avatars.fastly.steamstatic.com/ad587614ab33f6cd96b24f7959dd1a21920f352e_full.jpg",
            "memberCount": 14,
            "membersOnline": 7,
            "membersInGame": 0,
            "membersInChat": 0
        },
        "... 34 more"
    ],
    "groupCount": 36,
    "level": 32,
    "counts": {
        "badges": 17,
        "inventory": null,
        "screenshots": 88,
        "reviews": 4,
        "groups": 36,
        "friends": 294
    },
    "gameDetailsPublic": false,
    "favoriteBadge": {
        "name": "Valve Employee",
        "xp": 1000,
        "tooltip": "Valve Employee | \nCrowbar equipped",
        "badgeUrl": "https://steamcommunity.com/id/robinwalker/badges/11",
        "appid": null
    },
    "statusHeader": "Currently Online",
    "currentGame": null,
    "recentGames": [],
    "showcaseStats": {
        "Members": 151.0,
        "In-Game": 3.0,
        "Online": 71.0,
        "In Chat": 53.0,
        "Hours played": 1083.0
    },
    "showcases": [
        "Favorite Group",
        "Favorite Game"
    ],
    "equippedItems": {
        "profile_background": {
            "communityitemid": "10700277125",
            "image_large": "https://shared.fastly.steamstatic.com/community_assets/images/items/365360/66cf0c1582973d368b6e21d6e3e35e540f88a06e.jpg",
            "name": "Keyvisual",
            "item_title": "Keyvisual",
            "item_description": "",
            "appid": 365360,
            "item_type": 15,
            "item_class": 3
        },
        "mini_profile_background": {
            "communityitemid": "16550558337",
            "image_large": "https://shared.fastly.steamstatic.com/community_assets/images/items/1098340/d53102e2dde3f5b7d419c2a52e63ed51d3d4a38b.jpg",
            "name": "UNIVERSE",
            "item_title": "UNIVERSE",
            "item_description": "",
            "appid": 1098340,
            "item_type": 34,
            "item_class": 13,
            "movie_webm": "https://shared.fastly.steamstatic.com/community_assets/images/items/1098340/b0773e1a9f8fbf35fce4e6e5bb3d337ad88adca5.webm",
            "movie_mp4": "https://shared.fastly.steamstatic.com/community_assets/images/items/1098340/c5033fa46767025ffeed805d2bafb949555cb69a.mp4"
        },
        "avatar_frame": {
            "communityitemid": "16550578784",
            "image_small": "https://shared.fastly.steamstatic.com/community_assets/images/items/570/c6a479fae8979bc9c1a02378e488e3ce06b52cb1.png",
            "image_large": "https://shared.fastly.steamstatic.com/community_assets/images/items/570/cbd274867889e08f71c57e42004e2369a991463d.png",
            "name": "Aghanim Frame",
            "item_title": "Aghanim Frame",
            "item_description": "",
            "appid": 570,
            "item_type": 36,
            "item_class": 14
        },
        "animated_avatar": {},
        "profile_modifier": {},
        "steam_deck_keyboard_skin": {
            "communityitemid": "20231628825",
            "image_small": "https://shared.fastly.steamstatic.com/community_assets/images/items/1675200/3f8729ef33b47be964cb2e1db9d92dacd934930f.png",
            "image_large": "https://shared.fastly.steamstatic.com/community_assets/images/items/1675200/da088c1f226ae8d4058415f935b1632269489212.png",
            "name": "Digital",
            "item_title": "Digital",
            "item_description": "",
            "appid": 1675200,
            "item_type": 16,
            "item_class": 16
        }
    }
}
```

### Player achievements (`userAchievements`)

Identity fields of private players are masked in this README; the actor returns them in full.

```json
{
    "_input": "<profile>",
    "_source": "S1-community-stats-xml+S1-api-game-achievements",
    "_scrapedAt": "2026-10-11T06:46:09Z",
    "recordType": "PLAYER_GAME_ACHIEVEMENTS",
    "steamId64": "7656119XXXXXXXXXX",
    "personaName": "<player>",
    "profileUrl": "https://steamcommunity.com/profiles/7656119XXXXXXXXXX/",
    "appid": 1245620,
    "gameName": "ELDEN RING",
    "gameLink": "https://steamcommunity.com/app/1245620",
    "gameIcon": "https://shared.fastly.steamstatic.com/community_assets/images/apps/1245620/b6e290dd5a92ce98f89089a207733c70c41a1871.jpg",
    "gameLogo": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1245620/capsule_184x69.jpg?t=1790290043",
    "statsName": "1245620",
    "totalAchievements": 42,
    "unlockedAchievements": 42,
    "completionPct": 100.0,
    "isPerfect": true,
    "firstUnlockAt": "2022-07-07T04:33:26Z",
    "lastUnlockAt": "2026-10-10T23:16:57Z",
    "rarestUnlocked": {
        "apiname": "ACH00",
        "name": "Elden Ring",
        "globalPercent": 10.5
    },
    "hoursLast2Weeks": 39.0,
    "hoursOnRecord": 104.0,
    "lastPlayedDate": "2026-10-10",
    "ownershipConfirmed": true,
    "gameDetailsPublic": true,
    "language": "english",
    "achievements": [
        {
            "apiname": "ACH00",
            "name": "Elden Ring",
            "description": "Obtained all achievements",
            "achieved": true,
            "unlockTime": 1791674217,
            "unlockedAt": "2026-10-10T23:16:57Z",
            "hidden": false,
            "globalPercent": 10.5,
            "iconUrl": "https://shared.fastly.steamstatic.com/community_assets/images/apps/1245620/1cb1fe89084e822bd7d9ad4df66bc7f917995b38.jpg",
            "iconGrayUrl": "https://shared.fastly.steamstatic.com/community_assets/images/apps/1245620/172885dcb6a82300de9f34e8833afdf7d7cd24e1.jpg"
        },
        {
            "apiname": "ACH01",
            "name": "Elden Lord",
            "description": "Achieved the \"Elden Lord\" ending",
            "achieved": true,
            "unlockTime": 1791673258,
            "unlockedAt": "2026-10-10T23:00:58Z",
            "hidden": true,
            "globalPercent": 23.9,
            "iconUrl": "https://shared.fastly.steamstatic.com/community_assets/images/apps/1245620/e50726be4aca4d2b1f5f14d36859fc8e6f710097.jpg",
            "iconGrayUrl": "https://shared.fastly.steamstatic.com/community_assets/images/apps/1245620/172885dcb6a82300de9f34e8833afdf7d7cd24e1.jpg"
        },
        "... 40 more"
    ]
}
```

### Game achievement row (`gameAchievements` with **One row per achievement**)

```json
{
    "_input": "1245620",
    "_source": "S1-api-game-achievements",
    "_scrapedAt": "2026-10-11T06:46:12Z",
    "recordType": "GAME_ACHIEVEMENT",
    "appid": 1245620,
    "gameName": "ELDEN RING",
    "storeUrl": "https://store.steampowered.com/app/1245620/ELDEN_RING",
    "language": "english",
    "rank": 42,
    "apiname": "ACH00",
    "name": "Elden Ring",
    "description": "Obtained all achievements",
    "hidden": false,
    "globalPercent": 10.5,
    "iconUrl": "https://shared.fastly.steamstatic.com/community_assets/images/apps/1245620/1cb1fe89084e822bd7d9ad4df66bc7f917995b38.jpg",
    "iconGrayUrl": "https://shared.fastly.steamstatic.com/community_assets/images/apps/1245620/172885dcb6a82300de9f34e8833afdf7d7cd24e1.jpg",
    "archived": false,
    "progressType": 0
}
```

### Friend (`friends`)

```json
{
    "_input": "robinwalker",
    "_source": "S1-community-friends-html",
    "_scrapedAt": "2026-10-11T06:46:16Z",
    "recordType": "FRIEND",
    "ownerSteamId64": "76561197960435530",
    "ownerPersonaName": "Robin",
    "ownerFriendCount": 294,
    "position": 1,
    "steamId64": "7656119XXXXXXXXXX",
    "accountId": 0,
    "steamId2": "STEAM_1:X:XXXXXXX",
    "steamId3": "[U:1:XXXXXXXX]",
    "personaName": "<player>",
    "profileUrl": "https://steamcommunity.com/profiles/7656119XXXXXXXXXX/",
    "onlineState": "in-game",
    "statusText": "Dota 2",
    "avatarMedium": "https://avatars.fastly.steamstatic.com/<hash>_medium.jpg"
}
```

### Badge (`badges`)

```json
{
    "_input": "robinwalker",
    "_source": "S1-community-badges-html",
    "_scrapedAt": "2026-10-11T06:46:19Z",
    "recordType": "BADGE",
    "ownerSteamId64": "76561197960435530",
    "ownerPersonaName": "Robin",
    "profileLevel": 32,
    "profileXp": 6994,
    "xpToNextLevel": 206,
    "totalBadges": 17,
    "page": 1,
    "badgeKey": "badge_2",
    "badgeType": "community",
    "appid": null,
    "isFoil": null,
    "badgeId": 2,
    "title": "Community Ambassador",
    "levelName": "Community Ambassador",
    "level": null,
    "xp": 200,
    "unlocked": "9 Nov, 2015 @ 5:17pm",
    "unlockedDate": "2015-11-09",
    "isEarned": true,
    "progress": null,
    "cardDrops": null,
    "playtime": null,
    "iconUrl": "https://community.fastly.steamstatic.com/public/images/badges/01_community/community03_80.png",
    "badgeUrl": "https://steamcommunity.com/id/robinwalker/badges/2"
}
```

### Group member (`groupMembers` with **enrichProfiles**)

```json
{
    "_input": "Valve",
    "_source": "S1-community-group-xml",
    "_scrapedAt": "2026-10-11T06:46:22Z",
    "recordType": "GROUP_MEMBER",
    "groupId64": "103582791429521412",
    "groupName": "Valve",
    "groupUrl": "https://steamcommunity.com/groups/Valve",
    "memberCount": 151,
    "membersOnline": 72,
    "membersInGame": 3,
    "page": 1,
    "steamId64": "7656119XXXXXXXXXX",
    "accountId": 0,
    "steamId2": "STEAM_1:X:XXXXXXX",
    "steamId3": "[U:1:XXXXXXXX]",
    "personaName": "<player>",
    "customURL": null,
    "profileUrl": "https://steamcommunity.com/profiles/7656119XXXXXXXXXX/",
    "privacyState": "friendsonly",
    "onlineState": "offline",
    "vacBanned": false,
    "tradeBanState": "None",
    "isLimitedAccount": false,
    "memberSince": null,
    "memberSinceDate": null,
    "location": null,
    "realname": null,
    "avatarFull": "https://avatars.fastly.steamstatic.com/<hash>_full.jpg",
    "hoursPlayedLast2Weeks": null
}
```

### Error row

```json
{
    "_input": "<profile>",
    "_source": "none",
    "_scrapedAt": "2026-10-11T06:46:28Z",
    "recordType": "ERROR",
    "_error": "game_details_private",
    "_errorDetail": "Profile is public but its game details are private. Steam would answer with every achievement locked, so no data is emitted rather than false zeros.",
    "steamId64": "7656119XXXXXXXXXX",
    "personaName": "<player>",
    "profileUrl": "https://steamcommunity.com/profiles/7656119XXXXXXXXXX/"
}
```

| `_error` | Meaning |
|---|---|
| `invalid_input` | The value is not a Steam user / game / group reference. |
| `profile_not_found` | No Steam user with that id or custom URL. |
| `profile_private` | The profile is private or friends-only. |
| `game_details_private` | The profile is public but its game details (playtime, achievements) are hidden. |
| `no_achievements` | The game has no Steam achievements, or the appid does not exist. |
| `no_recent_games` | No `appIds` given and the user has no recently played games. |
| `friends_private` / `no_friends` | Friends list hidden / empty. |
| `badges_private` / `no_badges` | Badge page hidden / empty. |
| `group_not_found` | No Steam group at that URL or id. |
| `blocked` | Steam kept refusing after every retry. Run again later or enable a proxy. |

## Good to know

- **Steam no longer shows anyone's full game library without login.** `userAchievements` therefore works on the games you list, or on each user's recently played games. Use `gameAchievements` to see what every game contains.
- **`ownershipConfirmed: false`** means the player has 0 achievements and no recent playtime in that game. Steam answers the same way for games the player does not own, so a 0% there is not proof they played it.
- `hoursLast2Weeks` is playtime in the last two weeks. Lifetime hours (`hoursOnRecord`) are only published for recently played games.
- Steam hides the year on dates in the current year ("10 Oct"); `...Date` fields are completed to `YYYY-MM-DD`. Badge and last-played times of day are not included because Steam does not say which time zone they are in.
- Steam's privacy setting can take a while to reach every page. `profilePagePrivate: true` marks a profile whose page is already private even though `privacyState` still says public.
- VAC bans are reported as a yes/no flag. Steam no longer shows the number of bans or days since the last ban on public pages.
- Global achievement percentages are rounded by Steam to one decimal.

## Use cases

- Achievement hunting and completionist leaderboards for a community or Discord.
- Game analytics: which achievements players reach, where they drop off, how rare the ending is.
- Player research for esports, tournaments and community management (account age, level, ban flag).
- Group and community analysis: who is in a Steam group and how active they are.
