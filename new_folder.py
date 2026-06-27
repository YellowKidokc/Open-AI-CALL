#!/usr/bin/env python3
"""
Duplicate the _template into the next api_call_NN folder(s).

It always continues IN ORDER from the highest existing number, so you never
have to say which number -- just run it again and again:

    python new_folder.py            # make the next one  (e.g. api_call_11)
    python new_folder.py 5          # make the next FIVE (api_call_11 .. 15)
    python new_folder.py --provider anthropic        # next one, set provider
    python new_folder.py 3 --provider deepseek       # next three, all deepseek
    python new_folder.py --name api_call_99          # one, explicit name

Each new folder is fully self-contained: inbox/outbox/process/wait/templates,
its own config.txt + prompt.txt, and RUN / TROUBLESHOOT scripts.
"""

import re
import sys
import glob
import shutil
import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
TEMPLATE = ROOT / "_template"


def highest_number() -> int:
    nums = []
    for p in glob.glob(str(ROOT / "api_call_*")):
        m = re.search(r"api_call_(\d+)$", pathlib.Path(p).name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else 0


def set_config(folder: pathlib.Path, provider: str, model: str):
    cfg = folder / "config.txt"
    text = cfg.read_text(encoding="utf-8")
    if provider:
        text = re.sub(r"(?m)^PROVIDER=.*$", f"PROVIDER={provider}", text)
    if model:
        text = re.sub(r"(?m)^MODEL=.*$", f"MODEL={model}", text)
    cfg.write_text(text, encoding="utf-8")


def make_one(name: str, provider: str, model: str) -> bool:
    dest = ROOT / name
    if dest.exists():
        print(f"  skip: {name} already exists")
        return False
    shutil.copytree(TEMPLATE, dest)
    if provider or model:
        set_config(dest, provider, model)
    print(f"  created {name}/" + (f"  (provider={provider})" if provider else ""))
    return True


def main():
    ap = argparse.ArgumentParser(description="Duplicate the template into the next folder(s).")
    ap.add_argument("count", nargs="?", type=int, default=1,
                    help="How many new folders to make (default 1)")
    ap.add_argument("--name", help="Explicit name (only valid with count 1)")
    ap.add_argument("--provider", default="", help="openai | anthropic | deepseek | kimi")
    ap.add_argument("--model", default="", help="Model id (blank = provider default)")
    args = ap.parse_args()

    if not TEMPLATE.exists():
        sys.exit("ERROR: _template folder is missing.")
    if args.count < 1:
        sys.exit("ERROR: count must be 1 or more.")

    if args.name:
        if args.count != 1:
            sys.exit("ERROR: --name can only be used when making one folder.")
        made = [args.name] if make_one(args.name, args.provider, args.model) else []
    else:
        start = highest_number() + 1
        made = []
        for n in range(start, start + args.count):
            name = f"api_call_{n:02d}"
            if make_one(name, args.provider, args.model):
                made.append(name)

    if made:
        print(f"\nDone. Added {len(made)} folder(s): {', '.join(made)}")
        print("Next: edit each new folder's config.txt + prompt.txt, drop files in")
        print("its inbox/, then run RUN_ALL (it picks up the new folders automatically).")


if __name__ == "__main__":
    main()
