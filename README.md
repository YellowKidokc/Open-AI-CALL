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
├── RUN_ALL.bat / .sh        <- process EVERY folder's inbox in one go
├── TROUBLESHOOT_ALL.bat/.sh <- health-check everything (keys, configs, queues)
├── NEW_FOLDER.bat / .sh     <- scaffold another station (expand past 10)
│
├── api_call_01/             <- one "station"
│   ├── config.txt           <-   which provider + model
│   ├── prompt.txt           <-   what this station does
│   ├── inbox/               <-   drop files here (each file = one API call)
│   ├── process/             <-   in-flight (auto; empty when idle)
│   ├── outbox/              <-   finished answers
│   ├── wait/                <-   failed jobs (with .error.txt; retry-able)
│   ├── RUN.bat / .sh        <-   process just this station
│   └── TROUBLESHOOT.bat/.sh <-   health-check just this station
├── api_call_02/  ...  api_call_10/
│
├── _template/               <- the blueprint NEW_FOLDER copies
└── core/                    <- the shared engine (providers, client, worker)
```

## Quick start

1. **Install Python 3.8+** (https://www.python.org/downloads/). On Windows,
   check *"Add Python to PATH"* during install.

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

5. **Run it.**
   - One station: double-click its `RUN.bat` (Mac/Linux: `./RUN.sh`).
   - **All stations at once: `RUN_ALL.bat`** (Mac/Linux: `./RUN_ALL.sh`).

   Answers land in each station's `outbox/`. Failures land in `wait/` with a
   `.error.txt` explaining why — move them back to `inbox/` to retry.

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

To keep it running and re-scanning for new files:

```
python run_all.py --loop 60      # re-scan every 60 seconds, Ctrl+C to stop
```

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

```
NEW_FOLDER.bat                          (next number, defaults to openai)
NEW_FOLDER.bat --provider anthropic
NEW_FOLDER.bat --provider deepseek --model deepseek-reasoner
```

Mac/Linux: `./NEW_FOLDER.sh ...`. Or just copy any `api_call_NN` folder and
rename it — each folder is fully self-contained.

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
