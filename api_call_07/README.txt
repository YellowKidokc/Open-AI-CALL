THIS FOLDER = ONE API "STATION"
================================

It runs ONE prompt against ONE provider, over and over, for every file you
drop into inbox/.

How to use it
-------------
1. config.txt   -> pick the PROVIDER (openai / anthropic / deepseek / kimi)
                   and MODEL for this folder.
2. prompt.txt   -> write what this folder should DO to each file.
3. inbox/       -> drop files in here. Each file = one API call.
4. RUN.bat      -> double-click. (Or run RUN_ALL in the parent folder to do
                   every folder at once.)

The four sub-folders
--------------------
  inbox/    jobs waiting to be processed
  process/  the job currently running (auto; should be empty when idle)
  outbox/   finished answers  (<name>.response.md  + the archived input)
  wait/     jobs that FAILED  (<name>.error.txt says why -- move back to
            inbox/ to retry)

Keys are NOT stored here. They live once in the repo-root keys.txt.

To make another station just like this one, run NEW_FOLDER in the parent
folder (or copy this whole folder and rename it api_call_NN).
