"""Spotify's editorial chart playlists, verified live on 2026-09-20.

Spotify keeps its chart playlists **out of every search surface**. Pathfinder
search happily returns ordinary editorial playlists (Hot Hits, New Music
Friday) but never a ``37i9dQZEVXb…`` chart, and the Web API search hides them
too, so there is no way to discover a chart by name at runtime. They are only
reachable by id, which is why this catalogue is pinned rather than looked up.

Every entry below was fetched and confirmed to be a live ranked playlist. Ids
that once existed and no longer resolve are recorded in ``RETIRED`` so the
actor can explain a dead chart instead of reporting an empty one.
"""

from __future__ import annotations

# Top 50, recalculated daily.
DAILY = {
    "GLOBAL": "37i9dQZEVXbMDoHDwVN2tF",
    "AE": "37i9dQZEVXbM4UZuIrvHvA",
    "AR": "37i9dQZEVXbMMy2roB9myp",
    "AT": "37i9dQZEVXbKNHh6NIXu36",
    "AU": "37i9dQZEVXbJPcfkRz0wJ0",
    "BE": "37i9dQZEVXbJNSeeHswcKB",
    "BR": "37i9dQZEVXbMXbN3EUUhlg",
    "CA": "37i9dQZEVXbKj23U1GF4IR",
    "CH": "37i9dQZEVXbJiyhoAPEfMK",
    "CL": "37i9dQZEVXbL0GavIqMTeb",
    "CO": "37i9dQZEVXbOa2lmxNORXQ",
    "CZ": "37i9dQZEVXbIP3c3fqVrJY",
    "DE": "37i9dQZEVXbJiZcmkrIHGU",
    "DK": "37i9dQZEVXbL3J0k32lWnN",
    "ES": "37i9dQZEVXbNFJfN1Vw8d9",
    "FI": "37i9dQZEVXbMxcczTSoGwZ",
    "FR": "37i9dQZEVXbIPWwFssbupI",
    "GB": "37i9dQZEVXbLnolsZ8PSNw",
    "GR": "37i9dQZEVXbJqdarpmTJDL",
    "HK": "37i9dQZEVXbLwpL8TjsxOG",
    "HU": "37i9dQZEVXbNHwMxAkvmF8",
    "ID": "37i9dQZEVXbObFQZ3JLcXt",
    "IE": "37i9dQZEVXbKM896FDX8L1",
    "IL": "37i9dQZEVXbJ6IpvItkve3",
    "IN": "37i9dQZEVXbLZ52XmnySJg",
    "IT": "37i9dQZEVXbIQnj7RRhdSX",
    "JP": "37i9dQZEVXbKXQ4mDTEBXq",
    "KR": "37i9dQZEVXbNxXF4SkHj9F",
    "MA": "37i9dQZEVXbJU9eQpX8gPT",
    "MX": "37i9dQZEVXbO3qyFxbkOE1",
    "MY": "37i9dQZEVXbJlfUljuZExa",
    "NG": "37i9dQZEVXbKY7jLzlJ11V",
    "NL": "37i9dQZEVXbKCF6dqVpDkS",
    "NO": "37i9dQZEVXbJvfa0Yxg7E7",
    "NZ": "37i9dQZEVXbM8SIrkERIYl",
    "PE": "37i9dQZEVXbJfdy5b0KP7W",
    "PH": "37i9dQZEVXbNBz9cRCSFkY",
    "PL": "37i9dQZEVXbN6itCcaL3Tt",
    "PT": "37i9dQZEVXbKyJS56d1pgi",
    "RO": "37i9dQZEVXbNZbJ6TZelCq",
    "SA": "37i9dQZEVXbLrQBcXqUtaC",
    "SE": "37i9dQZEVXbLoATJ81JYXz",
    "SG": "37i9dQZEVXbK4gjvS1FjPY",
    "TH": "37i9dQZEVXbMnz8KIWsvf9",
    "TR": "37i9dQZEVXbIVYVBNw9D5K",
    "TW": "37i9dQZEVXbMnZEatlMSiu",
    "US": "37i9dQZEVXbLRQDuF5jeBp",
    "VN": "37i9dQZEVXbLdGSmz6xilI",
    "ZA": "37i9dQZEVXbMH2jvi6jvjk",
}

# Top Songs, recalculated weekly. Spotify publishes these for far fewer
# territories than the daily charts, so this map is deliberately shorter.
WEEKLY = {
    "GLOBAL": "37i9dQZEVXbNG2KDcFcKOF",
    "AR": "37i9dQZEVXbKPTKrnFPD0G",
    "AU": "37i9dQZEVXbK4fwx2r07XW",
    "BR": "37i9dQZEVXbKzoK95AbRy9",
    "CA": "37i9dQZEVXbMda2apknTqH",
    "DE": "37i9dQZEVXbK8BKKMArIyl",
    "ES": "37i9dQZEVXbJwoKy8qKpHG",
    "GB": "37i9dQZEVXbMwmF30ppw50",
    "IN": "37i9dQZEVXbMWDif5SCBJq",
    "IT": "37i9dQZEVXbJUPkgaWZcWG",
    "JP": "37i9dQZEVXbKqiTGXuCOsB",
    "KR": "37i9dQZEVXbJZGli0rRP3r",
    "MX": "37i9dQZEVXbKUoIkUXteF6",
    "US": "37i9dQZEVXbLp5XoPON0wI",
}

# Charts Spotify has discontinued. Their ids still resolve to HTTP 200, but the
# entity is {"__typename": "NotFound"} -- so without this list the actor would
# report "chart not found" for something that was a real product until recently.
RETIRED = {
    "37i9dQZEVXbLiRSasKsNU9": "Viral 50 - Global",
    "37i9dQZEVXbKuaTI1Z1Afx": "Viral 50 - USA",
    "37i9dQZEVXbKpV6RVDTWcZ": "Viral 50 - Indonesia",
}

RECURRENCES = ("daily", "weekly")


def resolve(country: str, recurrence: str) -> str | None:
    table = DAILY if recurrence == "daily" else WEEKLY
    return table.get(country.strip().upper())


def available(recurrence: str) -> list[str]:
    return sorted((DAILY if recurrence == "daily" else WEEKLY).keys())
