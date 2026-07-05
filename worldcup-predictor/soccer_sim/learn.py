"""
Self-improving calibration: learn from every finished match.

Each prediction run records its pre-match forecast. Once the real
result is available (fetched live from TheSportsDB), the prediction is
scored - winner called or not, Brier score, goal error - and per-team
adjustment factors get nudged:

  * a team that outscores its expected goals earns an attack boost;
    one that underdelivers gets docked
  * a defense that concedes more than predicted is marked leakier;
    one that holds firm is marked tighter

Adjustments are small (max ~6% per match), multiplicative, clamped to
[0.85, 1.18], and fully transparent: model_state.json holds every
prediction, result, score, and adjustment ever made, and the daily
message shows the running record. Deliberately simple, explainable
online learning - not a black box.
"""

import json
import os
from datetime import datetime, timezone

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "model_state.json")

LEARN_RATE = 0.06        # max fractional nudge per factor per match
ADJ_CLAMP = (0.85, 1.18)
MIN_ERR = 0.15           # ignore noise: goal error below this learns nothing

_cache = {"mtime": None, "state": None}


def _blank():
    return {"predictions": [], "team_adj": {},
            "record": {"matches": 0, "winners_called": 0, "brier_sum": 0.0},
            "history": []}


def load_state():
    try:
        mtime = os.path.getmtime(STATE_PATH)
        if _cache["mtime"] == mtime and _cache["state"] is not None:
            return _cache["state"]
        with open(STATE_PATH) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return _blank()
    _cache.update(mtime=mtime, state=state)
    return state


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=1)
    _cache.update(mtime=os.path.getmtime(STATE_PATH), state=state)


def team_adjustments():
    """{code: {"attack": x, "leak": y}} - consumed by the matchup engine.
    attack scales the team's own expected goals; leak scales what its
    opponents are expected to score against it."""
    return load_state().get("team_adj", {})


def is_settled(home_code, away_code):
    return any(p["home"] == home_code and p["away"] == away_code
               and p["settled"] for p in load_state()["predictions"])


def record_prediction(res):
    """Store/refresh the pre-match forecast so it can be scored later.
    A prediction that has already been scored is never overwritten."""
    fc = res.forecast
    state = load_state()
    entry = {
        "home": fc.home.team.code, "away": fc.away.team.code,
        "home_name": fc.home.team.name, "away_name": fc.away.team.name,
        "p_home_advance": round(res.p_home_advance, 4),
        "lam_home": round(fc.home.lam, 3), "lam_away": round(fc.away.lam, 3),
        "recorded": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "settled": False,
    }
    preds = state["predictions"]
    for i, p in enumerate(preds):
        if p["home"] == entry["home"] and p["away"] == entry["away"]:
            if p["settled"]:
                return
            preds[i] = entry
            break
    else:
        preds.append(entry)
    save_state(state)


def _nudge(state, code, factor, err):
    adj = state["team_adj"].setdefault(code, {"attack": 1.0, "leak": 1.0})
    lo, hi = ADJ_CLAMP
    adj[factor] = round(max(lo, min(hi, adj[factor] * (1 + LEARN_RATE * err))), 4)


def update_from_results():
    """Fetch real scores for unsettled predictions and learn from each.
    Returns human-readable notes about what was scored and adjusted."""
    from .live.fixtures import fetch_result
    state = load_state()
    notes = []
    for p in state["predictions"]:
        if p["settled"]:
            continue
        result = fetch_result(p["home_name"], p["away_name"])
        if not result or not result["finished"]:
            continue
        gh, ga = result["home_goals"], result["away_goals"]

        # -- score the winner call (a level score after ET can't tell us
        #    who won the shootout, so only decisive scorelines count)
        called = brier = None
        if gh != ga:
            actual = 1.0 if gh > ga else 0.0
            brier = round((p["p_home_advance"] - actual) ** 2, 4)
            called = (p["p_home_advance"] >= 0.5) == (actual == 1.0)
            state["record"]["matches"] += 1
            state["record"]["winners_called"] += int(called)
            state["record"]["brier_sum"] += brier

        # -- learn from goal errors on both sides
        learned = []
        for code, opp, lam, actual_g in (
                (p["home"], p["away"], p["lam_home"], gh),
                (p["away"], p["home"], p["lam_away"], ga)):
            err = (actual_g - lam) / max(lam, 0.75)
            err = max(-1.0, min(1.0, err))
            if abs(err) >= MIN_ERR:
                _nudge(state, code, "attack", err)
                _nudge(state, opp, "leak", err)
                learned.append(
                    f"{code} attack {'+' if err > 0 else '-'}"
                    f"{abs(LEARN_RATE * err):.0%} "
                    f"(scored {actual_g} vs {lam:.1f} expected); "
                    f"{opp} defense {'leakier' if err > 0 else 'tighter'}")

        p["settled"] = True
        p["result"] = f"{gh}-{ga}"
        p["called"] = called
        p["brier"] = brier
        state["history"].append({
            "match": f"{p['home']} {gh}-{ga} {p['away']}",
            "predicted_home": p["p_home_advance"],
            "called": called, "brier": brier, "learned": learned,
        })
        verdict = ("✓ called it" if called
                   else "✗ missed" if called is not None
                   else "level - shootout, winner not scored")
        notes.append(f"{p['home']} {gh}-{ga} {p['away']}: {verdict}"
                     + (f"; {'; '.join(learned)}" if learned else ""))
    save_state(state)
    return notes


def record_line():
    """One-line running accuracy summary for reports and texts."""
    r = load_state()["record"]
    if not r["matches"]:
        return "Model record: first scored match still pending"
    avg = r["brier_sum"] / r["matches"]
    return (f"Model record: {r['winners_called']}/{r['matches']} winners "
            f"called | avg Brier {avg:.2f} (0=perfect, 0.25=coin flip)")
