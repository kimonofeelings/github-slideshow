"""
World Cup match prediction engine - CLI

Examples
--------
python main.py                              # ARG vs EGY, 100,000 sims
python main.py --home BRA --away NOR        # any matchup from the data file
python main.py --fixtures                   # all three real R16 ties
python main.py --sims 250000 --validate     # more sims + math sanity check
python main.py --list-teams
python main.py --group-stage                # 90' only, draws allowed
"""

import argparse
import time

from soccer_sim.data.worldcup2026 import get_team, TEAMS, FIXTURES
from soccer_sim.simulator import simulate_match
from soccer_sim.report import print_report, save_json


def run(home, away, sims, knockout, seed, validate, save):
    a, b = get_team(home), get_team(away)
    t0 = time.time()
    res = simulate_match(a, b, n_sims=sims, knockout=knockout, seed=seed)
    dt = time.time() - t0
    print_report(res, validate=validate)
    print(f"({sims:,} simulations in {dt:.2f}s)\n")
    if save:
        path = f"results_{a.code}_vs_{b.code}.json"
        save_json(res, path)
        print(f"Saved detailed results -> {path}\n")


def main():
    ap = argparse.ArgumentParser(description="Soccer match Monte Carlo predictor")
    ap.add_argument("--home", default="ARG")
    ap.add_argument("--away", default="EGY")
    ap.add_argument("--sims", type=int, default=100_000)
    ap.add_argument("--group-stage", action="store_true",
                    help="90 minutes only (draws stand), no ET/pens")
    ap.add_argument("--seed", type=int, default=42,
                    help="-1 for fresh randomness each run")
    ap.add_argument("--validate", action="store_true",
                    help="compare Monte Carlo vs closed-form scorer probs")
    ap.add_argument("--save", action="store_true", help="write JSON results")
    ap.add_argument("--fixtures", action="store_true",
                    help="run all real Round-of-16 ties in the data file")
    ap.add_argument("--list-teams", action="store_true")
    args = ap.parse_args()

    if args.list_teams:
        for code, t in TEAMS.items():
            print(f"  {code}  {t.name}  ({len(t.players)} players)")
        return

    knockout = not args.group_stage
    if args.fixtures:
        for h, a in FIXTURES:
            run(h, a, args.sims, knockout, args.seed, args.validate, args.save)
    else:
        run(args.home, args.away, args.sims, knockout, args.seed,
            args.validate, args.save)


if __name__ == "__main__":
    main()
