"""
Full-tournament projection: exact title odds for every surviving team.

The remaining bracket (resolved from the official schedule on Jul 6):

  R16 g5  POR vs ESP          QF3 (Jul 10)  W(g5) vs W(g6)
  R16 g6  USA vs BEL          QF4 (Jul 12)  W(g7) vs W(g8)
  R16 g7  ARG vs EGY          QF1 (Jul 9)   FRA vs MAR   (R16 done Jul 4)
  R16 g8  SUI vs COL          QF2 (Jul 11)  NOR vs ENG   (R16 done Jul 5)
  SF1 (Jul 14)  W(QF1) vs W(QF2)      SF2 (Jul 15)  W(QF3) vs W(QF4)
  FINAL (Jul 19)

Pairwise advancement probabilities are computed EXACTLY from the match
engine's Dixon-Coles scoreline grid (90' + extra-time grid + shootout
model), then the bracket is solved by dynamic programming - no Monte
Carlo noise. Learned adjustments and current form flow in
automatically because the grid comes from the live forecast.

As matches finish, learn.py settles them and this module re-resolves:
played rounds contribute probability 1 to their real winner.
"""

import numpy as np

from .matchup import forecast_match
from .simulator import scoreline_grid, _penalty_shootout_prob, ET_RATE

# (slot_name, [participants or slot refs]) - resolved winners replace slots
R16_GAMES = {
    "g5": ("POR", "ESP"), "g6": ("USA", "BEL"),
    "g7": ("ARG", "EGY"), "g8": ("SUI", "COL"),
}
QF_GAMES = {
    "qf1": ("FRA", "MAR"),           # R16 winners, already through
    "qf2": ("NOR", "ENG"),
    "qf3": ("g5", "g6"),
    "qf4": ("g7", "g8"),
}
SF_GAMES = {"sf1": ("qf1", "qf2"), "sf2": ("qf3", "qf4")}
FINAL = ("sf1", "sf2")


def advance_prob(team_a, team_b):
    """Exact P(A advances) for a knockout tie: DC 90' grid, independent
    Poisson extra-time grid, shootout model for still-level games."""
    fc = forecast_match(team_a, team_b)
    la, lb = fc.home.lam, fc.away.lam
    g = scoreline_grid(la, lb)
    p_win90 = float(np.tril(g, -1).sum())      # rows = home goals
    p_draw90 = float(np.trace(g))

    ea, eb = la * ET_RATE, lb * ET_RATE
    k = np.arange(7)
    fact = np.array([1, 1, 2, 6, 24, 120, 720], dtype=float)
    pa = np.exp(-ea) * ea ** k / fact
    pb = np.exp(-eb) * eb ** k / fact
    et = np.outer(pa, pb)
    et /= et.sum()
    p_win_et = float(np.tril(et, -1).sum())
    p_draw_et = float(np.trace(et))

    p_pens = _penalty_shootout_prob(team_a, team_b)
    return p_win90 + p_draw90 * (p_win_et + p_draw_et * p_pens)


def _resolve(ref, teams, pair_cache, settled):
    """Distribution {team_code: P(wins this slot)} for any bracket ref:
    a concrete team code, an r16/qf/sf slot name, or 'final'."""
    slots = {**R16_GAMES, **QF_GAMES, **SF_GAMES, "final": FINAL}
    if ref not in slots:
        return {ref: 1.0}                       # concrete team code
    a_ref, b_ref = slots[ref]
    da = _resolve(a_ref, teams, pair_cache, settled)
    db = _resolve(b_ref, teams, pair_cache, settled)

    out = {}
    for x, px in da.items():
        for y, py in db.items():
            key = frozenset((x, y))
            if key in settled:                   # real result: fact
                w = settled[key]
                out[w] = out.get(w, 0.0) + px * py
                continue
            k = (x, y)
            if k not in pair_cache:
                pair_cache[k] = advance_prob(teams[x], teams[y])
                pair_cache[(y, x)] = 1.0 - pair_cache[k]
            out[x] = out.get(x, 0.0) + px * py * pair_cache[k]
            out[y] = out.get(y, 0.0) + px * py * (1.0 - pair_cache[k])
    return out


def title_odds():
    """{code: P(champion)}, exact given the pairwise model probabilities.
    Already-played ties (recorded by the learning ledger) count as fact."""
    from . import learn
    from .data.worldcup2026 import TEAMS

    settled = {}
    for p in learn.load_state()["predictions"]:
        if p.get("settled") and p.get("result"):
            gh, ga = map(int, p["result"].split("-"))
            if gh != ga:
                settled[frozenset((p["home"], p["away"]))] = (
                    p["home"] if gh > ga else p["away"])

    pair_cache = {}
    dist = _resolve("final", TEAMS, pair_cache, settled)
    total = sum(dist.values())
    return {k: v / total for k, v in
            sorted(dist.items(), key=lambda kv: -kv[1])}


def title_message():
    from .notify import FLAGS
    odds = title_odds()
    lines = ["\U0001F3C6 *WORLD CUP TITLE ODDS* (model projection)"]
    for code, p in odds.items():
        if p < 0.005:
            continue
        lines.append(f"{FLAGS.get(code, '')} {code}  {p:.1%}")
    lines.append("_Exact bracket math over every remaining path - "
                 "updates as results land_")
    return "\n".join(lines)
