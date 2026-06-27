#!/usr/bin/env python3
"""
Folder-queue worker.

Given an  api_call_NN  folder, this processes every job in its inbox/. Each
entry (a file, or a sub-folder of files) is ONE API call:

    inbox/   -> jobs waiting
    process/ -> the job currently running (claimed; auto)
    outbox/  -> finished results  (formatted per OUTPUT_FORMAT, + archived input)
    wait/    -> FAILED jobs        (<name>.error.txt says why)
    templates/ -> optional Excel/HTML template the answer is written into

The prompt (prompt.txt) is applied to every job; config.txt picks the provider,
model, output format, and optional retriever (your vector engine). Keys come
from the repo-root keys.txt.

    python core/worker.py path/to/api_call_01
    python core/worker.py path/to/api_call_01 --dry-run
    python core/worker.py path/to/api_call_01 --workers 4 --max-cost 2.00
    python core/worker.py path/to/api_call_01 --retry-failed
"""

import os
import sys
import shutil
import threading
import argparse
import pathlib
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import providers as P          # noqa: E402
import api_client              # noqa: E402
import outputs                 # noqa: E402
import retriever               # noqa: E402
import ledger                  # noqa: E402

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".c", ".cpp", ".h", ".java", ".rb",
    ".rs", ".go", ".sh", ".bat", ".ps1", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".log", ".sql", ".r",
    ".tex", ".bib", ".rst", ".org", ".eml",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# ---------------------------------------------------------------------------
#  Config / prompt
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
#  Attachments
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
    out = []
    if entry.is_dir():
        for p in sorted(entry.rglob("*")):
            if p.is_file() and p.name != ".gitkeep":
                out.append((str(p.relative_to(entry)), p, classify(p)))
    else:
        out.append((entry.name, entry, classify(entry)))
    return out


def query_text(prompt, attachments, limit=2000):
    """Build the retrieval query from the prompt + a sample of the input."""
    parts = [prompt]
    for name, path, kind in attachments:
        if kind == "text":
            try:
                parts.append(path.read_text(encoding="utf-8", errors="replace")[:limit])
            except Exception:
                pass
    return "\n".join(parts)[:4000]


# ---------------------------------------------------------------------------
#  Filesystem helpers
# ---------------------------------------------------------------------------

def unique(dest: pathlib.Path) -> pathlib.Path:
    if not dest.exists():
        return dest
    i = 1
    while True:
        cand = dest.parent / f"{dest.stem}_{i}{dest.suffix}"
        if not cand.exists():
            return cand
        i += 1


def jobs_in(inbox: pathlib.Path):
    return sorted(p for p in inbox.iterdir() if p.name != ".gitkeep")


def write_error(wait: pathlib.Path, stem: str, exc: Exception) -> pathlib.Path:
    import traceback
    import datetime
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dest = unique(wait / f"{stem}.error.txt")
    dest.write_text(f"Job failed at {ts}\n"
                    f"Error: {exc.__class__.__name__}: {exc}\n\n"
                    f"{traceback.format_exc()}\n", encoding="utf-8")
    return dest


def retry_failed(folder: pathlib.Path):
    """Sweep failed inputs from wait/ back into inbox/ (drop their .error.txt)."""
    wait, inbox = folder / "wait", folder / "inbox"
    moved = 0
    for p in list(wait.iterdir()):
        if p.name == ".gitkeep":
            continue
        if p.name.endswith(".error.txt"):
            p.unlink()
            continue
        shutil.move(str(p), str(unique(inbox / p.name)))
        moved += 1
    if moved:
        print(f"    retry: moved {moved} failed job(s) back to inbox/")
    return moved


# ---------------------------------------------------------------------------
#  Process one folder
# ---------------------------------------------------------------------------

def process_folder(folder, dry_run=False, workers=1, max_cost=None,
                   retry=False):
    folder = pathlib.Path(folder).resolve()
    name = folder.name
    inbox, process, outbox, wait = (folder / d for d in
                                    ("inbox", "process", "outbox", "wait"))
    for d in (inbox, process, outbox, wait):
        d.mkdir(exist_ok=True)

    if retry and not dry_run:
        retry_failed(folder)

    cfg = parse_config(folder / "config.txt")
    prompt = read_prompt(folder / "prompt.txt")

    provider = P.normalize_provider(cfg.get("PROVIDER", "openai"))
    pconf = P.get_provider(provider)
    model = cfg.get("MODEL", "") or pconf["default_model"]
    api_key = P.resolve_key(provider, cfg.get("API_KEY", ""))
    max_tokens = int(cfg.get("MAX_TOKENS", "4096") or "0")
    temperature = float(cfg.get("TEMPERATURE", "0.7"))
    thinking = cfg.get("THINKING", "off").lower()
    system = cfg.get("SYSTEM", "")
    out_fmt = cfg.get("OUTPUT_FORMAT", "md").lower()
    template_path = outputs.find_template(folder, out_fmt)
    fmt_note = outputs.format_instruction(out_fmt, template_path)

    pending = jobs_in(inbox)
    extra = f" fmt={out_fmt}"
    if template_path:
        extra += f" template={template_path.name}"
    if cfg.get("RETRIEVER", "none").lower() not in ("", "none", "off"):
        extra += f" retriever={cfg['RETRIEVER'].lower()}"
    print(f"\n=== {name} === provider={provider} model={model} "
          f"jobs={len(pending)} workers={workers}{extra}")

    if not prompt:
        print(f"    ! {name}/prompt.txt is empty -- skipping.")
        return {"folder": name, "ok": 0, "failed": 0, "skipped": len(pending), "cost": 0.0}
    if not pending:
        return {"folder": name, "ok": 0, "failed": 0, "skipped": 0, "cost": 0.0}

    if dry_run:
        if not api_key:
            print(f"    ! no API key for {provider} (add {pconf['key_names'][0]} to keys.txt)")
        price = P.price_for(provider, model)
        est_total = 0.0
        for entry in pending:
            atts = attachments_for(entry)
            in_chars = len(prompt) + len(fmt_note)
            for nm, p, kind in atts:
                if kind == "text":
                    try:
                        in_chars += p.stat().st_size
                    except OSError:
                        pass
                elif kind == "image":
                    in_chars += 4000          # rough image token-equivalent
            in_tok = max(1, in_chars // 4)
            out_tok = min(max_tokens or 1024, 1024)
            cost = (in_tok / 1000 * price[0] + out_tok / 1000 * price[1]) if price else 0.0
            est_total += cost
            tag = f"${cost:.4f}" if price else "$ n/a"
            print(f"    [DRY] '{entry.name}' ({len(atts)} file(s)) -> "
                  f"{provider}/{model} -> {out_fmt}  ~{in_tok} in tok, est {tag}")
        note = "" if price else "  (no pricing table for this model -- cost unknown)"
        print(f"    {name}: ~{len(pending)} call(s), est ${est_total:.4f}{note}")
        return {"folder": name, "ok": 0, "failed": 0,
                "skipped": len(pending), "cost": est_total}

    state = {"cost": 0.0, "ok": 0, "failed": 0, "skipped": 0}
    lock = threading.Lock()
    stop = threading.Event()

    def do_job(entry):
        stem = entry.stem if entry.is_file() else entry.name
        if stop.is_set():
            with lock:
                state["skipped"] += 1
            return
        claimed = unique(process / entry.name)
        try:
            shutil.move(str(entry), str(claimed))
        except FileNotFoundError:
            return
        print(f"    -> {entry.name} ...", flush=True)
        try:
            atts = attachments_for(claimed)
            context = retriever.retrieve(cfg, query_text(prompt, atts), folder)
            full_prompt = prompt + fmt_note + context
            result = api_client.call(
                provider=provider, model=model, api_key=api_key,
                prompt=full_prompt, attachments=atts,
                max_tokens=max_tokens, temperature=temperature,
                thinking=thinking, system=system,
            )
            out = outputs.write_output(outbox, stem, result, out_fmt, template_path)
            shutil.move(str(claimed), str(unique(outbox / f"{stem}.input{claimed.suffix}")))
            price = P.price_for(provider, model)
            cost = (result["input_tokens"] / 1000 * price[0] +
                    result["output_tokens"] / 1000 * price[1]) if price else 0.0
            ledger.record(name, entry.name, provider, model, "ok",
                          result["input_tokens"], result["output_tokens"],
                          cost, result["elapsed"], out.name)
            with lock:
                state["ok"] += 1
                state["cost"] += cost
                if max_cost is not None and state["cost"] >= max_cost:
                    stop.set()
            print(f"       done: {entry.name} ({result['output_tokens']} tok, "
                  f"{result['elapsed']:.1f}s, ${cost:.4f}) -> {out.name}")
        except Exception as exc:                       # noqa: BLE001
            shutil.move(str(claimed), str(unique(wait / claimed.name)))
            write_error(wait, stem, exc)
            ledger.record(name, entry.name, provider, model, "failed",
                          error=f"{exc.__class__.__name__}: {exc}")
            with lock:
                state["failed"] += 1
            print(f"       FAILED: {entry.name}: {exc.__class__.__name__} "
                  f"(see wait/{stem}.error.txt)")

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(do_job, pending))
    else:
        for entry in pending:
            do_job(entry)

    if stop.is_set():
        print(f"    ! budget cap (${max_cost:.2f}) reached -- remaining jobs left in inbox/")
    print(f"    {name}: {state['ok']} ok, {state['failed']} failed, "
          f"${state['cost']:.4f}")
    return {"folder": name, **state}


def main():
    ap = argparse.ArgumentParser(description="Process one api_call_NN folder's inbox.")
    ap.add_argument("folder")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=1, help="Parallel calls (default 1)")
    ap.add_argument("--max-cost", type=float, default=None, help="Stop after ~$ this much")
    ap.add_argument("--retry-failed", action="store_true",
                    help="Move wait/ jobs back to inbox/ before running")
    args = ap.parse_args()
    process_folder(args.folder, dry_run=args.dry_run, workers=args.workers,
                   max_cost=args.max_cost, retry=args.retry_failed)


if __name__ == "__main__":
    main()
