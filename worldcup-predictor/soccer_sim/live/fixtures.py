"""Live fixture lookup via TheSportsDB (free tier, keyless).

Confirms the real date, venue, and round for a pairing — which matters:
tournament schedules move, and the venue drives altitude, roof, and
weather. Searches both orderings and filters to FIFA World Cup events
in the current season.
"""

from .http import get_json

SEARCH = "https://www.thesportsdb.com/api/v1/json/3/searchevents.php?e={a}_vs_{b}"


def _slug(name):
    return name.strip().replace(" ", "_")


def fetch_fixture(home_name, away_name, season="2026"):
    """Returns dict(event, date, kickoff_utc, venue, city, round, swapped)
    or None if no matching World Cup fixture is found / API unreachable.
    `swapped` is True when the official listing has the teams reversed."""
    for a, b, swapped in ((home_name, away_name, False),
                          (away_name, home_name, True)):
        data = get_json(SEARCH.format(a=_slug(a), b=_slug(b)), ttl=6 * 3600)
        for ev in (data or {}).get("event") or []:
            if "world cup" not in (ev.get("strLeague") or "").lower():
                continue
            if season and ev.get("strSeason") not in (season, None, ""):
                continue
            return {
                "event": ev.get("strEvent"),
                "date": ev.get("dateEvent"),
                "kickoff_utc": ev.get("strTimestamp"),
                "venue": ev.get("strVenue"),
                "city": (ev.get("strCity") or "").split(",")[0].strip(),
                "round": ev.get("intRound"),
                "swapped": swapped,
            }
    return None
