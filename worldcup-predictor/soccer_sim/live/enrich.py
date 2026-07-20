"""Merge live data into a MatchContext, with graceful degradation.

Layering, most-trusted first:
  1. TheSportsDB          -> real fixture: date, venue, round      (keyless)
  2. Venue database       -> coordinates, altitude, roof           (shipped)
  3. Open-Meteo           -> kickoff-hour weather at the stadium   (keyless)
  4. football-data.org    -> squad cross-check          (FOOTBALL_DATA_TOKEN)
  5. API-Football         -> injury list -> player status  (APIFOOTBALL_KEY)

Anything unavailable simply keeps the hand-curated value from CONTEXTS,
and every change is reported as a note so the report shows exactly what
came from live sources.
"""

import os
import unicodedata
from dataclasses import replace
from datetime import datetime, timezone

from ..context import MatchContext
from ..models import OUT
from .fixtures import fetch_fixture
from .venues import find_venue
from .weather import fetch_weather
from .http import get_json

GEOCODE = ("https://geocoding-api.open-meteo.com/v1/search"
           "?name={name}&count=1")


def _geocode(city):
    data = get_json(GEOCODE.format(name=city.replace(" ", "+")), ttl=86400)
    hits = (data or {}).get("results") or []
    if hits:
        return {"lat": hits[0]["latitude"], "lon": hits[0]["longitude"],
                "altitude_m": int(hits[0].get("elevation") or 0),
                "roof": None, "city": city}
    return None


def live_context(home_team, away_team, base=None):
    """Returns (MatchContext, notes). Starts from the curated `base`
    context and overrides whatever live sources can confirm."""
    ctx = replace(base) if base is not None else MatchContext()
    notes = []

    # 1) confirm the real fixture: date, venue, round
    fx = fetch_fixture(home_team.name, away_team.name)
    if fx is None:
        notes.append("fixture: NOT FOUND live - using curated venue")
    else:
        notes.append(f"fixture: {fx['event']} on {fx['date']}"
                     f" at {fx['venue']} (round {fx['round']})")
        if fx["venue"]:
            ctx.venue = fx["venue"]
        if fx["city"]:
            ctx.city = fx["city"]
        if fx["kickoff_utc"]:
            ctx.kickoff_local = fx["kickoff_utc"][:16].replace("T", " ") + " UTC"

    # 2) venue facts: coordinates, altitude, roof
    vinfo = find_venue(ctx.venue) or (_geocode(ctx.city) if ctx.city else None)
    if vinfo:
        if vinfo.get("altitude_m") is not None:
            if abs(vinfo["altitude_m"] - ctx.altitude_m) > 25:
                notes.append(f"venue: altitude {ctx.altitude_m}m -> "
                             f"{vinfo['altitude_m']}m")
            ctx.altitude_m = vinfo["altitude_m"]
        if vinfo.get("roof") is not None and vinfo["roof"] != ctx.roof_closed:
            ctx.roof_closed = vinfo["roof"]
            notes.append(f"venue: roof {'closed' if vinfo['roof'] else 'open'}")
        if vinfo.get("city"):
            ctx.city = vinfo["city"]

        # 3) weather at the stadium for the kickoff hour
        kickoff = fx["kickoff_utc"] if fx else None
        wx = fetch_weather(vinfo["lat"], vinfo["lon"], kickoff)
        if wx is None:
            notes.append("weather: UNAVAILABLE - using curated estimates")
        else:
            ctx.temp_c = wx["temp_c"]
            ctx.humidity = wx["humidity"]
            ctx.rain = wx["rain"]
            ctx.wind_kmh = wx["wind_kmh"]
            notes.append(f"weather: {wx['temp_c']:.0f}C, "
                         f"{wx['humidity']:.0%} humidity, "
                         f"wind {wx['wind_kmh']:.0f} km/h, "
                         f"rain {wx['rain']:.0%} ({wx['when']})")
    else:
        notes.append(f"venue: '{ctx.venue}' unknown - keeping curated facts")

    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return ctx, notes, fetched


# ---------------------------------------------------------------------------
# Optional premium squad news (needs free API keys via environment vars).
# ---------------------------------------------------------------------------
def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().replace(".", "").replace("-", " ")


def _surname(name):
    return _norm(name).split()[-1]


def apply_squad_news(team, notes):
    """If APIFOOTBALL_KEY is set, pull the live injury list and flip
    matching players to OUT. Matching is by surname, conservatively."""
    key = os.environ.get("APIFOOTBALL_KEY")
    if not key:
        notes.append(f"injuries {team.code}: skipped (set APIFOOTBALL_KEY "
                     "for live squad news)")
        return
    url = ("https://v3.football.api-sports.io/injuries"
           f"?league=1&season=2026&team={team.code}")
    data = get_json(url, ttl=3600, headers={"x-apisports-key": key})
    if not data or data.get("errors"):
        notes.append(f"injuries {team.code}: API error - statuses unchanged")
        return
    injured = {_surname(item["player"]["name"])
               for item in data.get("response", [])
               if item.get("player", {}).get("name")}
    hits = []
    for p in team.players:
        if _surname(p.name) in injured and p.status != OUT:
            p.status = OUT
            hits.append(p.name)
    notes.append(f"injuries {team.code}: "
                 + (", ".join(hits) + " -> OUT" if hits else "no new injuries"))
