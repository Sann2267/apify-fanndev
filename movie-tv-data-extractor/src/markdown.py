"""Render a record as a self-contained Markdown document, for RAG pipelines.

This is the output format that exists because of how these datasets are
actually used. A buyer pulling 500 films to answer questions over them does not
want to write a JSON-to-prose template first, and pasting raw TMDB JSON into a
prompt spends most of the context window on punctuation and null fields.

Three properties are deliberate, because they are what makes a chunk work as a
retrieval unit:

* Every document is self-describing. The title, year and media type appear in
  the text, not only in a metadata column, so a chunk retrieved on its own
  still says what it is about. A cast list that begins "Leonardo DiCaprio as
  Dom Cobb" with no film named above it is a retrieval dead end.
* Empty fields are omitted, never rendered as "None" or "N/A". A model reading
  "Budget: None" will cheerfully tell someone the budget was none.
* Numbers are formatted the way a human writes them -- $160,000,000, 8.4/10,
  1h 48m -- because that is the form the model has seen most often and is
  least likely to mangle when it quotes it back.
"""

from __future__ import annotations

from typing import Any


def _fmt_money(value: Any) -> str | None:
    try:
        return f"${int(value):,}"
    except (TypeError, ValueError):
        return None


def _fmt_runtime(minutes: Any) -> str | None:
    try:
        total = int(minutes)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    hours, mins = divmod(total, 60)
    return f"{hours}h {mins}m ({total} min)" if hours else f"{total} min"


def _fmt_votes(value: Any) -> str | None:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return None


def _join(values: Any, limit: int = 0) -> str | None:
    if not isinstance(values, list) or not values:
        return None
    items = [str(v) for v in values if v]
    if not items:
        return None
    if limit and len(items) > limit:
        return ", ".join(items[:limit]) + f", and {len(items) - limit} more"
    return ", ".join(items)


def _facts(rows: list[tuple[str, Any]]) -> list[str]:
    """A bullet per fact, skipping every fact that has no value."""
    return [f"- **{label}:** {value}" for label, value in rows if value not in (None, "", [], {})]


def _section(lines: list[str], heading: str, body: list[str]) -> None:
    if body:
        lines.append(f"## {heading}")
        lines.extend(body)
        lines.append("")


def _rating_line(data: dict[str, Any]) -> str | None:
    score = data.get("voteAverage")
    if not score:
        return None
    votes = _fmt_votes(data.get("voteCount"))
    return f"{round(float(score), 1)}/10" + (f" from {votes} votes" if votes else "")


# -- titles ----------------------------------------------------------------

def title_markdown(data: dict[str, Any]) -> str:
    is_tv = data.get("mediaType") == "tv"
    name = data.get("title") or "Untitled"
    year = data.get("year")
    heading = f"# {name}" + (f" ({year})" if year else "")
    lines: list[str] = [heading, ""]

    if data.get("tagline"):
        lines += [f"*{data['tagline']}*", ""]

    original = data.get("originalTitle")
    facts = _facts([
        ("Type", "TV series" if is_tv else "Movie"),
        ("Original title", original if original and original != name else None),
        ("Status", data.get("status")),
        ("First aired" if is_tv else "Released", data.get("releaseDate")),
        ("Last aired", data.get("lastAirDate") if is_tv else None),
        ("Seasons", data.get("numberOfSeasons")),
        ("Episodes", data.get("numberOfEpisodes")),
        ("Runtime", _fmt_runtime(data.get("runtimeMins"))),
        ("Genres", _join(data.get("genres"))),
        ("Rating", _rating_line(data)),
        ("Certification", data.get("certification")),
        ("Original language", data.get("originalLanguage")),
        ("Spoken languages", _join(data.get("spokenLanguages"), 6)),
        ("Countries", _join(data.get("productionCountries"), 6)),
        ("Networks", _join(data.get("networks")) if is_tv else None),
        ("Created by", _join(data.get("createdBy")) if is_tv else None),
        ("Production", _join(data.get("productionCompanies"), 6)),
        ("Part of", (data.get("collection") or {}).get("name")),
        ("IMDb", data.get("imdbId")),
        ("TMDB", data.get("tmdbUrl")),
        ("Homepage", data.get("homepage")),
    ])
    lines += facts + [""]

    if data.get("overview"):
        _section(lines, "Overview", [data["overview"]])

    key_crew = _facts([
        ("Directed by", _join(data.get("directors"))),
        ("Written by", _join(data.get("writers"), 8)),
        ("Produced by", _join(data.get("producers"), 8)),
        ("Music by", _join(data.get("composers"), 4)),
        ("Cinematography", _join(data.get("cinematographers"), 4)),
        ("Editing", _join(data.get("editors"), 4)),
    ])
    _section(lines, "Key crew", key_crew)

    cast = data.get("cast")
    if isinstance(cast, list) and cast:
        rows = []
        for member in cast:
            if not isinstance(member, dict) or not member.get("name"):
                continue
            role = member.get("character")
            episodes = member.get("episodeCount")
            suffix = f" ({episodes} episodes)" if is_tv and episodes else ""
            rows.append(f"- {member['name']}" + (f" as {role}" if role else "") + suffix)
        total = data.get("castCount")
        if total and len(rows) < total:
            rows.append(f"- ...and {total - len(rows)} more credited cast members")
        _section(lines, "Cast", rows)

    money = _facts([
        ("Budget", _fmt_money(data.get("budgetUsd"))),
        ("Revenue", _fmt_money(data.get("revenueUsd"))),
        ("Profit", _fmt_money(data.get("profitUsd"))),
        ("Return on budget", f"{data['returnOnBudget']}x" if data.get("returnOnBudget") else None),
    ])
    _section(lines, "Box office", money)

    providers = data.get("watchProviders") or {}
    if isinstance(providers, dict) and providers.get("watchRegion"):
        watch = _facts([
            ("Streaming", _join(providers.get("streamingOn"))),
            ("Free with ads", _join(providers.get("freeWithAdsOn"))),
            ("Rent", _join(providers.get("rentFrom"))),
            ("Buy", _join(providers.get("buyFrom"))),
        ])
        _section(lines, f"Where to watch ({providers['watchRegion']})", watch)

    if is_tv and isinstance(data.get("seasons"), list) and data["seasons"]:
        rows = []
        for season in data["seasons"]:
            if not isinstance(season, dict):
                continue
            label = season.get("name") or f"Season {season.get('seasonNumber')}"
            bits = [b for b in (
                f"{season.get('episodeCount')} episodes" if season.get("episodeCount") else None,
                season.get("airDate"),
            ) if b]
            rows.append(f"- **{label}**" + (f" - {', '.join(bits)}" if bits else ""))
        _section(lines, "Seasons", rows)

    if data.get("keywords"):
        _section(lines, "Keywords", [_join(data["keywords"], 30) or ""])

    if data.get("trailerUrl"):
        _section(lines, "Trailer", [data["trailerUrl"]])

    return "\n".join(lines).strip() + "\n"


# -- people ----------------------------------------------------------------

def person_markdown(data: dict[str, Any]) -> str:
    name = data.get("name") or "Unknown person"
    lines: list[str] = [f"# {name}", ""]

    lifespan = None
    if data.get("birthday"):
        lifespan = data["birthday"]
        if data.get("deathday"):
            lifespan += f" - {data['deathday']}"

    lines += _facts([
        ("Known for", data.get("knownForDepartment")),
        ("Born", lifespan),
        ("Age at death" if data.get("deathday") else "Age", data.get("age")),
        ("Place of birth", data.get("placeOfBirth")),
        ("Gender", data.get("gender") if data.get("gender") != "unknown" else None),
        ("Also known as", _join(data.get("alsoKnownAs"), 5)),
        ("Acting credits", data.get("actingCreditCount")),
        ("Crew credits", data.get("crewCreditCount")),
        ("IMDb", data.get("imdbId")),
        ("TMDB", data.get("tmdbUrl")),
        ("Homepage", data.get("homepage")),
        ("Instagram", data.get("instagramUrl")),
        ("X / Twitter", data.get("twitterUrl")),
    ]) + [""]

    if data.get("biography"):
        _section(lines, "Biography", [data["biography"]])

    credits = data.get("filmography")
    if isinstance(credits, list) and credits:
        acting = [c for c in credits if isinstance(c, dict) and c.get("creditKind") == "cast"]
        crew = [c for c in credits if isinstance(c, dict) and c.get("creditKind") == "crew"]
        _section(lines, "Filmography - acting", _credit_rows(acting))
        _section(lines, "Filmography - crew", _credit_rows(crew))
    return "\n".join(lines).strip() + "\n"


def _credit_rows(credits: list[dict[str, Any]]) -> list[str]:
    rows = []
    for credit in credits:
        title = credit.get("title")
        if not title:
            continue
        year = credit.get("year")
        role = credit.get("character") or credit.get("job")
        episodes = credit.get("episodeCount")
        line = f"- **{title}**" + (f" ({year})" if year else "")
        if role:
            line += f" - {role}"
        if episodes and episodes > 1:
            line += f", {episodes} episodes"
        rows.append(line)
    return rows


# -- episodes, reviews, and the thin shapes -------------------------------

def episode_markdown(data: dict[str, Any]) -> str:
    series = data.get("seriesName") or "Unknown series"
    code = data.get("episodeCode") or (
        f"S{data.get('seasonNumber')}E{data.get('episodeNumber')}"
    )
    name = data.get("name") or "Untitled episode"
    lines = [f"# {series} - {code}: {name}", ""]
    lines += _facts([
        ("Series", series),
        ("Season", data.get("seasonNumber")),
        ("Episode", data.get("episodeNumber")),
        ("Aired", data.get("airDate")),
        ("Runtime", _fmt_runtime(data.get("runtimeMins"))),
        ("Rating", _rating_line(data)),
        ("Type", data.get("episodeType")),
        ("Directed by", _join(data.get("directors"))),
        ("Written by", _join(data.get("writers"), 6)),
        ("TMDB", data.get("tmdbUrl")),
    ]) + [""]
    if data.get("overview"):
        _section(lines, "Synopsis", [data["overview"]])
    guests = data.get("guestStars")
    if isinstance(guests, list) and guests:
        _section(lines, "Guest stars", [
            f"- {g['name']}" + (f" as {g['character']}" if g.get("character") else "")
            for g in guests if isinstance(g, dict) and g.get("name")
        ])
    return "\n".join(lines).strip() + "\n"


def review_markdown(data: dict[str, Any]) -> str:
    parent = data.get("parentTitle") or "Unknown title"
    author = data.get("author") or "anonymous"
    lines = [f"# Review of {parent} by {author}", ""]
    lines += _facts([
        ("Title reviewed", parent),
        ("Author", author),
        ("Author rating", f"{data['authorRating']}/10" if data.get("authorRating") else None),
        ("Written", str(data.get("createdAt") or "")[:10] or None),
        ("Length", f"{data['contentLength']} characters" if data.get("contentLength") else None),
        ("Source", data.get("url")),
    ]) + [""]
    if data.get("content"):
        _section(lines, "Review", [data["content"]])
    return "\n".join(lines).strip() + "\n"


def list_entry_markdown(data: dict[str, Any]) -> str:
    if data.get("mediaType") == "person":
        lines = [f"# {data.get('name') or 'Unknown person'}", ""]
        lines += _facts([
            ("Known for department", data.get("knownForDepartment")),
            ("Known for", _join(data.get("knownFor"))),
            ("Popularity", data.get("popularity")),
            ("TMDB", data.get("tmdbUrl")),
        ])
        return "\n".join(lines).strip() + "\n"
    name = data.get("title") or "Untitled"
    year = data.get("year")
    lines = [f"# {name}" + (f" ({year})" if year else ""), ""]
    lines += _facts([
        ("Type", "TV series" if data.get("mediaType") == "tv" else "Movie"),
        ("Released", data.get("releaseDate")),
        ("Rating", _rating_line(data)),
        ("Original language", data.get("originalLanguage")),
        ("TMDB", data.get("tmdbUrl")),
    ]) + [""]
    if data.get("overview"):
        _section(lines, "Overview", [data["overview"]])
    return "\n".join(lines).strip() + "\n"


def collection_markdown(data: dict[str, Any]) -> str:
    lines = [f"# {data.get('name') or 'Collection'}", ""]
    lines += _facts([
        ("Films in collection", data.get("partCount")),
        ("TMDB", data.get("tmdbUrl")),
    ]) + [""]
    if data.get("overview"):
        _section(lines, "Overview", [data["overview"]])
    parts = data.get("parts")
    if isinstance(parts, list) and parts:
        _section(lines, "Films", [
            f"- **{p.get('title')}**"
            + (f" ({p.get('year')})" if p.get("year") else "")
            + (f" - {round(float(p['voteAverage']), 1)}/10" if p.get("voteAverage") else "")
            for p in parts if isinstance(p, dict) and p.get("title")
        ])
    return "\n".join(lines).strip() + "\n"


def company_markdown(data: dict[str, Any]) -> str:
    lines = [f"# {data.get('name') or 'Company'}", ""]
    lines += _facts([
        ("Type", "TV network" if data.get("mediaType") == "network" else "Production company"),
        ("Country", data.get("originCountry")),
        ("Headquarters", data.get("headquarters")),
        ("Parent company", data.get("parentCompany")),
        ("Homepage", data.get("homepage")),
        ("TMDB", data.get("tmdbUrl")),
    ]) + [""]
    if data.get("description"):
        _section(lines, "About", [data["description"]])
    return "\n".join(lines).strip() + "\n"


RENDERERS = {
    "title": title_markdown,
    "person": person_markdown,
    "episode": episode_markdown,
    "season": list_entry_markdown,
    "review": review_markdown,
    "search_result": list_entry_markdown,
    "discover_result": list_entry_markdown,
    "chart_entry": list_entry_markdown,
    "collection": collection_markdown,
    "company": company_markdown,
}


def render(item_type: str, data: dict[str, Any]) -> str | None:
    """Render a record body, or None when this item type has no document form.

    Diagnostic rows deliberately have none: a run that writes an error row into
    a RAG corpus as prose has just taught someone's index that "no results" is
    a fact about a film.
    """
    renderer = RENDERERS.get(item_type)
    if renderer is None:
        return None
    try:
        return renderer(data)
    except Exception:  # noqa: BLE001 - a formatting slip must not lose the row
        return None
