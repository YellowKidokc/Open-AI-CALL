#!/usr/bin/env python3
"""
Troubleshooter / health check for the multi-API batch processor.

    python troubleshoot.py                 # check everything
    python troubleshoot.py api_call_03      # check one folder

It checks, without making any API calls:
  * Python version and whether the openai / anthropic packages are installed
  * keys.txt -- which provider keys are present
  * each folder's config (known provider? model set? key resolvable?)
  * inbox / process / outbox / wait counts
  * the most recent errors sitting in each wait/ folder
"""

import os
import sys
import glob
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "core"))
import providers as P            # noqa: E402

OK = "[ OK ]"
WARN = "[WARN]"
BAD = "[FAIL]"


def check_environment():
    print("=" * 64)
    print("  ENVIRONMENT")
    print("=" * 64)
    print(f"  {OK} Python {sys.version.split()[0]}")
    for pkg in ("openai", "anthropic"):
        try:
            __import__(pkg)
            print(f"  {OK} package '{pkg}' is installed")
        except ImportError:
            print(f"  {WARN} package '{pkg}' NOT installed  ->  pip install {pkg}")

    print("\n  API keys (from keys.txt / environment):")
    file_keys = P.load_keys_file()
    if not P.KEYS_FILE.exists():
        print(f"  {WARN} keys.txt not found. Copy keys.example.txt -> keys.txt "
              f"and paste your keys.")
    any_key = False
    for name, pconf in P.PROVIDERS.items():
        key = P.resolve_key(name)
        if key:
            masked = key[:6] + "..." + key[-4:] if len(key) > 12 else "set"
            print(f"  {OK} {name:<10} key found ({masked})")
            any_key = True
        else:
            print(f"  {WARN} {name:<10} no key  (add {pconf['key_names'][0]})")
    if not any_key:
        print(f"  {BAD} No keys at all -- nothing can run until you add one.")


def check_folder(folder: pathlib.Path):
    name = folder.name
    cfg_path = folder / "config.txt"
    print(f"\n--- {name} ---")

    if not cfg_path.exists():
        print(f"  {BAD} no config.txt")
        return
    cfg = {}
    for line in cfg_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            cfg[k.strip().upper()] = v.strip()

    provider = cfg.get("PROVIDER", "")
    try:
        pconf = P.get_provider(provider)
        prov = P.normalize_provider(provider)
        model = cfg.get("MODEL", "") or pconf["default_model"]
        print(f"  {OK} provider={prov}  model={model}")
        key = P.resolve_key(prov, cfg.get("API_KEY", ""))
        if key:
            print(f"  {OK} API key resolved for {prov}")
        else:
            print(f"  {WARN} no API key for {prov} (add {pconf['key_names'][0]} to keys.txt)")
    except ValueError as e:
        print(f"  {BAD} {e}")

    out_fmt = cfg.get("OUTPUT_FORMAT", "md").lower()
    tdir = folder / "templates"
    tmpls = [p.name for p in tdir.iterdir()
             if p.name != ".gitkeep"] if tdir.exists() else []
    tnote = f"  (templates: {', '.join(tmpls)})" if tmpls else ""
    print(f"  {OK} output={out_fmt}{tnote}")
    if out_fmt == "xlsx":
        try:
            __import__("openpyxl")
        except ImportError:
            print(f"  {WARN} OUTPUT_FORMAT=xlsx needs openpyxl  ->  pip install openpyxl")

    retr = cfg.get("RETRIEVER", "none").lower()
    if retr not in ("", "none", "off"):
        detail = {"folder": cfg.get("RETRIEVER_PATH", ""),
                  "command": cfg.get("RETRIEVER_CMD", ""),
                  "http": cfg.get("RETRIEVER_URL", "")}.get(retr, "")
        if detail:
            print(f"  {OK} retriever={retr} -> {detail}")
        else:
            need = {"folder": "RETRIEVER_PATH", "command": "RETRIEVER_CMD",
                    "http": "RETRIEVER_URL"}.get(retr, "?")
            print(f"  {WARN} retriever={retr} but {need} is not set")

    prompt = folder / "prompt.txt"
    if prompt.exists() and prompt.read_text(encoding="utf-8").strip():
        body = [l for l in prompt.read_text(encoding="utf-8").splitlines()
                if not l.strip().startswith("#")]
        if "\n".join(body).strip():
            print(f"  {OK} prompt.txt has content")
        else:
            print(f"  {WARN} prompt.txt is only comments (folder will be skipped)")
    else:
        print(f"  {WARN} prompt.txt missing/empty (folder will be skipped)")

    def count(sub):
        d = folder / sub
        if not d.exists():
            return 0
        return sum(1 for p in d.iterdir() if p.name != ".gitkeep")

    print(f"  queue: inbox={count('inbox')}  process={count('process')}  "
          f"outbox={count('outbox')}  wait={count('wait')}")

    waitdir = folder / "wait"
    if waitdir.exists():
        errs = sorted(waitdir.glob("*.error.txt"))
        if errs:
            print(f"  {WARN} {len(errs)} failed job(s) waiting. Most recent error:")
            last = max(errs, key=lambda p: p.stat().st_mtime)
            for line in last.read_text(encoding="utf-8").splitlines()[:3]:
                print(f"        {line}")
            print(f"        (move files from wait/ back to inbox/ to retry)")

    procdir = folder / "process"
    if procdir.exists():
        stuck = [p for p in procdir.iterdir() if p.name != ".gitkeep"]
        if stuck:
            print(f"  {WARN} {len(stuck)} item(s) stuck in process/ "
                  f"(a previous run was interrupted; move them back to inbox/)")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    check_environment()
    print("\n" + "=" * 64)
    print("  FOLDERS")
    print("=" * 64)

    if target:
        folder = (ROOT / target).resolve()
        if not folder.exists():
            print(f"  {BAD} folder not found: {target}")
            return
        check_folder(folder)
    else:
        folders = sorted(pathlib.Path(p) for p in glob.glob(str(ROOT / "api_call_*"))
                         if pathlib.Path(p).is_dir())
        if not folders:
            print(f"  {WARN} no api_call_* folders found. Run NEW_FOLDER to make one.")
        for f in folders:
            check_folder(f)
    print("\nDone.")


if __name__ == "__main__":
    main()
