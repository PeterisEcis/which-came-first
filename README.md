# Which Came First?

A daily game: five events from Wikipedia's *On this day* feed, put them in
chronological order. The plan, step by step, is in `todo.md`.

So far: **Step 1, the puzzle generator** (`puzzle_generator/`). Plain Python, no
Django yet. The game service in Step 2 will import it.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env   # then fill in WCF_CONTACT
```

`WCF_CONTACT` goes into the User-Agent sent to Wikipedia. Wikimedia's policy
requires one that says who is calling and how to reach them: a repo URL or an
email address.

## Generate a puzzle

```powershell
python -m puzzle_generator                     # today (UTC) -> output/puzzles/YYYY-MM-DD.json
python -m puzzle_generator --date 2026-10-13
python -m puzzle_generator --stdout            # print the JSON instead; shows the answers
python -m puzzle_generator --feed events -v    # the bigger, noisier feed, with debug logs
```

A date that already has a file is skipped; `--force` regenerates it. Exit codes
are listed at the top of `puzzle_generator/cli.py`.

## Checks

The same ones CI will run:

```powershell
pytest
ruff check .
ruff format --check .
mypy
```
