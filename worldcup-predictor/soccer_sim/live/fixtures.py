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


FINISHED_STATUSES = {"match finished", "ft", "aet", "pen", "finished"}


def fetch_result(home_name, away_name, season="2026"):
    """Final score for a played fixture, in the caller's team order.
    Returns dict(home_goals, away_goals, finished) or None. Scores can
    appear mid-match, so `finished` gates on the status field."""
    for a, b, swapped in ((home_name, away_name, False),
                          (away_name, home_name, True)):
        data = get_json(SEARCH.format(a=_slug(a), b=_slug(b)), ttl=900)
        for ev in (data or {}).get("event") or []:
            if "world cup" not in (ev.get("strLeague") or "").lower():
                continue
            if season and ev.get("strSeason") not in (season, None, ""):
                continue
            hs, as_ = ev.get("intHomeScore"), ev.get("intAwayScore")
            if hs is None or as_ is None:
                return None
            gh, ga = int(hs), int(as_)
            if swapped:
                gh, ga = ga, gh
            status = (ev.get("strStatus") or "").strip().lower()
            return {"home_goals": gh, "away_goals": ga,
                    "finished": status in FINISHED_STATUSES}
    return None
