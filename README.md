# Multi-AI Call System

Run your prompts and files through **any AI provider you have a key for** —
OpenAI, Anthropic (Claude), DeepSeek, Moonshot/Kimi, Google Gemini, or xAI
(Grok) — one at a time or several in a row, with a cost preview before you
spend a cent.

It is **folder-driven** and **portable**: copy the whole folder anywhere, run
it, and it works. Nothing is tied to where it lives on disk.

---

## The 30-second version

1. Copy `config.example.txt` to `config.txt` and paste in the API keys you have.
2. **Windows:** double-click `RUN.bat`. **Mac/Linux:** run `./run.sh`.
3. It creates 10 job folders, you pick which jobs and which providers, it shows
   you the cost, you say yes, it runs.

Answers land in two places: each job's own `outbox/`, and a single shared
`output/` folder where everything accumulates with a dated filename like
`anthropic_2026-06-25_1430_API_CALL_01_word-cluster.txt`.

---

## How the folders work

Running `init` (or the launcher) creates this:

```
jobs/
  API_CALL_01/
    prompt/prompt.txt   <- what you want done
    inbox/              <- drop the files to work on here
    process/            <- files move here after a successful run
    outbox/             <- this job's answers
    job.txt             <- optional per-job settings
  API_CALL_02/
  ... up to API_CALL_10 (make more with --count)

output/                 <- shared accumulator: EVERY answer also lands here,
                           dated and named, so it piles up in one place
```

Each numbered folder is one **job**. Put a prompt in `prompt/prompt.txt`, drop
files in `inbox/`, and that's a unit of work. Add `API_CALL_11`, `_12`, … just
by following the same naming.

### Two ways to feed a job

- **Drop files in `inbox/`** — the normal way. After a successful run they move
  to `process/` so the inbox is clear for next time (set `KEEP_INBOX=true` to
  leave them).
- **Point at a file or folder** — set `SOURCE=` in that job's `job.txt` to read
  an external file directly instead of the inbox. Example: an Obsidian note at
  `C:\Vault\paper.md`. The original is never moved or touched.

---

## Picking providers and running a sequence

A "sequence" just means running your selected jobs through more than one
provider, one after another. The interactive menu asks you; from the command
line:

```
python ai_call.py dry-run                                   # cost preview, all jobs, all keys
python ai_call.py run --provider anthropic --jobs all       # one provider, all jobs
python ai_call.py run --providers anthropic,openai --jobs 01,02   # two providers in sequence
python ai_call.py list                                      # show keys + jobs
python ai_call.py init --count 20                           # make 20 job folders
```

You can also pin a single job to one provider/model inside its `job.txt`:

```
PROVIDER=anthropic
MODEL=claude-haiku-4-5
DESCRIPTION=word-cluster
```

---

## Always dry-run first

The dry run sends nothing. It estimates the input size of every job and prints
the cost on each provider so you can choose the cheapest one that's good enough,
plus money-saving tips (Batch APIs that halve cost if you can wait 24h, DeepSeek
off-peak discounts, prompt caching, proxy/SOCKS notes). Then it asks before
spending real money.

> Prices in the dry run are **approximate** and stored in `providers.py`. Update
> them there when a provider changes pricing.

---

## Adding a new provider

Open `providers.py` and add one entry to `PROVIDERS`. If the service speaks the
OpenAI API (most do), set `"api": "openai"` and give it a `base_url`. That's the
only change needed — the rest of the system picks it up automatically.

---

## Files at a glance

| File | What it is |
|------|------------|
| `ai_call.py` | the engine + command line + interactive menu |
| `providers.py` | the list of providers, models, prices, and tips |
| `config.txt` | your API keys (you create this; never committed) |
| `RUN.bat` / `run.sh` | double-click launchers (menu) |
| `DRY_RUN.bat` | cost-preview launcher |
| `call_openai.py` | the original single-provider OpenAI script (still works) |

---

## Notes / future hooks

- **Vectorization / Postgres / direct DB pointing** is not built in yet. The
  `SOURCE=` mechanism already lets a job read any file or folder on disk
  (including a vault), which covers most "point at my paper" cases. Pulling from
  a vector store or Postgres would be the next extension — it would slot in as a
  new kind of `SOURCE`.
- Keys can be set as environment variables instead of `config.txt`, which helps
  when moving the folder between machines.
