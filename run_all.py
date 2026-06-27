#!/usr/bin/env python3
"""
Master runner -- processes the inbox of every api_call_NN folder.

    python run_all.py            # one pass over every folder that has jobs
    python run_all.py --dry-run  # show what would happen, make no API calls
    python run_all.py --loop 60  # keep running, re-scanning every 60 seconds
    python run_all.py --only api_call_03 api_call_07   # just these folders

Each folder is taken all the way through (its whole inbox is processed) before
moving to the next. Drop files into any folder's inbox/, run this once, and walk
away -- hundreds of queued jobs get processed unattended.
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
    """Best-effort: install the SDKs needed by the configured folders."""
    import importlib
    needed = set()
    for cfg in glob.glob(str(ROOT / "api_call_*" / "config.txt")):
        for line in pathlib.Path(cfg).read_text(encoding="utf-8").splitlines():
            line = line.strip().lower()
            if line.startswith("provider"):
                if "anthropic" in line or "claude" in line:
                    needed.add("anthropic")
                else:
                    needed.add("openai")   # openai/deepseek/kimi all use it
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


def one_pass(folders, dry_run):
    import worker
    totals = {"ok": 0, "failed": 0, "skipped": 0}
    for folder in folders:
        r = worker.process_folder(folder, dry_run=dry_run)
        for k in totals:
            totals[k] += r.get(k, 0)
    print("\n" + "-" * 64)
    print(f"  PASS COMPLETE: {totals['ok']} ok, {totals['failed']} failed, "
          f"{totals['skipped']} skipped/queued")
    print("-" * 64)
    return totals


def main():
    ap = argparse.ArgumentParser(description="Run every api_call_NN folder.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be sent, make no API calls")
    ap.add_argument("--loop", type=int, default=0, metavar="SECONDS",
                    help="Keep running, re-scanning every N seconds")
    ap.add_argument("--only", nargs="*", default=None,
                    help="Only run these folder names")
    args = ap.parse_args()

    if not args.dry_run:
        ensure_deps()

    folders = discover(args.only)
    if not folders:
        print("No api_call_* folders found. Run NEW_FOLDER to create one.")
        return

    print(f"Found {len(folders)} folder(s): {', '.join(f.name for f in folders)}")

    if args.loop > 0:
        print(f"Loop mode: re-scanning every {args.loop}s. Press Ctrl+C to stop.")
        try:
            while True:
                one_pass(folders, args.dry_run)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        one_pass(folders, args.dry_run)


if __name__ == "__main__":
    main()
