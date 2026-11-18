"""Supervisor: poll children, restart with backoff, count by source (§3.4).

source ∈ {"platform", "pilot"} — uptime of the Platform is computed EXCLUDING pilot
failures (playbook §5.3). Runbook 72h (§5.2): alert a human at ≥3 restarts/h of the
same child; this module only counts.
"""

import csv
import subprocess
import sys
import time
from pathlib import Path

RESTART_LOG = Path("data/metrics/restarts.csv")


def supervise(procs: dict[str, dict], poll_s: float = 2.0, backoff_max: float = 60.0) -> None:
    """procs: {name: {"cmd": [...], "source": "platform" | "pilot" | ...}}.

    Blocks forever; Ctrl+C exits without killing children (supervisor ≠ terminator).
    """
    RESTART_LOG.parent.mkdir(parents=True, exist_ok=True)
    info = {n: {"p": None, "next_ok": 0.0, "backoff": 1.0, "cmd": v["cmd"], "source": v["source"]}
            for n, v in procs.items()}
    try:
        while True:
            time.sleep(poll_s)
            for name, it in info.items():
                if it["p"] is not None and it["p"].poll() is None:
                    continue
                now = time.time()
                if now < it["next_ok"]:
                    continue  # backoff window
                if it["p"] is not None:  # died once — record (source-tagged, §5.3)
                    with open(RESTART_LOG, "a", newline="") as f:
                        csv.writer(f).writerow([f"{now:.0f}", name, it["source"], it["backoff"]])
                    print(f"{name}: died, restart in {it['backoff']}s ({it['source']})",
                          file=sys.stderr)
                    it["backoff"] = min(it["backoff"] * 2, backoff_max)
                    it["next_ok"] = now + it["backoff"]
                it["p"] = subprocess.Popen(it["cmd"])
    except KeyboardInterrupt:
        pass
