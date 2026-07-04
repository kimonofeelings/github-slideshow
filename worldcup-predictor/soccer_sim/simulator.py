"""
Monte Carlo match simulator (fully vectorized with numpy).

For each of N simulated matches:
  1. Draw 90-minute goal counts for each team from Poisson(lambda),
     where lambda comes from the player-matchup engine.
  2. Assign every goal to a specific scorer via a multinomial draw over
     player scoring weights (position, finishing, minutes, form, pens).
  3. Knockout mode: level games go to 30' of extra time (reduced-rate
     Poisson), then a penalty shootout decided by penalty-taking quality
     vs the opposing keeper.

100,000 simulations run in ~1s.
"""

from dataclasses import dataclass, field
import numpy as np

from .matchup import forecast_match, MatchForecast

# Goal-scoring likelihood by position (per unit of attack rating).
POSITION_GOAL_MULT = {
    "ST": 1.35, "LW": 1.05, "RW": 1.05, "AM": 0.95,
    "CM": 0.55, "DM": 0.35, "CB": 0.30, "LB": 0.28, "RB": 0.28, "GK": 0.01,
}

ET_RATE = (30.0 / 90.0) * 0.90     # extra time: shorter + more cautious


# ---------------------------------------------------------------------------
def scorer_weights(team):
    """Probability that a given team goal is scored by each player."""
    players = team.outfield()
    w = np.zeros(len(players))
    for i, p in enumerate(players):
        base = (p.attack ** 1.7) * POSITION_GOAL_MULT[p.position]
        base *= p.minutes_share * p.form * p.fitness
        if p.pen_rank == 1:
            base *= 1.14          # first-choice pens ~= extra goal share
        elif p.pen_rank == 2:
            base *= 1.05
        w[i] = base
    total = w.sum()
    return players, (w / total if total > 0 else np.full(len(w), 1 / len(w)))


def _distribute_goals(goal_counts, probs, rng):
    """Vectorized multinomial: split each sim's goal count across players."""
    n_sims, n_players = len(goal_counts), len(probs)
    out = np.zeros((n_sims, n_players), dtype=np.uint8)
    for g in range(1, int(goal_counts.max()) + 1 if goal_counts.max() > 0 else 1):
        idx = np.where(goal_counts == g)[0]
        if len(idx):
            out[idx] = rng.multinomial(g, probs, size=len(idx))
    return out


def _penalty_shootout_prob(team_a, team_b):
    """P(team A wins a shootout) from taker quality + keepers."""
    def side_score(team, opp_gk):
        takers = sorted(team.outfield(), key=lambda p: p.attack, reverse=True)[:5]
        shoot = np.mean([p.attack * p.form * p.fitness for p in takers])
        own_gk = team.keeper()
        save = own_gk.defense * own_gk.form * own_gk.fitness
        return 0.65 * shoot + 0.35 * save
    a = side_score(team_a, team_b.keeper())
    b = side_score(team_b, team_a.keeper())
    return 1.0 / (1.0 + np.exp(-(a - b) / 6.0))


# ---------------------------------------------------------------------------
@dataclass
class SimulationResult:
    forecast: MatchForecast
    n_sims: int
    knockout: bool
    # 90-minute outcomes
    p_home_win: float = 0.0
    p_draw: float = 0.0
    p_away_win: float = 0.0
    avg_goals_home: float = 0.0        # includes ET goals when knockout
    avg_goals_away: float = 0.0
    avg_goals_home_90: float = 0.0
    avg_goals_away_90: float = 0.0
    p_over_2_5: float = 0.0
    p_btts: float = 0.0
    top_scorelines: list = field(default_factory=list)   # [(h, a, prob)]
    # knockout resolution
    p_home_advance: float = 0.0
    p_away_advance: float = 0.0
    p_extra_time: float = 0.0
    p_penalties: float = 0.0
    # scorer stats: list of dicts per player
    scorers_home: list = field(default_factory=list)
    scorers_away: list = field(default_factory=list)


def simulate_match(team_a, team_b, n_sims=100_000, knockout=True, seed=42):
    rng = np.random.default_rng(None if seed is None or seed < 0 else seed)
    fc = forecast_match(team_a, team_b)
    lam_a, lam_b = fc.home.lam, fc.away.lam

    # --- 1) regulation goals -------------------------------------------------
    g90_a = rng.poisson(lam_a, n_sims)
    g90_b = rng.poisson(lam_b, n_sims)

    # --- 2) scorer assignment (regulation) -----------------------------------
    players_a, pw_a = scorer_weights(team_a)
    players_b, pw_b = scorer_weights(team_b)
    sc_a = _distribute_goals(g90_a, pw_a, rng)
    sc_b = _distribute_goals(g90_b, pw_b, rng)

    tot_a = g90_a.astype(np.int64).copy()
    tot_b = g90_b.astype(np.int64).copy()

    # --- 3) knockout resolution ----------------------------------------------
    went_et = np.zeros(n_sims, dtype=bool)
    went_pens = np.zeros(n_sims, dtype=bool)
    adv_a = g90_a > g90_b
    if knockout:
        level = g90_a == g90_b
        went_et = level
        n_level = int(level.sum())
        if n_level:
            et_a = rng.poisson(lam_a * ET_RATE, n_level)
            et_b = rng.poisson(lam_b * ET_RATE, n_level)
            # assign ET goals to scorers too
            et_sc_a = _distribute_goals(et_a, pw_a, rng)
            et_sc_b = _distribute_goals(et_b, pw_b, rng)
            sc_a[level] += et_sc_a
            sc_b[level] += et_sc_b
            tot_a[level] += et_a
            tot_b[level] += et_b

            after_et_a = g90_a[level] + et_a
            after_et_b = g90_b[level] + et_b
            still_level = after_et_a == after_et_b
            pens_idx = np.where(level)[0][still_level]
            went_pens[pens_idx] = True

            adv_a[level] = after_et_a > after_et_b
            if len(pens_idx):
                p_a_pens = _penalty_shootout_prob(team_a, team_b)
                adv_a[pens_idx] = rng.random(len(pens_idx)) < p_a_pens

    # --- 4) aggregate ----------------------------------------------------------
    res = SimulationResult(forecast=fc, n_sims=n_sims, knockout=knockout)
    res.p_home_win = float((g90_a > g90_b).mean())
    res.p_draw = float((g90_a == g90_b).mean())
    res.p_away_win = float((g90_a < g90_b).mean())
    res.avg_goals_home_90 = float(g90_a.mean())
    res.avg_goals_away_90 = float(g90_b.mean())
    res.avg_goals_home = float(tot_a.mean())
    res.avg_goals_away = float(tot_b.mean())
    res.p_over_2_5 = float(((g90_a + g90_b) > 2.5).mean())
    res.p_btts = float(((g90_a > 0) & (g90_b > 0)).mean())

    if knockout:
        res.p_home_advance = float(adv_a.mean())
        res.p_away_advance = 1.0 - res.p_home_advance
        res.p_extra_time = float(went_et.mean())
        res.p_penalties = float(went_pens.mean())

    # top scorelines (90 minutes)
    cap = 6
    ha = np.minimum(g90_a, cap)
    hb = np.minimum(g90_b, cap)
    grid = np.zeros((cap + 1, cap + 1))
    np.add.at(grid, (ha, hb), 1)
    grid /= n_sims
    flat = [(h, a, grid[h, a]) for h in range(cap + 1) for a in range(cap + 1)
            if grid[h, a] > 0]
    res.top_scorelines = sorted(flat, key=lambda t: t[2], reverse=True)[:8]

    # scorer tables (regulation + ET goals)
    def scorer_table(players, scored):
        rows = []
        for i, p in enumerate(players):
            col = scored[:, i]
            rows.append({
                "name": p.name, "pos": p.position,
                "anytime": float((col >= 1).mean()),
                "two_plus": float((col >= 2).mean()),
                "xg": float(col.mean()),
            })
        rows.sort(key=lambda r: r["anytime"], reverse=True)
        return rows
    res.scorers_home = scorer_table(players_a, sc_a)
    res.scorers_away = scorer_table(players_b, sc_b)
    return res


# ---------------------------------------------------------------------------
def analytic_anytime_check(result: SimulationResult, side="home", top_n=3):
    """
    Validation: by Poisson thinning, a player receiving share p of team
    goals scores ~Poisson(lambda*p), so P(anytime) = 1 - exp(-lambda*p).
    Compares that closed form against the Monte Carlo estimate.
    """
    fc = result.forecast
    tf = fc.home if side == "home" else fc.away
    players, probs = scorer_weights(tf.team)
    lam = tf.lam * (1 + (result.p_extra_time * ET_RATE if result.knockout else 0))
    table = {p.name: 1 - np.exp(-lam * pr) for p, pr in zip(players, probs)}
    rows = result.scorers_home if side == "home" else result.scorers_away
    out = []
    for r in rows[:top_n]:
        out.append((r["name"], r["anytime"], float(table[r["name"]])))
    return out
