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
import os
import time

from soccer_sim.data.worldcup2026 import get_team, get_context, TEAMS, FIXTURES
from soccer_sim.simulator import simulate_match
from soccer_sim.report import print_report, save_json


def run(home, away, sims, knockout, seed, validate, save, neutral=False,
        live=False):
    a, b = get_team(home), get_team(away)
    context = None if neutral else get_context(home, away)
    if live and not neutral:
        from soccer_sim.live import live_context, apply_squad_news
        context, notes, fetched = live_context(a, b, base=context)
        apply_squad_news(a, notes)
        apply_squad_news(b, notes)
        context.source = f"LIVE, fetched {fetched}"
        print("LIVE DATA")
        for n in notes:
            print(f"  - {n}")
    t0 = time.time()
    res = simulate_match(a, b, n_sims=sims, knockout=knockout, seed=seed,
                         context=context)
    dt = time.time() - t0
    print_report(res, validate=validate)
    print(f"({sims:,} simulations in {dt:.2f}s)\n")
    if save:
        path = f"results_{a.code}_vs_{b.code}.json"
        save_json(res, path)
        print(f"Saved detailed results -> {path}\n")
    return res


def _load_sms_env():
    """Load SMS provider credentials from gitignored sms.env (KEY=VALUE
    lines, # comments allowed) so nothing secret lives in the shell
    profile or the repo. Real environment variables take precedence."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sms.env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    ap = argparse.ArgumentParser(description="Soccer match Monte Carlo predictor")
    ap.add_argument("--home", default="ARG")
    ap.add_argument("--away", default="EGY")
    ap.add_argument("--sims", type=int, default=1_000_000)
    ap.add_argument("--group-stage", action="store_true",
                    help="90 minutes only (draws stand), no ET/pens")
    ap.add_argument("--seed", type=int, default=42,
                    help="-1 for fresh randomness each run")
    ap.add_argument("--validate", action="store_true",
                    help="compare Monte Carlo vs closed-form scorer probs")
    ap.add_argument("--save", action="store_true", help="write JSON results")
    ap.add_argument("--fixtures", action="store_true",
                    help="run all real Round-of-16 ties in the data file")
    ap.add_argument("--neutral", action="store_true",
                    help="ignore venue/weather/crowd conditions")
    ap.add_argument("--live", action="store_true",
                    help="fetch real fixture, venue and kickoff weather "
                         "(TheSportsDB + Open-Meteo, no keys needed); "
                         "injury feeds activate with APIFOOTBALL_KEY")
    ap.add_argument("--text", nargs="?", const="", metavar="PHONE",
                    help="text the results to this number (or set "
                         "PREDICTOR_PHONE); see README for provider setup")
    ap.add_argument("--text-preview", action="store_true",
                    help="print the exact SMS without sending it")
    ap.add_argument("--learn", action="store_true",
                    help="score past predictions against real results, "
                         "adjust team factors, and record today's forecasts")
    ap.add_argument("--history", action="store_true",
                    help="show the model's prediction ledger and accuracy")
    ap.add_argument("--live-match", action="store_true",
                    help="one live poll of --home vs --away: fetch the real "
                         "current score, re-simulate from that state, and "
                         "text updated odds (full-time grades the model)")
    ap.add_argument("--inbox", action="store_true",
                    help="answer any new text-message commands (ODDS, BETS, "
                         "RECORD, LIVE, MENU) and exit")
    ap.add_argument("--list-teams", action="store_true")
    args = ap.parse_args()

    if args.list_teams:
        for code, t in TEAMS.items():
            print(f"  {code}  {t.name}  ({len(t.players)} players)")
        return

    if args.inbox:
        _load_sms_env()
        from soccer_sim.inbox import process
        for action in process() or ["inbox: nothing new"]:
            print(action)
        return

    if args.live_match:
        _load_sms_env()
        from soccer_sim.inplay import run_live_update
        outcome = run_live_update(args.home, args.away, n_sims=args.sims)
        print(f"live update: {outcome}")
        return

    if args.history:
        from soccer_sim import learn
        state = learn.load_state()
        print("PREDICTION LEDGER")
        for h in state["history"]:
            mark = ("✓" if h["called"] else
                    "✗" if h["called"] is not None else "~")
            print(f"  {mark} {h['match']}   "
                  f"(predicted home {h['predicted_home']:.0%}"
                  + (f", Brier {h['brier']:.2f}" if h["brier"] is not None
                     else "") + ")")
            for line in h.get("learned", []):
                print(f"      learned: {line}")
        pending = [p for p in state["predictions"] if not p["settled"]]
        for p in pending:
            print(f"  … {p['home']} vs {p['away']}: "
                  f"{p['p_home_advance']:.0%} home, awaiting result")
        print(f"  {learn.record_line()}")
        adj = state["team_adj"]
        if adj:
            print("CURRENT TEAM ADJUSTMENTS (attack / defense-leak)")
            for code, a in sorted(adj.items()):
                print(f"  {code}: x{a['attack']:.3f} / x{a['leak']:.3f}")
        return

    knockout = not args.group_stage
    learn_notes = []
    if args.learn:
        from soccer_sim import learn
        learn_notes = learn.update_from_results()
        if learn_notes:
            print("LEARNED FROM RESULTS")
            for n in learn_notes:
                print(f"  - {n}")

    results = []
    if args.fixtures:
        for h, a in FIXTURES:
            if args.learn:
                from soccer_sim import learn
                th, ta = get_team(h), get_team(a)
                if learn.is_settled(th.code, ta.code):
                    print(f"(skipping {h} vs {a}: already played "
                          f"and scored)\n")
                    continue
            results.append(run(h, a, args.sims, knockout, args.seed,
                               args.validate, args.save,
                               neutral=args.neutral, live=args.live))
    else:
        results.append(run(args.home, args.away, args.sims, knockout,
                           args.seed, args.validate, args.save,
                           neutral=args.neutral, live=args.live))

    paper_notes, paper_placed = [], []
    if args.learn and results:
        from soccer_sim import learn, paper
        for res in results:
            learn.record_prediction(res)
        paper_notes, paper_placed = paper.consider_bets(results)
        for n in paper_notes:
            print(f"  - {n}")

    if not results:
        print("All fixtures in the data file have been played and scored. "
              "Add upcoming fixtures to soccer_sim/data/worldcup2026.py.")
        return

    if args.learn:
        # answer any text commands that arrived since the last run
        _load_sms_env()
        try:
            from soccer_sim.inbox import process as inbox_process
            for action in inbox_process():
                print(f"  - {action}")
        except Exception:
            pass

    if args.text is not None or args.text_preview:
        _load_sms_env()
        from soccer_sim.notify import build_message, send_long as send_sms
        extra = []
        if args.learn:
            from soccer_sim import learn, paper
            bets = [n for n in paper_notes if not n.startswith("paper ")]
            extra = learn_notes + bets + [learn.record_line(),
                                          paper.summary_line()]
        message = build_message(results, extra)
        if args.text_preview:
            print("SMS PREVIEW" + f" ({len(message)} chars)\n" + "-" * 40)
            print(message)
            print("-" * 40)
        if args.text is not None:
            phone = args.text or os.environ.get("PREDICTOR_PHONE", "")
            if not phone:
                # phone.txt is gitignored: your number stays off GitHub
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "phone.txt")
                if os.path.exists(path):
                    with open(path) as f:
                        phone = f.read().strip()
            if not phone:
                print("\nNo phone number. Either pass --text +15551234567, "
                      "set PREDICTOR_PHONE, or save it once with:\n"
                      "  echo +15551234567 > phone.txt   (gitignored)")
                return
            ok, provider, detail = send_sms(phone, message)
            if ok:
                print(f"\nText sent via {provider}: {detail}")
            else:
                print(f"\nText NOT sent. {detail}")
            if ok and paper_placed:
                from soccer_sim import paper
                slip_ok, _, slip_detail = send_sms(
                    phone, paper.build_bet_slip(paper_placed))
                print("Bet slip sent" if slip_ok
                      else f"Bet slip NOT sent: {slip_detail}")


if __name__ == "__main__":
    main()
