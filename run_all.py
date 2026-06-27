#!/usr/bin/env python3
"""
Master runner -- processes the inbox of every api_call_NN folder.

    python run_all.py                  # one pass over every folder with jobs
    python run_all.py --dry-run        # show what would happen, no API calls
    python run_all.py --workers 6      # 6 calls in parallel
    python run_all.py --max-cost 5.00  # stop the whole run near $5
    python run_all.py --retry-failed   # sweep each wait/ back into inbox/ first
    python run_all.py --loop 60        # keep running, re-scan every 60s
    python run_all.py --only api_call_03 api_call_07

Each folder is taken all the way through before the next. A per-run ledger is
written to runs.csv (every job: provider, model, tokens, cost, status).
"""

import os
import sys
import glob
import time
import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "core"))


def ensure_deps():
    """Best-effort: install the SDKs / libs the configured folders need."""
    import importlib
    needed = set()
    for cfg in glob.glob(str(ROOT / "api_call_*" / "config.txt")):
        text = pathlib.Path(cfg).read_text(encoding="utf-8")
        low = text.lower()
        for line in low.splitlines():
            line = line.strip()
            if line.startswith("provider"):
                needed.add("anthropic" if ("anthropic" in line or "claude" in line)
                           else "openai")
            if line.startswith("output_format") and "xlsx" in line:
                needed.add("openpyxl")
    for pkg in sorted(needed):
        try:
            importlib.import_module(pkg)
        except ImportError:
            print(f"Installing required package '{pkg}' ...")
            os.system(f'"{sys.executable}" -m pip install -q {pkg}')


def discover(only):
    folders = sorted(pathlib.Path(p) for p in glob.glob(str(ROOT / "api_call_*"))
                     if pathlib.Path(p).is_dir())
    if only:
        wanted = {o.rstrip("/\\") for o in only}
        folders = [f for f in folders if f.name in wanted]
    return folders


def one_pass(folders, args):
    import worker
    totals = {"ok": 0, "failed": 0, "skipped": 0, "cost": 0.0}
    remaining = args.max_cost
    for folder in folders:
        r = worker.process_folder(
            folder, dry_run=args.dry_run, workers=args.workers,
            max_cost=remaining, retry=args.retry_failed,
        )
        for k in totals:
            totals[k] += r.get(k, 0)
        if remaining is not None:
            remaining = max(0.0, remaining - r.get("cost", 0.0))
            if remaining <= 0:
                print(f"\n  ! global budget cap (${args.max_cost:.2f}) reached "
                      f"-- stopping.")
                break
    print("\n" + "-" * 64)
    print(f"  PASS COMPLETE: {totals['ok']} ok, {totals['failed']} failed, "
          f"{totals['skipped']} queued/skipped   est total ${totals['cost']:.4f}")
    print(f"  ledger: runs.csv")
    print("-" * 64)
    return totals


def main():
    ap = argparse.ArgumentParser(description="Run every api_call_NN folder.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=1, help="Parallel calls (default 1)")
    ap.add_argument("--max-cost", type=float, default=None,
                    help="Approx $ cap for the whole run")
    ap.add_argument("--retry-failed", action="store_true",
                    help="Move each folder's wait/ jobs back to inbox/ first")
    ap.add_argument("--loop", type=int, default=0, metavar="SECONDS",
                    help="Keep running, re-scanning every N seconds")
    ap.add_argument("--only", nargs="*", default=None, help="Only these folders")
    args = ap.parse_args()

    if not args.dry_run:
        ensure_deps()

    folders = discover(args.only)
    if not folders:
        print("No api_call_* folders found. Run NEW_FOLDER to create one.")
        return
    print(f"Found {len(folders)} folder(s): {', '.join(f.name for f in folders)}")

    if args.loop > 0:
        print(f"Loop mode: re-scanning every {args.loop}s. Ctrl+C to stop.")
        try:
            while True:
                one_pass(folders, args)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        one_pass(folders, args)


if __name__ == "__main__":
    main()
