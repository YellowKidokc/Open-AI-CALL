#!/usr/bin/env python3
"""
Create a new api_call_NN folder by copying the _template.

    python new_folder.py                       # next number, defaults to openai
    python new_folder.py --provider anthropic  # set its provider
    python new_folder.py --provider deepseek --model deepseek-reasoner
    python new_folder.py --name api_call_99     # explicit name

This is how you expand past the starter 10 folders. Each new folder is fully
self-contained: inbox/outbox/process/wait, its own config.txt, prompt.txt, and
RUN / TROUBLESHOOT scripts.
"""

import re
import sys
import glob
import shutil
import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
TEMPLATE = ROOT / "_template"


def next_name() -> str:
    nums = []
    for p in glob.glob(str(ROOT / "api_call_*")):
        m = re.search(r"api_call_(\d+)$", pathlib.Path(p).name)
        if m:
            nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    return f"api_call_{n:02d}"


def set_config(folder: pathlib.Path, provider: str, model: str):
    cfg = folder / "config.txt"
    text = cfg.read_text(encoding="utf-8")
    if provider:
        text = re.sub(r"(?m)^PROVIDER=.*$", f"PROVIDER={provider}", text)
    if model:
        text = re.sub(r"(?m)^MODEL=.*$", f"MODEL={model}", text)
    cfg.write_text(text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Scaffold a new api_call_NN folder.")
    ap.add_argument("--name", help="Explicit folder name (default: next number)")
    ap.add_argument("--provider", default="", help="openai | anthropic | deepseek | kimi")
    ap.add_argument("--model", default="", help="Model id (blank = provider default)")
    args = ap.parse_args()

    if not TEMPLATE.exists():
        print("ERROR: _template folder is missing.")
        sys.exit(1)

    name = args.name or next_name()
    dest = ROOT / name
    if dest.exists():
        print(f"ERROR: {name} already exists.")
        sys.exit(1)

    shutil.copytree(TEMPLATE, dest)
    if args.provider or args.model:
        set_config(dest, args.provider, args.model)

    print(f"Created {name}/")
    print(f"  1. Edit {name}/config.txt  (provider / model)")
    print(f"  2. Edit {name}/prompt.txt  (what this folder should do)")
    print(f"  3. Drop input files into {name}/inbox/")
    print(f"  4. Double-click {name}/RUN.bat  (or run RUN_ALL)")


if __name__ == "__main__":
    main()
