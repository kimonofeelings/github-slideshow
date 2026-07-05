"""
Live in-match predictions: re-simulate from the real current state.

While a match is in progress, the live score and elapsed time replace
the kickoff assumptions: the rest of regulation is simulated at each
side's remaining-time goal rate (same player/conditions-derived lambdas
as pre-match), then extra time and penalties as usual. Output is the
updated advancement probability given what has actually happened.

`run_live_update()` is the one-shot entry used by scheduled polls:
fetch state -> simulate -> WhatsApp. On full time it grades the
pre-match prediction immediately and texts the verdict.
"""

from datetime import datetime, timezone

import numpy as np

from .matchup import forecast_match
from .simulator import _penalty_shootout_prob, ET_RATE


def minutes_left_from_kickoff(kickoff_utc, now=None):
    """Regulation minutes remaining, estimated from the clock:
    kickoff + 45' + 15' halftime + 45' (+ stoppage absorbed by capping)."""
    try:
        ko = datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
        ko = ko.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None
    now = now or datetime.utcnow()
    elapsed = (now - ko).total_seconds() / 60.0
    if elapsed <= 0:
        return 90.0
    if elapsed <= 45:
        played = elapsed
    elif elapsed <= 62:            # halftime + first-half stoppage
        played = 45.0
    else:
        played = min(45.0 + (elapsed - 62), 90.0)
    return max(0.0, 90.0 - played)


def simulate_inplay(team_a, team_b, score_a, score_b, minutes_left,
                    context=None, n_sims=1_000_000, seed=42):
    """Advancement probabilities conditioned on the current score."""
    fc = forecast_match(team_a, team_b, context=context)
    rng = np.random.default_rng(seed)
    frac = max(minutes_left, 0.0) / 90.0
    fin_a = score_a + rng.poisson(fc.home.lam * frac, n_sims)
    fin_b = score_b + rng.poisson(fc.away.lam * frac, n_sims)

    adv_a = fin_a > fin_b
    level = fin_a == fin_b
    n_level = int(level.sum())
    p_et = n_level / n_sims
    p_pens = 0.0
    if n_level:
        et_a = rng.poisson(fc.home.lam * ET_RATE, n_level)
        et_b = rng.poisson(fc.away.lam * ET_RATE, n_level)
        after_a, after_b = et_a, et_b
        still = after_a == after_b
        p_pens = still.sum() / n_sims
        adv_a[level] = after_a > after_b
        idx = np.where(level)[0][still]
        if len(idx):
            p_a = _penalty_shootout_prob(team_a, team_b)
            adv_a[idx] = rng.random(len(idx)) < p_a

    # most likely FT (90') scorelines from here
    cap = 6
    grid = np.zeros((cap + 1, cap + 1))
    np.add.at(grid, (np.minimum(fin_a, cap), np.minimum(fin_b, cap)), 1)
    grid /= n_sims
    flat = sorted(((h, a, grid[h, a]) for h in range(cap + 1)
                   for a in range(cap + 1) if grid[h, a] > 0),
                  key=lambda t: t[2], reverse=True)

    return {"p_advance_a": float(adv_a.mean()),
            "p_advance_b": float(1 - adv_a.mean()),
            "p_extra_time": float(p_et), "p_penalties": float(p_pens),
            "exp_final_a": float(fin_a.mean()),
            "exp_final_b": float(fin_b.mean()),
            "top_finals": flat[:3]}


def build_live_message(team_a, team_b, state, sim, minutes_left):
    from .notify import FLAGS
    fa, fb = FLAGS.get(team_a.code, ""), FLAGS.get(team_b.code, "")
    mins = f"~{90 - minutes_left:.0f}'" if minutes_left is not None else ""
    lines = [
        f"\U0001F534 *LIVE {mins}*  {fa} {team_a.name} "
        f"*{state['home_goals']}-{state['away_goals']}* {team_b.name} {fb}",
    ]
    lead = team_a if sim["p_advance_a"] >= 0.5 else team_b
    p = max(sim["p_advance_a"], sim["p_advance_b"])
    lines.append(f"\U0001F52E *{lead.name} to advance: {p:.0%}*")
    if sim["p_extra_time"] > 0.05:
        lines.append(f"⏱ Extra time {sim['p_extra_time']:.0%}  |  "
                     f"pens {sim['p_penalties']:.0%}")
    tops = "  |  ".join(f"{h}-{a} ({pr:.0%})"
                        for h, a, pr in sim["top_finals"])
    lines.append(f"\U0001F3AF Likely final: {tops}")
    return "\n".join(lines)


def build_ft_message(team_a, team_b, state, learn_notes, record):
    from .notify import FLAGS
    fa, fb = FLAGS.get(team_a.code, ""), FLAGS.get(team_b.code, "")
    lines = [
        f"\U0001F3C1 *FULL TIME*  {fa} {team_a.name} "
        f"*{state['home_goals']}-{state['away_goals']}* {team_b.name} {fb}",
    ]
    for n in learn_notes:
        lines.append(f"\U0001F9E0 {n}")
    lines.append(f"\U0001F4C8 {record}")
    return "\n".join(lines)


def run_live_update(home_code, away_code, n_sims=1_000_000):
    """One poll: fetch real state, simulate, send. Returns a status
    string: 'live-sent', 'ft-sent', 'not-started', 'already-graded',
    'no-data', or an error description."""
    from .data.worldcup2026 import get_team, get_context
    from .live.fixtures import fetch_live_state
    from .notify import send_sms
    from . import learn

    a, b = get_team(home_code), get_team(away_code)
    state = fetch_live_state(a.name, b.name)
    if state is None:
        return "no-data"

    if state["finished"]:
        if learn.is_settled(a.code, b.code):
            return "already-graded"
        notes = learn.update_from_results()
        msg = build_ft_message(a, b, state, notes, learn.record_line())
        ok, prov, detail = send_sms(_phone(), msg)
        return "ft-sent" if ok else f"ft-send-failed: {detail}"

    if not state["live"]:
        return "not-started"

    minutes_left = minutes_left_from_kickoff(state.get("kickoff_utc")) or 30.0
    ctx = get_context(home_code, away_code)
    sim = simulate_inplay(a, b, state["home_goals"], state["away_goals"],
                          minutes_left, context=ctx, n_sims=n_sims)
    msg = build_live_message(a, b, state, sim, minutes_left)
    ok, prov, detail = send_sms(_phone(), msg)
    return "live-sent" if ok else f"live-send-failed: {detail}"


def _phone():
    import os
    phone = os.environ.get("PREDICTOR_PHONE", "")
    if phone:
        return phone
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "phone.txt")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return ""
