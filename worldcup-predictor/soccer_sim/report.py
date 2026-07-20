"""Terminal + markdown reporting for simulation results."""

import json
from .simulator import SimulationResult, analytic_anytime_check
from .context import describe

BAR = "=" * 66
SUB = "-" * 66


def pct(x):
    return f"{100 * x:5.1f}%"


def print_report(res: SimulationResult, validate=False):
    fc = res.forecast
    A, B = fc.home.team, fc.away.team
    print(BAR)
    print(f"  {A.name.upper()}  vs  {B.name.upper()}"
          f"   |   {res.n_sims:,} simulations")
    print(BAR)

    if fc.context is not None:
        c = fc.context
        tag = f" [{c.source}]" if c.source else ""
        print(f"\nMATCH CONDITIONS - {describe(c)}{tag}")
        print(f"  Crowd {c.crowd:,} ({c.home_support:.0%} behind {A.name})"
              f"   |   pitch {c.pitch_quality:.0%}"
              f"   |   rest {c.rest_days[0]}v{c.rest_days[1]} days")
        if fc.context_rows:
            print(f"  {'Factor':<20} {A.name:>10} {B.name:>10}")
            for r in fc.context_rows:
                print(f"  {r['factor']:<20} {'x%.2f' % r['home']:>10}"
                      f" {'x%.2f' % r['away']:>10}")
            print(f"  {'TOTAL':<20} {'x%.2f' % fc.home.ctx_mult:>10}"
                  f" {'x%.2f' % fc.away.ctx_mult:>10}")

    print(f"\nTEAM RATINGS (0-100, minutes/fitness-weighted)")
    for tf in (fc.home, fc.away):
        print(f"  {tf.team.name:<14} attack {tf.attack_score:5.1f}   |   "
              f"defense {tf.defense_score:5.1f}")

    print(f"\nMODEL EXPECTED GOALS (per 90')")
    print(f"  {A.name:<14} lambda = {fc.home.lam:.2f}"
          f"   (attack x{fc.home.att_score_mult:.2f}, "
          f"vs-def x{fc.home.def_score_mult:.2f}, "
          f"midfield x{fc.home.midfield_mult:.2f}, "
          f"vs-GK x{fc.home.gk_mult:.2f}, form x{fc.home.form_mult:.2f}, "
          f"conditions x{fc.home.ctx_mult:.2f}, "
          f"learned x{fc.home.learn_mult:.2f})")
    print(f"  {B.name:<14} lambda = {fc.away.lam:.2f}"
          f"   (attack x{fc.away.att_score_mult:.2f}, "
          f"vs-def x{fc.away.def_score_mult:.2f}, "
          f"midfield x{fc.away.midfield_mult:.2f}, "
          f"vs-GK x{fc.away.gk_mult:.2f}, form x{fc.away.form_mult:.2f}, "
          f"conditions x{fc.away.ctx_mult:.2f}, "
          f"learned x{fc.away.learn_mult:.2f})")

    print(f"\nZONE MATCHUPS ({A.name} attacking -> {B.name} defending)")
    for z, label in (("L", "Left "), ("C", "Center"), ("R", "Right ")):
        zb = fc.home.zones[z]
        atk = ", ".join(n for n, _ in zb.key_attackers)
        dfn = ", ".join(n for n, _ in zb.key_defenders)
        print(f"  {label}: x{zb.multiplier:.2f}  [{atk}]  vs  [{dfn}]")
    print(f"ZONE MATCHUPS ({B.name} attacking -> {A.name} defending)")
    for z, label in (("L", "Left "), ("C", "Center"), ("R", "Right ")):
        zb = fc.away.zones[z]
        atk = ", ".join(n for n, _ in zb.key_attackers)
        dfn = ", ".join(n for n, _ in zb.key_defenders)
        print(f"  {label}: x{zb.multiplier:.2f}  [{atk}]  vs  [{dfn}]")

    print(f"\n{SUB}\nRESULT PROBABILITIES (90 minutes)")
    print(f"  {A.name} win {pct(res.p_home_win)}   |   "
          f"Draw {pct(res.p_draw)}   |   {B.name} win {pct(res.p_away_win)}")
    if res.knockout:
        print(f"\nADVANCEMENT (incl. extra time + penalties)")
        print(f"  {A.name} advance {pct(res.p_home_advance)}   |   "
              f"{B.name} advance {pct(res.p_away_advance)}")
        print(f"  Goes to extra time {pct(res.p_extra_time)}   |   "
              f"Decided on penalties {pct(res.p_penalties)}")

    print(f"\nAVERAGE GOALS")
    print(f"  {A.name:<14} {res.avg_goals_home_90:.2f} per 90'"
          + (f"   ({res.avg_goals_home:.2f} incl. extra time)" if res.knockout else ""))
    print(f"  {B.name:<14} {res.avg_goals_away_90:.2f} per 90'"
          + (f"   ({res.avg_goals_away:.2f} incl. extra time)" if res.knockout else ""))
    print(f"  Over 2.5 goals {pct(res.p_over_2_5)}   |   "
          f"Both teams score {pct(res.p_btts)}")

    print(f"\nMOST LIKELY SCORELINES (90')")
    for h, a, p in res.top_scorelines[:6]:
        print(f"  {A.code} {h}-{a} {B.code}   {pct(p)}")

    for team, rows in ((A, res.scorers_home), (B, res.scorers_away)):
        print(f"\nLIKELY SCORERS - {team.name}   "
              f"(anytime | 2+ goals | expected goals)")
        for r in rows[:6]:
            print(f"  {r['name']:<22} {r['pos']:<3} "
                  f"{pct(r['anytime'])} | {pct(r['two_plus'])} | {r['xg']:.2f} xG")

    if validate:
        print(f"\n{SUB}\nVALIDATION: Monte Carlo vs closed-form Poisson thinning")
        for side, team in (("home", A), ("away", B)):
            for name, mc, an in analytic_anytime_check(res, side):
                print(f"  {team.code} {name:<22} sim {pct(mc)}  vs  "
                      f"analytic {pct(an)}")
    print(BAR + "\n")


def to_dict(res: SimulationResult):
    fc = res.forecast
    return {
        "match": f"{fc.home.team.name} vs {fc.away.team.name}",
        "n_sims": res.n_sims,
        "knockout": res.knockout,
        "lambda": {fc.home.team.code: round(fc.home.lam, 3),
                   fc.away.team.code: round(fc.away.lam, 3)},
        "conditions": None if fc.context is None else {
            "venue": describe(fc.context),
            "multipliers": {fc.home.team.code: round(fc.home.ctx_mult, 3),
                            fc.away.team.code: round(fc.away.ctx_mult, 3)},
            "factors": fc.context_rows},
        "team_scores": {
            fc.home.team.code: {"attack": round(fc.home.attack_score, 1),
                                "defense": round(fc.home.defense_score, 1)},
            fc.away.team.code: {"attack": round(fc.away.attack_score, 1),
                                "defense": round(fc.away.defense_score, 1)}},
        "result_90": {"home_win": res.p_home_win, "draw": res.p_draw,
                      "away_win": res.p_away_win},
        "advance": {fc.home.team.code: res.p_home_advance,
                    fc.away.team.code: res.p_away_advance,
                    "extra_time": res.p_extra_time,
                    "penalties": res.p_penalties},
        "avg_goals": {fc.home.team.code: res.avg_goals_home,
                      fc.away.team.code: res.avg_goals_away},
        "top_scorelines": [{"score": f"{h}-{a}", "p": round(p, 4)}
                           for h, a, p in res.top_scorelines],
        "scorers": {fc.home.team.code: res.scorers_home,
                    fc.away.team.code: res.scorers_away},
    }


def save_json(res: SimulationResult, path):
    with open(path, "w") as f:
        json.dump(to_dict(res), f, indent=2)
