#!/usr/bin/env python3
"""
Folder-queue worker.

Given an  api_call_NN  folder, this processes every job sitting in its inbox/.
Each entry in inbox/ (a file, or a sub-folder of files) is ONE API call:

    inbox/   -> jobs waiting to be processed
    process/ -> the job currently being worked on (claimed; avoids double-runs)
    outbox/  -> finished results  (<name>.response.md  + the archived input)
    wait/    -> jobs that FAILED   (<name>.error.txt explains why; move back to
                inbox/ to retry)

The folder's prompt.txt is applied to every job; config.txt picks the provider,
model, and options. API keys come from the repo-root keys.txt (see keys.example.txt).

Run it directly:
    python core/worker.py path/to/api_call_01
    python core/worker.py path/to/api_call_01 --dry-run
"""

import os
import sys
import shutil
import datetime
import argparse
import pathlib

# Make sibling modules importable whether run as a script or imported.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import providers as P            # noqa: E402
import api_client                # noqa: E402

# Same file-type knowledge as the original single-call script.
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".c", ".cpp", ".h", ".java", ".rb",
    ".rs", ".go", ".sh", ".bat", ".ps1", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".log", ".sql", ".r",
    ".tex", ".bib", ".rst", ".org", ".eml",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# ---------------------------------------------------------------------------
#  Config / prompt loading
# ---------------------------------------------------------------------------

def parse_config(path: pathlib.Path) -> dict:
    cfg = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            cfg[k.strip().upper()] = v.strip()
    return cfg


def read_prompt(path: pathlib.Path) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    body = [l for l in lines if not l.strip().startswith("#")]
    return "\n".join(body).strip()


# ---------------------------------------------------------------------------
#  Attachment classification
# ---------------------------------------------------------------------------

def classify(path: pathlib.Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in TEXT_EXTENSIONS:
        return "text"
    try:
        with open(path, "r", encoding="utf-8") as f:
            f.read(8192)
        return "text"
    except (UnicodeDecodeError, PermissionError):
        return "binary_skip"


def attachments_for(entry: pathlib.Path):
    """An inbox entry can be a single file or a folder of files."""
    out = []
    if entry.is_dir():
        for p in sorted(entry.rglob("*")):
            if p.is_file() and p.name != ".gitkeep":
                out.append((str(p.relative_to(entry)), p, classify(p)))
    else:
        out.append((entry.name, entry, classify(entry)))
    return out


# ---------------------------------------------------------------------------
#  Filesystem helpers
# ---------------------------------------------------------------------------

def unique(dest: pathlib.Path) -> pathlib.Path:
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    i = 1
    while True:
        cand = parent / f"{stem}_{i}{suffix}"
        if not cand.exists():
            return cand
        i += 1


def jobs_in(inbox: pathlib.Path):
    return sorted(p for p in inbox.iterdir() if p.name != ".gitkeep")


# ---------------------------------------------------------------------------
#  Result writing
# ---------------------------------------------------------------------------

def write_response(outbox: pathlib.Path, stem: str, result: dict) -> pathlib.Path:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    price = P.price_for(result["provider"], result["model"])
    if price:
        in_c = result["input_tokens"] / 1000 * price[0]
        out_c = result["output_tokens"] / 1000 * price[1]
        cost = f"${in_c + out_c:.6f}"
    else:
        cost = "n/a"
    header = (
        f"<!--\n"
        f"  provider : {result['provider']}\n"
        f"  model    : {result['model']}\n"
        f"  finished : {ts}\n"
        f"  tokens   : {result['input_tokens']} in / {result['output_tokens']} out\n"
        f"  est cost : {cost}\n"
        f"  seconds  : {result['elapsed']:.1f}\n"
        f"-->\n\n"
    )
    dest = unique(outbox / f"{stem}.response.md")
    dest.write_text(header + result["text"], encoding="utf-8")
    return dest


def write_error(wait: pathlib.Path, stem: str, exc: Exception) -> pathlib.Path:
    import traceback
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dest = unique(wait / f"{stem}.error.txt")
    dest.write_text(
        f"Job failed at {ts}\n"
        f"Error: {exc.__class__.__name__}: {exc}\n\n"
        f"{traceback.format_exc()}\n",
        encoding="utf-8",
    )
    return dest


# ---------------------------------------------------------------------------
#  Process one folder
# ---------------------------------------------------------------------------

def process_folder(folder, dry_run=False):
    folder = pathlib.Path(folder).resolve()
    name = folder.name
    inbox = folder / "inbox"
    process = folder / "process"
    outbox = folder / "outbox"
    wait = folder / "wait"
    for d in (inbox, process, outbox, wait):
        d.mkdir(exist_ok=True)

    cfg = parse_config(folder / "config.txt")
    prompt = read_prompt(folder / "prompt.txt")

    provider = cfg.get("PROVIDER", "openai")
    pconf = P.get_provider(provider)
    provider = P.normalize_provider(provider)
    model = cfg.get("MODEL", "") or pconf["default_model"]
    api_key = P.resolve_key(provider, cfg.get("API_KEY", ""))
    max_tokens = int(cfg.get("MAX_TOKENS", "4096") or "0")
    temperature = float(cfg.get("TEMPERATURE", "0.7"))
    thinking = cfg.get("THINKING", "off").lower()
    system = cfg.get("SYSTEM", "")

    pending = jobs_in(inbox)
    print(f"\n=== {name} === provider={provider} model={model} "
          f"jobs={len(pending)}")

    if not prompt:
        print(f"    ! {name}/prompt.txt is empty -- skipping this folder.")
        return {"folder": name, "ok": 0, "failed": 0, "skipped": len(pending)}

    if not pending:
        return {"folder": name, "ok": 0, "failed": 0, "skipped": 0}

    if dry_run:
        if not api_key:
            print(f"    ! no API key resolved for {provider} "
                  f"(add {pconf['key_names'][0]} to keys.txt)")
        for entry in pending:
            atts = attachments_for(entry)
            print(f"    [DRY] would process '{entry.name}' "
                  f"({len(atts)} file(s)) -> {provider}/{model}")
        return {"folder": name, "ok": 0, "failed": 0, "skipped": len(pending)}

    ok = failed = 0
    for entry in pending:
        stem = entry.stem if entry.is_file() else entry.name
        claimed = unique(process / entry.name)
        shutil.move(str(entry), str(claimed))
        print(f"    -> {entry.name} ...", end="", flush=True)
        try:
            atts = attachments_for(claimed)
            result = api_client.call(
                provider=provider, model=model, api_key=api_key,
                prompt=prompt, attachments=atts,
                max_tokens=max_tokens, temperature=temperature,
                thinking=thinking, system=system,
            )
            out = write_response(outbox, stem, result)
            # archive the processed input next to its answer
            shutil.move(str(claimed), str(unique(outbox / f"{stem}.input{claimed.suffix}")))
            ok += 1
            print(f" done ({result['output_tokens']} tok, "
                  f"{result['elapsed']:.1f}s) -> {out.name}")
        except Exception as exc:                       # noqa: BLE001
            shutil.move(str(claimed), str(unique(wait / claimed.name)))
            write_error(wait, stem, exc)
            failed += 1
            print(f" FAILED: {exc.__class__.__name__} (see wait/{stem}.error.txt)")

    print(f"    {name}: {ok} ok, {failed} failed")
    return {"folder": name, "ok": ok, "failed": failed, "skipped": 0}


def main():
    ap = argparse.ArgumentParser(description="Process one api_call_NN folder's inbox.")
    ap.add_argument("folder", help="Path to the api_call_NN folder")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be sent, make no API calls")
    args = ap.parse_args()
    process_folder(args.folder, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
