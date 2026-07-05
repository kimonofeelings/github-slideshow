"""Real-time match state via ESPN's public scoreboard API (keyless).

TheSportsDB's free tier only refreshes scores at full time - useless
mid-match. ESPN's scoreboard updates live and carries the actual match
clock ("67'", "90'+11'"), halftime state, and pre/in/post status, so
in-play updates can be conditioned on the true score and minute.
"""

import re

from .http import get_json

SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/soccer/"
              "fifa.world/scoreboard")


def fetch_live_state(home_name, away_name):
    """Live state in the caller's team order, or None if unavailable.
    Returns dict(home_goals, away_goals, live, finished, minute,
    halftime, detail)."""
    data = get_json(SCOREBOARD, ttl=60)
    if not data:
        return None
    want = {home_name.lower(), away_name.lower()}
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        if "home" not in sides or "away" not in sides:
            continue
        h, a = sides["home"], sides["away"]
        names = {h["team"]["displayName"].lower(),
                 a["team"]["displayName"].lower()}
        if names != want:
            continue
        gh = int(h.get("score") or 0)
        ga = int(a.get("score") or 0)
        if h["team"]["displayName"].lower() != home_name.lower():
            gh, ga = ga, gh
        st = ev.get("status", {})
        state = st.get("type", {}).get("state", "")
        detail = st.get("type", {}).get("shortDetail", "") or ""
        m = re.match(r"(\d+)", st.get("displayClock") or "")
        return {
            "home_goals": gh, "away_goals": ga,
            "live": state == "in", "finished": state == "post",
            "minute": int(m.group(1)) if m else None,
            "halftime": detail.strip().upper() == "HT",
            "detail": detail,
        }
    return None
