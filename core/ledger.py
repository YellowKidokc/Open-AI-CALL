#!/usr/bin/env python3
"""
Run ledger -- one CSV row per job, appended to the repo-root runs.csv.

After a big unattended batch you can open runs.csv to see exactly what ran,
what it cost, and what failed. Thread-safe (workers append concurrently).
"""

import csv
import threading
import datetime
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = ROOT / "runs.csv"

_LOCK = threading.Lock()
_HEADER = ["timestamp", "folder", "job", "provider", "model",
           "status", "in_tokens", "out_tokens", "est_cost_usd",
           "seconds", "output", "error"]


def record(folder, job, provider, model, status,
           in_tokens=0, out_tokens=0, est_cost=0.0,
           seconds=0.0, output="", error=""):
    row = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "folder": folder, "job": job, "provider": provider, "model": model,
        "status": status, "in_tokens": in_tokens, "out_tokens": out_tokens,
        "est_cost_usd": f"{est_cost:.6f}", "seconds": f"{seconds:.1f}",
        "output": output, "error": error.replace("\n", " ")[:300],
    }
    with _LOCK:
        new = not LEDGER.exists()
        with open(LEDGER, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=_HEADER)
            if new:
                w.writeheader()
            w.writerow(row)
