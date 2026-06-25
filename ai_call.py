#!/usr/bin/env python3
"""
Multi-AI Call System
====================
A portable, folder-driven way to run prompts + files through one or more
AI providers (OpenAI, Anthropic/Claude, DeepSeek, Moonshot/Kimi, Gemini, xAI).

THE IDEA
--------
You have numbered "job" folders.  Each job is one unit of work:

    jobs/API_CALL_01/
        prompt/prompt.txt   <- what you want done
        inbox/              <- drop the files to work on here (optional)
        process/            <- files get moved here after a successful run
        outbox/             <- this job's answers land here
        job.txt             <- optional per-job settings (provider, model, source)

There is also ONE shared accumulator:

    output/   <- every answer is ALSO copied here with a dated, named file
                 e.g.  anthropic_2026-06-25_1430_API_CALL_01.txt

You can run one job, several jobs, or all of them — through one provider or
through several providers one after another (a "sequence").

This script is location-independent: it always works relative to its OWN
folder, so you can copy the whole folder anywhere and it still runs.

QUICK START
-----------
    python ai_call.py menu                 interactive — recommended
    python ai_call.py init                 create the jobs/ folders
    python ai_call.py list                 show providers + jobs + key status
    python ai_call.py dry-run              cost preview across providers
    python ai_call.py run --provider anthropic --jobs all
    python ai_call.py run --providers anthropic,openai --jobs 01,02
"""

import os
import sys
import json
import base64
import shutil
import pathlib
import argparse
import datetime
import mimetypes

import providers as P

# ---------------------------------------------------------------------------
#  Locations — everything is relative to THIS file, so the folder is portable.
# ---------------------------------------------------------------------------
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.txt"
JOBS_DIR = SCRIPT_DIR / "jobs"
GLOBAL_OUTPUT_DIR = SCRIPT_DIR / "output"
GLOBAL_PROMPT = SCRIPT_DIR / "prompt.txt"        # fallback prompt for old-style use

DEFAULT_JOB_COUNT = 10                            # how many folders `init` makes

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".c", ".cpp", ".h", ".java", ".rb",
    ".rs", ".go", ".sh", ".bat", ".ps1", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".log", ".sql", ".r",
    ".tex", ".bib", ".rst", ".org", ".eml",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# ===========================================================================
#  Config
# ===========================================================================

def parse_config(path: pathlib.Path) -> dict:
    """Read KEY=VALUE pairs from config.txt (comments with # are ignored)."""
    cfg = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            cfg[key.strip()] = value.strip()
    return cfg


def get_api_key(provider_id: str, cfg: dict) -> str:
    """API key from config.txt first, then environment. Empty string if missing."""
    key_var = P.PROVIDERS[provider_id]["key_var"]
    val = cfg.get(key_var, "") or os.environ.get(key_var, "")
    if val.startswith("sk-PASTE") or val.startswith("PASTE"):
        val = ""
    return val.strip()


def configured_providers(cfg: dict) -> list:
    """Provider ids that have a usable API key, in display order."""
    return [pid for pid in P.PROVIDER_ORDER if get_api_key(pid, cfg)]


# ===========================================================================
#  Jobs
# ===========================================================================

def job_subdirs(job_dir: pathlib.Path) -> dict:
    return {
        "prompt":  job_dir / "prompt",
        "inbox":   job_dir / "inbox",
        "process": job_dir / "process",
        "outbox":  job_dir / "outbox",
    }


def init_jobs(count: int = DEFAULT_JOB_COUNT):
    """Create jobs/API_CALL_01 .. NN with the inbox/prompt/process/outbox layout."""
    JOBS_DIR.mkdir(exist_ok=True)
    GLOBAL_OUTPUT_DIR.mkdir(exist_ok=True)
    (GLOBAL_OUTPUT_DIR / ".gitkeep").touch()

    for i in range(1, count + 1):
        name = f"API_CALL_{i:02d}"
        job_dir = JOBS_DIR / name
        subs = job_subdirs(job_dir)
        for d in subs.values():
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()

        prompt_file = subs["prompt"] / "prompt.txt"
        if not prompt_file.exists():
            prompt_file.write_text(
                "# Prompt for {name}\n"
                "# Write what you want the AI to do with the files in inbox/.\n"
                "# Lines starting with # are ignored.\n\n"
                "Summarize the attached files and list the key points.\n".format(name=name),
                encoding="utf-8",
            )

        job_cfg = job_dir / "job.txt"
        if not job_cfg.exists():
            job_cfg.write_text(
                "# Optional per-job settings. Delete or leave blank to use defaults.\n"
                "# PROVIDER=anthropic        # force this job onto one provider\n"
                "# MODEL=claude-haiku-4-5    # force a specific model\n"
                "# SOURCE=                   # a file OR folder to read INSTEAD of inbox/\n"
                "#                           # (e.g. an Obsidian note: C:\\Vault\\paper.md)\n"
                "# DESCRIPTION=word-cluster  # short tag added to the output filename\n",
                encoding="utf-8",
            )
    print(f"Created {count} job folders under {JOBS_DIR}")


def discover_jobs() -> list:
    """Return sorted list of job folder names like ['API_CALL_01', ...]."""
    if not JOBS_DIR.exists():
        return []
    return sorted(
        p.name for p in JOBS_DIR.iterdir()
        if p.is_dir() and p.name.upper().startswith("API_CALL")
    )


def resolve_job_selection(selection: str) -> list:
    """Turn '01,03' or 'all' or 'API_CALL_02' into a list of job folder names."""
    jobs = discover_jobs()
    if not selection or selection.lower() == "all":
        return jobs
    wanted = []
    for tok in selection.split(","):
        tok = tok.strip()
        if not tok:
            continue
        # accept '1', '01', 'API_CALL_01'
        match = None
        for j in jobs:
            if j == tok or j.upper() == tok.upper():
                match = j
                break
            num = j.split("_")[-1]
            if tok.zfill(2) == num:
                match = j
                break
        if match:
            wanted.append(match)
        else:
            print(f"  (warning: no job matches '{tok}')")
    return wanted


def read_job_config(job_dir: pathlib.Path) -> dict:
    return parse_config(job_dir / "job.txt")


def read_prompt(job_dir: pathlib.Path) -> str:
    """Prompt from job's prompt/prompt.txt, falling back to the global prompt.txt."""
    for candidate in (job_dir / "prompt" / "prompt.txt", GLOBAL_PROMPT):
        if candidate.exists():
            lines = candidate.read_text(encoding="utf-8").splitlines()
            text = "\n".join(l for l in lines if not l.strip().startswith("#")).strip()
            if text:
                return text
    return ""


# ===========================================================================
#  Inputs (files)
# ===========================================================================

def classify_file(path: pathlib.Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in TEXT_EXTENSIONS or _looks_like_text(path):
        return "text"
    return "binary_skip"


def _looks_like_text(path: pathlib.Path) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            f.read(8192)
        return True
    except (UnicodeDecodeError, PermissionError, OSError):
        return False


def gather_inputs(job_dir: pathlib.Path, job_cfg: dict) -> list:
    """
    Return list of (display_name, abs_path, kind).

    If job.txt sets SOURCE=<file-or-folder> we read from there (e.g. an
    Obsidian note or any path on disk).  Otherwise we read the job's inbox/.
    """
    source = job_cfg.get("SOURCE", "").strip()
    files = []

    if source:
        src = pathlib.Path(os.path.expanduser(source))
        if not src.is_absolute():
            src = (SCRIPT_DIR / src).resolve()
        if src.is_file():
            files.append((src.name, src, classify_file(src)))
        elif src.is_dir():
            for p in sorted(src.rglob("*")):
                if p.is_file() and p.name != ".gitkeep":
                    files.append((str(p.relative_to(src)), p, classify_file(p)))
        else:
            print(f"  (warning: SOURCE path not found: {src})")
        return files

    inbox = job_dir / "inbox"
    if inbox.exists():
        for p in sorted(inbox.rglob("*")):
            if p.is_file() and p.name != ".gitkeep":
                files.append((str(p.relative_to(inbox)), p, classify_file(p)))
    return files


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)        # ~4 chars per token, rough English heuristic


# ===========================================================================
#  Building the request payload (provider-agnostic)
# ===========================================================================

def build_text_blob(prompt_text: str, files: list, vision_ok: bool) -> tuple:
    """
    Combine the prompt and all TEXT files into one string, and collect images
    separately.  Returns (combined_text, images) where images is a list of
    (media_type, base64_data).  Images are only collected if vision_ok.
    """
    parts = [prompt_text]
    images = []
    for name, path, kind in files:
        if kind == "text":
            body = path.read_text(encoding="utf-8", errors="replace")
            parts.append(f"\n\n--- FILE: {name} ---\n{body}")
        elif kind == "image":
            if vision_ok:
                mime = mimetypes.guess_type(str(path))[0] or "image/png"
                data = base64.b64encode(path.read_bytes()).decode("ascii")
                images.append((mime, data))
            else:
                parts.append(f"\n\n[Skipped image {name}: this provider's model has no vision]")
        else:
            parts.append(f"\n\n[Skipped binary file {name}]")
    return "\n".join(parts), images


# ===========================================================================
#  Provider adapters
# ===========================================================================

def call_openai_compatible(provider_id, model, api_key, prompt_text, files, cfg):
    """OpenAI-style Chat Completions — works for OpenAI, DeepSeek, Moonshot, Gemini, xAI."""
    try:
        import openai
    except ImportError:
        raise RuntimeError("The 'openai' package is not installed. Run: pip install openai")

    prov = P.PROVIDERS[provider_id]
    text, images = build_text_blob(prompt_text, files, prov["vision"])

    content = [{"type": "text", "text": text}]
    for mime, data in images:
        content.append({"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{data}"}})
    messages = [{"role": "user", "content": content}]

    client = openai.OpenAI(api_key=api_key, base_url=prov["base_url"])
    kwargs = {"model": model, "messages": messages}
    max_tokens = int(cfg.get("MAX_TOKENS", "4096") or 0)
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    temperature = cfg.get("TEMPERATURE")
    if temperature:
        kwargs["temperature"] = float(temperature)

    resp = client.chat.completions.create(**kwargs)
    reply = resp.choices[0].message.content or ""
    usage = resp.usage
    in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    return reply, in_tok, out_tok


def call_anthropic(provider_id, model, api_key, prompt_text, files, cfg):
    """Anthropic Messages API — Claude models."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("The 'anthropic' package is not installed. Run: pip install anthropic")

    prov = P.PROVIDERS[provider_id]
    text, images = build_text_blob(prompt_text, files, prov["vision"])

    content = [{"type": "text", "text": text}]
    for mime, data in images:
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": data}})
    messages = [{"role": "user", "content": content}]

    client = anthropic.Anthropic(api_key=api_key)
    max_tokens = int(cfg.get("MAX_TOKENS", "4096") or 4096)
    resp = client.messages.create(model=model, max_tokens=max_tokens, messages=messages)

    reply = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    usage = resp.usage
    in_tok = getattr(usage, "input_tokens", 0) if usage else 0
    out_tok = getattr(usage, "output_tokens", 0) if usage else 0
    return reply, in_tok, out_tok


def call_provider(provider_id, model, api_key, prompt_text, files, cfg):
    api = P.PROVIDERS[provider_id]["api"]
    if api == "anthropic":
        return call_anthropic(provider_id, model, api_key, prompt_text, files, cfg)
    return call_openai_compatible(provider_id, model, api_key, prompt_text, files, cfg)


# ===========================================================================
#  Output
# ===========================================================================

def save_output(reply, provider_id, model, job_name, job_dir, description):
    """Write to the job's outbox/ AND the shared output/ accumulator (dated)."""
    now = datetime.datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H%M")
    desc = (description or "").strip().replace(" ", "-")
    tag = f"_{desc}" if desc else ""

    header = (
        f"# {P.PROVIDERS[provider_id]['label']}  |  model: {model}\n"
        f"# job: {job_name}  |  {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'='*60}\n\n"
    )
    body = header + reply

    GLOBAL_OUTPUT_DIR.mkdir(exist_ok=True)
    fname = f"{provider_id}_{stamp}_{job_name}{tag}.txt"
    global_path = GLOBAL_OUTPUT_DIR / fname
    global_path.write_text(body, encoding="utf-8")

    outbox = job_dir / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    (outbox / fname).write_text(body, encoding="utf-8")

    return global_path


def archive_inputs(job_dir: pathlib.Path, files: list, job_cfg: dict):
    """Move successfully-processed inbox files into process/ (unless KEEP_INBOX=true)."""
    if job_cfg.get("SOURCE", "").strip():
        return                                  # external source: never move user's files
    if str(job_cfg.get("KEEP_INBOX", "")).lower() in ("true", "1", "yes"):
        return
    process = job_dir / "process"
    process.mkdir(parents=True, exist_ok=True)
    inbox = job_dir / "inbox"
    for _name, path, _kind in files:
        try:
            if inbox in path.parents:
                dest = process / path.relative_to(inbox)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(dest))
        except Exception as e:
            print(f"    (could not archive {path.name}: {e})")


# ===========================================================================
#  Dry run (cost preview)
# ===========================================================================

def estimate_job_input_tokens(job_dir, job_cfg) -> int:
    files = gather_inputs(job_dir, job_cfg)
    prompt_text = read_prompt(job_dir)
    text, _images = build_text_blob(prompt_text, files, vision_ok=False)
    return estimate_tokens(text)


def dry_run(cfg, job_names, provider_ids, assumed_output_tokens=1500):
    print("=" * 64)
    print("  DRY RUN — no API calls, estimated cost only")
    print("=" * 64)

    if not job_names:
        print("  No jobs found. Run:  python ai_call.py init")
        return

    grand_total = {pid: 0.0 for pid in provider_ids}
    for job_name in job_names:
        job_dir = JOBS_DIR / job_name
        job_cfg = read_job_config(job_dir)
        in_tok = estimate_job_input_tokens(job_dir, job_cfg)
        n_files = len(gather_inputs(job_dir, job_cfg))
        print(f"\n  {job_name}  (~{in_tok:,} input tokens, {n_files} file(s))")

        forced = job_cfg.get("PROVIDER", "").strip().lower()
        for pid in provider_ids:
            if forced and forced != pid:
                continue
            model = job_cfg.get("MODEL", "").strip() or P.resolve_model(pid, cfg)
            price = P.price_for(pid, model)
            label = P.PROVIDERS[pid]["label"]
            if not price:
                print(f"      {label:22s} {model:24s}  (no pricing data)")
                continue
            in_rate, out_rate = price
            cost = (in_tok / 1000) * in_rate + (assumed_output_tokens / 1000) * out_rate
            grand_total[pid] += cost
            print(f"      {label:22s} {model:24s}  ~${cost:.4f}")

    print("\n" + "-" * 64)
    print("  ESTIMATED TOTAL to run ALL selected jobs, per provider:")
    for pid in provider_ids:
        if grand_total[pid]:
            print(f"      {P.PROVIDERS[pid]['label']:22s} ~${grand_total[pid]:.4f}")

    print("\n  TIPS:")
    for t in P.GENERAL_TIPS:
        print(f"    - {t}")
    for pid in provider_ids:
        for t in P.PROVIDERS[pid]["tips"]:
            print(f"    - [{P.PROVIDERS[pid]['label']}] {t}")
    print("=" * 64)


# ===========================================================================
#  Real run
# ===========================================================================

def run_jobs(cfg, job_names, provider_ids):
    if not job_names:
        print("No jobs found. Run:  python ai_call.py init")
        return

    print("=" * 64)
    print(f"  RUNNING {len(job_names)} job(s) through "
          f"{len(provider_ids)} provider(s) in sequence")
    print("=" * 64)

    for pid in provider_ids:
        api_key = get_api_key(pid, cfg)
        if not api_key:
            print(f"\n!! Skipping {P.PROVIDERS[pid]['label']}: no API key configured.")
            continue

        print(f"\n### PROVIDER: {P.PROVIDERS[pid]['label']}")
        for job_name in job_names:
            job_dir = JOBS_DIR / job_name
            job_cfg = read_job_config(job_dir)

            forced = job_cfg.get("PROVIDER", "").strip().lower()
            if forced and forced != pid:
                print(f"  - {job_name}: pinned to '{forced}', skipping on {pid}")
                continue

            model = job_cfg.get("MODEL", "").strip() or P.resolve_model(pid, cfg)
            prompt_text = read_prompt(job_dir)
            if not prompt_text:
                print(f"  - {job_name}: no prompt, skipping")
                continue
            files = gather_inputs(job_dir, job_cfg)

            print(f"  - {job_name}: model={model}, {len(files)} file(s) ... ", end="", flush=True)
            try:
                reply, in_tok, out_tok = call_provider(
                    pid, model, api_key, prompt_text, files, {**cfg, **job_cfg})
            except Exception as e:
                print(f"FAILED\n      {e}")
                continue

            out_path = save_output(reply, pid, model, job_name, job_dir,
                                   job_cfg.get("DESCRIPTION", ""))
            archive_inputs(job_dir, files, job_cfg)

            price = P.price_for(pid, model)
            cost_str = ""
            if price and (in_tok or out_tok):
                cost = (in_tok / 1000) * price[0] + (out_tok / 1000) * price[1]
                cost_str = f", ~${cost:.4f}"
            print(f"OK ({in_tok}+{out_tok} tok{cost_str})")
            print(f"      -> {out_path.relative_to(SCRIPT_DIR)}")

    print("\n" + "=" * 64)
    print(f"  Done. Answers are in  output/  and each job's  outbox/")
    print("=" * 64)


# ===========================================================================
#  Listing / status
# ===========================================================================

def show_status(cfg):
    print("=" * 64)
    print("  PROVIDERS")
    print("=" * 64)
    for pid in P.PROVIDER_ORDER:
        prov = P.PROVIDERS[pid]
        has_key = "YES" if get_api_key(pid, cfg) else "no "
        model = P.resolve_model(pid, cfg)
        print(f"  [{has_key}] {prov['label']:22s} default model: {model}")
    print("\n  (set keys in config.txt or as environment variables)")

    print("\n" + "=" * 64)
    print("  JOBS")
    print("=" * 64)
    jobs = discover_jobs()
    if not jobs:
        print("  (none yet — run:  python ai_call.py init)")
    for j in jobs:
        job_dir = JOBS_DIR / j
        job_cfg = read_job_config(job_dir)
        n_files = len(gather_inputs(job_dir, job_cfg))
        src = job_cfg.get("SOURCE", "").strip()
        where = f"SOURCE={src}" if src else f"{n_files} file(s) in inbox"
        pinned = job_cfg.get("PROVIDER", "").strip()
        pin = f"  [pinned:{pinned}]" if pinned else ""
        print(f"  {j}  ({where}){pin}")
    print("=" * 64)


# ===========================================================================
#  Interactive menu
# ===========================================================================

def menu():
    cfg = parse_config(CONFIG_PATH)

    print("\n" + "=" * 64)
    print("  MULTI-AI CALL SYSTEM")
    print("=" * 64)

    if not discover_jobs():
        ans = input("\nNo job folders found. Create 10 now? [Y/n] ").strip().lower()
        if ans in ("", "y", "yes"):
            init_jobs()

    show_status(cfg)

    avail = configured_providers(cfg)
    if not avail:
        print("\n!! No API keys configured yet.")
        print("   Open config.txt and paste at least one key, then run again.")
        return

    # --- choose providers ---
    print("\nWhich provider(s)?  Enter comma-separated names to run them in")
    print("sequence (e.g. 'anthropic,openai'), or 'all' for every key you have.")
    print(f"Available: {', '.join(avail)}")
    raw = input("Providers [all]: ").strip().lower()
    if not raw or raw == "all":
        provider_ids = avail
    else:
        provider_ids = [p.strip() for p in raw.split(",")
                        if p.strip() in P.PROVIDERS and get_api_key(p.strip(), cfg)]
    if not provider_ids:
        print("No usable providers selected.")
        return

    # --- choose jobs ---
    raw = input("Which jobs?  e.g. '01,03' or 'all' [all]: ").strip()
    job_names = resolve_job_selection(raw or "all")
    if not job_names:
        print("No jobs selected.")
        return

    # --- dry run first ---
    print()
    dry_run(cfg, job_names, provider_ids)

    ans = input("\nProceed with the REAL run for real money? [y/N] ").strip().lower()
    if ans in ("y", "yes"):
        run_jobs(cfg, job_names, provider_ids)
    else:
        print("Stopped. Nothing was sent.")


# ===========================================================================
#  CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run prompts + files through one or more AI providers.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("menu", help="interactive menu (recommended)")
    sub.add_parser("list", help="show providers, key status, and jobs")

    p_init = sub.add_parser("init", help="create the jobs/ folder structure")
    p_init.add_argument("--count", type=int, default=DEFAULT_JOB_COUNT)

    for name in ("dry-run", "run"):
        sp = sub.add_parser(name, help=("cost preview" if name == "dry-run" else "run for real"))
        sp.add_argument("--provider", help="single provider id (e.g. anthropic)")
        sp.add_argument("--providers", help="comma list, run in sequence (e.g. anthropic,openai)")
        sp.add_argument("--jobs", default="all", help="e.g. 01,03 or all")

    args = parser.parse_args()
    cfg = parse_config(CONFIG_PATH)

    if args.command in (None, "menu"):
        menu()
        return
    if args.command == "list":
        show_status(cfg)
        return
    if args.command == "init":
        init_jobs(args.count)
        return

    # dry-run / run share provider+job resolution
    if args.providers:
        provider_ids = [p.strip() for p in args.providers.split(",") if p.strip() in P.PROVIDERS]
    elif args.provider:
        provider_ids = [args.provider] if args.provider in P.PROVIDERS else []
    else:
        provider_ids = configured_providers(cfg) or P.PROVIDER_ORDER

    if not provider_ids:
        print("No valid providers. Use --provider or --providers with a known id:")
        print("  " + ", ".join(P.PROVIDER_ORDER))
        return

    job_names = resolve_job_selection(args.jobs)

    if args.command == "dry-run":
        dry_run(cfg, job_names, provider_ids)
    elif args.command == "run":
        run_jobs(cfg, job_names, provider_ids)


if __name__ == "__main__":
    main()
