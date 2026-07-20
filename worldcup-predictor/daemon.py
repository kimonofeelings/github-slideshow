"""
Autonomous runner - the predictor with nobody at the wheel.

Run:  nohup python3 daemon.py >/dev/null 2>&1 &

One process, three jobs, forever:
  * every ~45s   answer inbound text commands (ODDS, CUP, BETS, ...)
  * every ~150s  sweep all fixtures for live action: goal alerts,
                 heartbeats, full-time grading + paper settlement
                 (cheap when idle - one cached scoreboard fetch)
  * every ~15min commit & push model/paper state if it changed

A heartbeat file is touched every loop; an external watchdog restarts
the daemon if the heartbeat goes stale. All cycles are individually
fault-isolated: one bad API response never kills the loop, and file
locks make any concurrent agent-driven run harmless.
"""

import os
import subprocess
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CACHE = os.path.join(ROOT, ".cache")
HEARTBEAT = os.path.join(CACHE, "daemon_heartbeat")
LOGFILE = os.path.join(CACHE, "daemon.log")

INBOX_EVERY = 45
LIVE_EVERY = 150
PUSH_EVERY = 900

STATE_FILES = ["soccer_sim/data/model_state.json",
               "soccer_sim/data/paper_trading.json"]


def log(msg):
    os.makedirs(CACHE, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    with open(LOGFILE, "a") as f:
        f.write(f"{stamp} {msg}\n")


def load_sms_env():
    path = os.path.join(ROOT, "sms.env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def push_state_if_dirty():
    dirty = subprocess.run(["git", "status", "--porcelain", "--"] + STATE_FILES,
                           capture_output=True, text=True, cwd=ROOT)
    if not dirty.stdout.strip():
        return
    subprocess.run(["git", "add", "--"] + STATE_FILES, cwd=ROOT)
    subprocess.run(["git", "commit", "-q", "-m",
                    "Auto-commit state (daemon)\n\n"
                    "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"],
                   cwd=ROOT)
    for attempt in range(3):
        r = subprocess.run(["git", "push", "origin",
                            "claude/soccer-prediction-simulator-gv1p8g"],
                           capture_output=True, cwd=ROOT)
        if r.returncode == 0:
            log("state pushed")
            return
        time.sleep(5 * (attempt + 1))
    log("state push FAILED after retries")


def main():
    load_sms_env()
    from soccer_sim import inbox
    from soccer_sim.data.worldcup2026 import FIXTURES
    from soccer_sim.inplay import run_live_update

    log(f"daemon started pid={os.getpid()}")
    last = {"inbox": 0.0, "live": 0.0, "push": 0.0}
    while True:
        now = time.time()
        os.makedirs(CACHE, exist_ok=True)
        with open(HEARTBEAT, "w") as f:
            f.write(str(int(now)))

        if now - last["inbox"] >= INBOX_EVERY:
            last["inbox"] = now
            try:
                for a in inbox.process(n_sims=200_000):
                    log(a)
            except Exception:
                log("inbox cycle error:\n" + traceback.format_exc(limit=2))

        if now - last["live"] >= LIVE_EVERY:
            last["live"] = now
            for h, a in FIXTURES:
                try:
                    outcome = run_live_update(h, a, n_sims=500_000)
                    if outcome not in ("no-change", "not-started",
                                       "already-graded", "no-data"):
                        log(f"live {h}-{a}: {outcome}")
                        push_state_if_dirty()
                except Exception:
                    log(f"live {h}-{a} error:\n"
                        + traceback.format_exc(limit=2))

        if now - last["push"] >= PUSH_EVERY:
            last["push"] = now
            try:
                push_state_if_dirty()
            except Exception:
                log("push cycle error:\n" + traceback.format_exc(limit=2))

        time.sleep(10)


if __name__ == "__main__":
    main()
