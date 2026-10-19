# Which Came First?

A daily game: five events from Wikipedia's *On this day* feed, put them in
chronological order. The plan, step by step, is in `todo.md`.

So far:

- **Step 1, the puzzle generator** (`puzzle_generator/`): plain Python, no Django.
- **Step 2, the game service** (`config/`, `game/`): Django and Postgres. A page
  with drag-to-reorder, a small JSON API, and anonymous players.
- **Step 3, CI** (`.github/workflows/ci.yml`): tests against a real Postgres,
  lint, formatting, types and migrations, on every pull request and push to `main`.
- **Step 4, the container** (`Dockerfile`): one image for the server, the
  migrations and the generator. CI builds and smoke-tests it, and on `main`
  pushes it to ghcr.io tagged with the commit.

## Setup

Needs Python 3.13 and Docker Desktop (for Postgres).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env      # then fill in WCF_CONTACT; keep DJANGO_DEBUG=1
docker compose up -d        # Postgres on 127.0.0.1:5432
python manage.py migrate
```

`WCF_CONTACT` goes into the User-Agent sent to Wikipedia. Wikimedia's policy
requires one that says who is calling and how to reach them: a repo URL or an
email address.

## Play locally

```powershell
python manage.py generate_puzzle    # today's puzzle (UTC), from the live feed
python manage.py runserver          # http://127.0.0.1:8000
```

`generate_puzzle` skips a date that already has a puzzle; `--force` replaces it,
unless someone has played it. `--date YYYY-MM-DD` picks another day.

To look at the stored puzzles (answers included), make an admin user with
`python manage.py createsuperuser` and open http://127.0.0.1:8000/admin/.

## Run the production image

The image as a host will run it: gunicorn, debug off, static files from
WhiteNoise. Against the compose database:

```powershell
docker compose up --build app                 # http://localhost:8080
docker compose run --rm app migrate
docker compose run --rm app generate          # same flags as generate_puzzle
```

The image takes one of three commands, `serve` (the default), `migrate` and
`generate`, described at the top of `config/entrypoint.py`. Any other command
goes to `manage.py`, e.g. `docker compose run --rm app createsuperuser`.

The server listens on `0.0.0.0:$PORT` (default 8000). `/healthz` answers while
the process is up; `/readyz` only while it can also reach the database.

## Generate a puzzle file without the database

```powershell
python -m puzzle_generator                     # today (UTC) -> output/puzzles/YYYY-MM-DD.json
python -m puzzle_generator --stdout            # print the JSON instead; shows the answers
python -m puzzle_generator --feed events -v    # the bigger, noisier feed, with debug logs
```

Exit codes, the same for both generators, are listed at the top of
`puzzle_generator/cli.py`.

## Checks

The same ones CI will run. The tests need Postgres running.

```powershell
pytest
ruff check .
ruff format --check .
mypy
python manage.py makemigrations --check --dry-run
```
