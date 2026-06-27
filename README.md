# Multi-API Batch Processor

Drop files into folders, walk away, and let OpenAI / Anthropic (Claude) /
DeepSeek / Kimi answer hundreds of prompts unattended.

This is a **folder-based job queue**. You get 10 ready-made "stations"
(`api_call_01` … `api_call_10`), and you can add as many more as you want.
Each station runs **one prompt** against **one API provider**, over and over,
for every file you drop into its `inbox/`.

```
Open-AI-CALL/
├── keys.txt                 <- your API keys (paste once; git-ignored)
├── INSTALL.bat / .sh        <- one-time: install the Python packages
├── DRY_RUN_ALL.bat / .sh    <- estimate the cost; makes NO API calls
├── RUN_ALL.bat / .sh        <- process EVERY folder's inbox (4 at a time)
├── TROUBLESHOOT_ALL.bat/.sh <- health-check everything (keys, configs, queues)
├── NEW_FOLDER.bat / .sh     <- scaffold the next station (11th, 12th, ...)
│
├── api_call_01/             <- one "station"
│   ├── config.txt           <-   which provider + model
│   ├── prompt.txt           <-   what this station does
│   ├── inbox/               <-   drop files here (each file = one API call)
│   ├── process/             <-   in-flight (auto; empty when idle)
│   ├── outbox/              <-   finished answers
│   ├── wait/                <-   failed jobs (with .error.txt; retry-able)
│   ├── templates/           <-   optional .xlsx/.html to write the answer into
│   ├── RUN.bat / .sh        <-   process just this station
│   └── TROUBLESHOOT.bat/.sh <-   health-check just this station
├── api_call_02/  ...  api_call_10/
│
├── _template/               <- the blueprint NEW_FOLDER copies
└── core/                    <- the shared engine (providers, client, worker)
```

## The outer "operating" scripts (work for ANY number of folders)

These five live at the top level and always act on **every** `api_call_*` folder
that exists — whether you have 10, 11, or 50. Add folders and they're picked up
automatically; you never edit these scripts.

| Script | What it does |
|--------|--------------|
| `INSTALL`          | One-time: installs the Python packages |
| `DRY_RUN_ALL`      | Estimates the cost of everything queued — **spends nothing** |
| `RUN_ALL`          | Processes every inbox, **4 calls at a time** (override: `RUN_ALL.bat --workers 8`) |
| `TROUBLESHOOT_ALL` | Health-checks keys, configs, queues, and recent errors |
| `NEW_FOLDER`       | Creates the next station (`api_call_11`, `12`, …) from `_template` |

`_template/` is the blueprint. `NEW_FOLDER` copies it to the next number — that's
how you "pop out" an 11th folder. (You can also just copy any `api_call_NN`
folder and rename it; each one is fully self-contained.)

## Quick start

1. **Install Python 3.8+** (https://www.python.org/downloads/). On Windows,
   check *"Add Python to PATH"* during install. Then double-click
   **`INSTALL.bat`** (Mac/Linux: `./INSTALL.sh`) to install the packages.

2. **Add your keys.** Copy `keys.example.txt` → `keys.txt` and paste in the
   keys for the providers you use. You only paste each key **once** — every
   folder using that provider shares it.

   ```
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   DEEPSEEK_API_KEY=sk-...
   KIMI_API_KEY=sk-...
   ```

3. **Set up each station.** In any `api_call_NN` folder:
   - `config.txt` — pick `PROVIDER` (openai / anthropic / deepseek / kimi)
     and `MODEL`.
   - `prompt.txt` — write what that station should do.

4. **Drop files** into a station's `inbox/`. Each file becomes one API call
   (your prompt + that file's contents).

5. **(Optional) Check the price first:** double-click **`DRY_RUN_ALL.bat`** —
   it lists every call that would run and an estimated total cost, without
   spending anything.

6. **Run it.**
   - One station: double-click its `RUN.bat` (Mac/Linux: `./RUN.sh`).
   - **All stations at once: `RUN_ALL.bat`** — runs 4 at a time. For more,
     `RUN_ALL.bat --workers 8`.

   Answers land in each station's `outbox/`. Failures land in `wait/` with a
   `.error.txt` explaining why — or just run `RUN_ALL.bat --retry-failed`.

## How a job flows

```
inbox/  ──►  process/  ──►  outbox/   (success: answer + archived input)
                      └──►  wait/     (failure: input + .error.txt)
```

`process/` should be empty when nothing is running. If a run is interrupted and
something is stuck there, just move it back to `inbox/`.

## "Hundreds of calls without touching it"

Queue up as much as you like across the 10 inboxes, then run `RUN_ALL`. It
takes each folder **all the way through** (its entire inbox) before moving to
the next, with automatic retries/backoff on rate limits and transient errors.

Useful flags (work on both `run_all.py` and a single folder's `worker.py`):

```
python run_all.py --workers 6        # 6 calls in parallel (much faster)
python run_all.py --max-cost 5.00    # stop the run near $5 (budget guardrail)
python run_all.py --retry-failed     # sweep every wait/ back into inbox/ and rerun
python run_all.py --loop 60          # keep running, re-scan every 60 seconds
python run_all.py --only api_call_03 # just these folders
```

Every job is logged to **`runs.csv`** (timestamp, folder, file, provider, model,
tokens, est. cost, status) and each pass prints a grand-total cost.

## Output formats and templates

Each folder's `config.txt` has `OUTPUT_FORMAT`:

| `OUTPUT_FORMAT=` | Saved as | Notes |
|------------------|----------|-------|
| `md` (default)   | `.md`    | answer + a metadata header |
| `txt`            | `.txt`   | just the text |
| `json`           | `.json`  | validated JSON |
| `csv`            | `.csv`   | spreadsheet rows |
| `html`           | `.html`  | an HTML page |
| `xlsx`           | `.xlsx`  | a real Excel file |

**Writing into a template:** drop a file in the folder's `templates/` folder.
- `templates/report.xlsx` → with `OUTPUT_FORMAT=xlsx`, the answer is written
  into a copy of that sheet under its column headers (the model is told to use
  exactly those columns).
- `templates/page.html` → with `OUTPUT_FORMAT=html`, the answer replaces the
  `{{OUTPUT}}` marker in your template.

## Referencing your vector engine (RAG)

When a station needs to consult your knowledge base / "the whole series" before
answering, set a `RETRIEVER` in its `config.txt`. The relevant context is
fetched and prepended to the prompt on every call:

| `RETRIEVER=` | What it does | Set |
|--------------|--------------|-----|
| `none` (default) | off | — |
| `folder`  | reads reference files from a folder | `RETRIEVER_PATH=` |
| `command` | runs your local search script and uses its output | `RETRIEVER_CMD=` |
| `http`    | POSTs `{"query","top_k"}` to an endpoint | `RETRIEVER_URL=` |

For a local vector engine, `command` is the wire-in point:

```
RETRIEVER=command
RETRIEVER_CMD=python C:\tools\my_vector_search.py "{query}"
```

`{query}` is replaced with the job's question (prompt + a sample of the input);
if you omit `{query}`, the question is sent to your script on **stdin**. Whatever
your script prints becomes the reference context. `RETRIEVER_MAX_CHARS` caps how
much gets injected.

## The four providers

| `PROVIDER=` | Service        | Example models                                   |
|-------------|----------------|--------------------------------------------------|
| `openai`    | OpenAI         | `gpt-4o`, `gpt-4o-mini`, `o3-mini`               |
| `anthropic` | Anthropic      | `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5` |
| `deepseek`  | DeepSeek       | `deepseek-chat`, `deepseek-reasoner`             |
| `kimi`      | Moonshot / Kimi| `kimi-k2-0905-preview`, `moonshot-v1-128k`       |

The 10 starter folders are pre-wired to cycle through all four providers so you
can see how each is configured — change any folder's `config.txt` to whatever
you want.

## Add more stations

`NEW_FOLDER` duplicates `_template` into the next number, **in order** — run it
again and again and you get 11, 12, 13, 14, … (no need to say which number):

```
NEW_FOLDER.bat                          (make the next one)
NEW_FOLDER.bat 5                        (make the next FIVE at once)
NEW_FOLDER.bat --provider anthropic     (next one, set its provider)
NEW_FOLDER.bat 3 --provider deepseek    (next three, all deepseek)
```

Mac/Linux: `./NEW_FOLDER.sh ...`. Or just copy any `api_call_NN` folder and
rename it — each folder is fully self-contained. All the outer scripts
(`RUN_ALL`, `DRY_RUN_ALL`, `TROUBLESHOOT_ALL`) automatically pick up the new
folders.

## Troubleshooting

Run **`TROUBLESHOOT_ALL.bat`** (Mac/Linux: `./TROUBLESHOOT_ALL.sh`). It checks,
without spending a cent:

- Python + whether the `openai` / `anthropic` packages are installed
- which provider keys it found in `keys.txt`
- each folder's config (known provider? model set? key resolvable? prompt set?)
- inbox / process / outbox / wait counts, and the most recent error per folder

Each station also has its own `TROUBLESHOOT.bat` / `.sh` for just that folder.

## Notes

- **Keys are never committed.** `keys.txt` is git-ignored; the per-folder
  `config.txt` files contain no secrets (just provider/model choices).
- **Dependencies** install automatically on first `RUN_ALL`, or manually with
  `pip install -r requirements.txt`.
- Vision/images work on `openai` and `anthropic`; `deepseek` and `deepseek`-style
  `kimi` chat models are text-only (images are noted and skipped).
- The old single-call scripts (`call_openai.py`, top-level `RUN.bat`) still work
  but are superseded by this folder system.
