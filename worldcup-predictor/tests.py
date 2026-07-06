"""Test suite - run with:  python tests.py

Covers the math that must not silently break: the Dixon-Coles grid,
learning-loop updates, match-condition bounds, team scores, message
building, and a full simulation smoke test with validation.
"""

import os
import tempfile
from unittest import mock

import numpy as np

PASS = 0


def check(name, cond):
    global PASS
    assert cond, f"FAIL: {name}"
    PASS += 1
    print(f"  ok - {name}")


def test_dixon_coles():
    from soccer_sim.simulator import scoreline_grid
    g = scoreline_grid(1.5, 1.1)
    check("DC grid sums to 1", abs(g.sum() - 1.0) < 1e-9)
    check("DC grid non-negative", (g >= 0).all())
    # rho < 0 must boost 0-0 and 1-1 relative to independent Poisson
    ind = scoreline_grid(1.5, 1.1, rho=0.0)
    check("DC boosts 0-0", g[0, 0] > ind[0, 0])
    check("DC boosts 1-1", g[1, 1] > ind[1, 1])
    check("DC trims 1-0", g[1, 0] < ind[1, 0])
    draws = g.trace() - ind.trace()
    check("DC raises overall draw probability", draws > 0)


def test_learning():
    from soccer_sim import learn, paper
    from soccer_sim.data.worldcup2026 import get_team
    from soccer_sim.simulator import simulate_match

    orig = learn.STATE_PATH
    orig_paper = paper.STATE_PATH
    with tempfile.TemporaryDirectory() as tmp:
        learn.STATE_PATH = os.path.join(tmp, "state.json")
        paper.STATE_PATH = os.path.join(tmp, "paper.json")
        learn._cache.update(mtime=None, state=None)
        try:
            res = simulate_match(get_team("ARG"), get_team("EGY"),
                                 n_sims=5000)
            learn.record_prediction(res)
            check("prediction recorded",
                  len(learn.load_state()["predictions"]) == 1)
            with mock.patch("soccer_sim.live.fixtures.fetch_result",
                            return_value={"home_goals": 0, "away_goals": 2,
                                          "finished": True}):
                notes = learn.update_from_results()
            check("upset produced notes", len(notes) == 1)
            st = learn.load_state()
            check("record scored", st["record"]["matches"] == 1)
            check("miss counted", st["record"]["winners_called"] == 0)
            adj = st["team_adj"]
            check("EGY attack boosted", adj["EGY"]["attack"] > 1.0)
            check("ARG attack docked", adj["ARG"]["attack"] < 1.0)
            check("ARG marked leakier", adj["ARG"]["leak"] > 1.0)
            lo, hi = learn.ADJ_CLAMP
            check("adjustments clamped",
                  all(lo <= v <= hi for a in adj.values()
                      for v in a.values()))
            check("settled", learn.is_settled("ARG", "EGY"))
            with mock.patch("soccer_sim.live.fixtures.fetch_result",
                            return_value={"home_goals": 9, "away_goals": 0,
                                          "finished": True}):
                check("never re-scored", learn.update_from_results() == [])
        finally:
            learn.STATE_PATH = orig
            paper.STATE_PATH = orig_paper
            learn._cache.update(mtime=None, state=None)


def test_context_bounds():
    from soccer_sim.context import MatchContext, context_effects, TOTAL_CLAMP
    brutal = MatchContext(altitude_m=3000, temp_c=40, humidity=0.95,
                          rain=1.0, wind_kmh=60, pitch_quality=0.85,
                          crowd=90000, home_support=1.0,
                          rest_days=(2, 2), travel_km=(9000, 9000))
    ma, mb, rows = context_effects(brutal)
    lo, hi = TOTAL_CLAMP
    check("context totals clamped", lo <= ma <= hi and lo <= mb <= hi)
    roof = MatchContext(temp_c=45, humidity=1.0, rain=1.0, wind_kmh=80,
                        roof_closed=True)
    _, _, rows = context_effects(roof)
    check("roof neutralizes weather",
          not any("Heat" in r["factor"] or "Rain" in r["factor"]
                  or "Wind" in r["factor"] for r in rows))
    neutral = MatchContext()
    ma, mb, _ = context_effects(neutral)
    check("neutral context ~1.0", abs(ma - 1.0) < 0.02 and abs(mb - 1.0) < 0.02)


def test_team_scores():
    from soccer_sim.data.worldcup2026 import TEAMS
    for t in TEAMS.values():
        a, d = t.attack_score(), t.defense_score()
        check(f"{t.code} scores in range", 40 < a < 100 and 40 < d < 100)


def test_messages():
    from soccer_sim.data.worldcup2026 import get_team, get_context
    from soccer_sim.simulator import simulate_match
    from soccer_sim.notify import sms_summary, whatsapp_summary, build_message
    res = simulate_match(get_team("MEX"), get_team("ENG"), n_sims=5000,
                         context=get_context("MEX", "ENG"))
    compact = sms_summary([res])
    rich = whatsapp_summary([res], extra=["Model record: test"])
    check("compact has advance pct", "%" in compact)
    check("rich is bold", "*" in rich and "England" in rich)
    check("rich carries extra lines", "Model record: test" in rich)
    check("rich under Twilio 1600-char cap", len(rich) < 1600)
    with mock.patch.dict(os.environ,
                         {"TWILIO_WHATSAPP_FROM": "whatsapp:+1"}):
        check("build_message picks rich", "*" in build_message([res]))
    env = {k: v for k, v in os.environ.items()
           if k != "TWILIO_WHATSAPP_FROM"}
    with mock.patch.dict(os.environ, env, clear=True):
        check("build_message picks compact",
              "*Mexico" not in build_message([res]))


def test_paper():
    from soccer_sim import paper
    from soccer_sim.data.worldcup2026 import get_team
    from soccer_sim.simulator import simulate_match
    orig = paper.STATE_PATH
    with tempfile.TemporaryDirectory() as tmp:
        paper.STATE_PATH = os.path.join(tmp, "paper.json")
        try:
            res = simulate_match(get_team("MEX"), get_team("ENG"),
                                 n_sims=20000)
            fake = {"england": 0.50, "mexico": 0.48}
            with mock.patch("soccer_sim.paper.fetch_advance_prices",
                            return_value=fake):
                notes, placed = paper.consider_bets([res])
            check("paper bet placed on edge", any("ENG" in n for n in notes))
            check("placed list returned", len(placed) == 1)
            check("bet slip mentions stake and payout",
                  "$" in paper.build_bet_slip(placed)
                  and "pays" in paper.build_bet_slip(placed))
            st = paper._load()
            check("stake capped at 5%", st["open"][0]["stake"] <= 50.0)
            check("bankroll reduced", st["bankroll"] < 1000)
            with mock.patch("soccer_sim.paper.fetch_advance_prices",
                            return_value=fake):
                _, again = paper.consider_bets([res])
            check("no duplicate bet on same match",
                  len(paper._load()["open"]) == 1 and again == [])
            win_notes = paper.settle("MEX", "ENG", "ENG")
            check("winning bet pays out", "WON" in win_notes[0])
            st = paper._load()
            check("payout ~= stake/price",
                  abs(st["bankroll"] - (1000 - st["settled"][0]["stake"]
                      + st["settled"][0]["stake"] / 0.50)) < 0.05)
            check("re-settle is no-op",
                  paper.settle("MEX", "ENG", "ENG") == [])
        finally:
            paper.STATE_PATH = orig


def test_chunking():
    from soccer_sim.notify import chunk_message
    short = "hello\n\nworld"
    check("short message unchunked", chunk_message(short) == [short])
    blocks = "\n\n".join("block %d " % i + "x" * 300 for i in range(8))
    parts = chunk_message(blocks)
    check("long message splits", len(parts) >= 2)
    check("every part under cap", all(len(p) <= 1500 for p in parts))
    check("parts numbered", parts[0].startswith("(1/"))
    joined = "".join(p.split("\n", 1)[1] for p in parts)
    check("no content lost", all(("block %d" % i) in joined
                                 for i in range(8)))


def test_inbox_commands():
    from soccer_sim import inbox, paper
    check("menu answered", "ODDS" in inbox._answer("menu"))
    check("bets answered", "$" in inbox._answer("bets"))
    check("record answered", "record" in inbox._answer("record").lower()
          or "Model" in inbox._answer("record"))
    check("noise ignored", inbox._answer("\U0001F44D") is None)
    check("empty ignored", inbox._answer("") is None)


def test_inplay():
    from soccer_sim.data.worldcup2026 import get_team
    from soccer_sim.inplay import simulate_inplay, minutes_left_from_kickoff
    a, b = get_team("MEX"), get_team("ENG")
    pre = simulate_inplay(a, b, 0, 0, 90, n_sims=50000)["p_advance_a"]
    ht_lead = simulate_inplay(a, b, 1, 0, 45, n_sims=50000)["p_advance_a"]
    late_lead = simulate_inplay(a, b, 1, 0, 10, n_sims=50000)["p_advance_a"]
    check("lead at HT beats kickoff odds", ht_lead > pre + 0.2)
    check("late lead beats HT lead", late_lead > ht_lead + 0.1)
    two_down = simulate_inplay(a, b, 0, 2, 30, n_sims=50000)["p_advance_a"]
    check("two down late is <5%", two_down < 0.05)
    check("probs complementary", abs(
        simulate_inplay(a, b, 1, 1, 20, n_sims=20000)["p_advance_a"]
        + simulate_inplay(a, b, 1, 1, 20, n_sims=20000)["p_advance_b"]
        - 1.0) < 0.02)
    from datetime import datetime, timedelta
    ko = (datetime.utcnow() - timedelta(minutes=70)).strftime(
        "%Y-%m-%dT%H:%M:%S")
    left = minutes_left_from_kickoff(ko)
    check("clock estimator ~37' left after 70 real minutes",
          35 < left < 39)
    check("pre-kickoff clock says 90", minutes_left_from_kickoff(
        (datetime.utcnow() + timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%S")) == 90.0)


def test_simulation_sanity():
    from soccer_sim.data.worldcup2026 import get_team
    from soccer_sim.simulator import simulate_match, analytic_anytime_check
    res = simulate_match(get_team("BRA"), get_team("NOR"), n_sims=50000)
    check("probabilities sum to 1",
          abs(res.p_home_win + res.p_draw + res.p_away_win - 1) < 1e-9)
    check("advance probs sum to 1",
          abs(res.p_home_advance + res.p_away_advance - 1) < 1e-9)
    check("realistic total goals",
          1.5 < res.avg_goals_home_90 + res.avg_goals_away_90 < 4.0)
    for name, mc, an in analytic_anytime_check(res, "home"):
        check(f"scorer validation {name} within 2pp", abs(mc - an) < 0.02)


if __name__ == "__main__":
    for fn in (test_dixon_coles, test_learning, test_context_bounds,
               test_team_scores, test_messages, test_paper, test_chunking,
               test_inbox_commands, test_inplay,
               test_simulation_sanity):
        print(fn.__name__)
        fn()
    print(f"\nALL TESTS PASSED ({PASS} checks)")
