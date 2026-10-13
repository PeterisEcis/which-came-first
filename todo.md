# Daily Timeline Quiz — TODO

Daily "which came first?" game: five events from Wikipedia's *On this day* feed,
players put them in chronological order. The real goal is learning the CI/CD steps the
proverb app had no reason to need: a real service, a database, migrations, deploys with
rollback, and a human approval gate. Each one is required here, not contrived.

**Current tier: Step 1 done. No GitHub Pages — a real service from day one.**

Why it can't be static: the answer (the years) must not reach the browser before the
player finishes. A static site would have to ship it.

---

## Progression

### Step 1 — Puzzle generator (local)
- [x] Fetch events from the *On this day* feed:
      `https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected/{MM}/{DD}`
      — `selected` (~15–20 curated per day) is cleaner than `events` (~50)
- [x] Pick 5 events, deterministic by date (same idea as the proverb pick)
- [x] Reject sets that can't be ordered fairly:
      - duplicate years — the `events` list for 15 March repeats three of them
      - years too close together, or two events from the same war
        (13 October has War of 1812 events from both 1812 and 1814)
      - done as: years at least 10 apart; "same war" = both events link the same article
- [x] Clean text that gives the answer away:
      - drop events whose text contains a year ("War of 1812: …")
      - strip "(pictured)" — it refers to the Main Page image, not yours
- [x] Handle BCE — the feed uses negative years (`-474`)
- [x] Output a puzzle as JSON: events with years, article links, attribution
- [x] Descriptive User-Agent, retries, idempotent — same rules as the proverb app

*Teaches: nothing pipeline-wise. This is the content source everything else serves.*

### Step 2 — Game service (local)
- [ ] Python 3.13 again so tooling and CI carry over; framework — see Open decisions
- [ ] Postgres locally via `docker compose` — not SQLite locally and Postgres in prod
- [ ] Alembic from the first table: `puzzles`, `plays`
- [ ] API:
      - `GET /api/puzzle/today` — events in shuffled order, **no years**
      - `POST /api/puzzle/{date}/guess` — per-position right/wrong, Wordle-style
      - years and article links only after a solve or when attempts run out
- [ ] Attempt limit enforced on the server — 5 events is 120 orderings; with
      per-position feedback and unlimited tries it's trivially brute-forced
- [ ] Anonymous player ID in a cookie — no accounts yet
- [ ] Server-rendered page (Jinja) + a little JS for drag-to-reorder. No frontend
      build step, so the pipeline stays about the service
- [ ] Shareable emoji result grid that doesn't reveal the order

*Teaches: why this needs a server at all. Anti-cheat is best-effort — a player can clear
the cookie — the bar is "no answers in page source", not a fortress.*

### Step 3 — CI gate from day one
You've done this before. Set it up before there's much to protect.
- [ ] Tests, lint, type-check on PRs; branch protection
- [ ] Postgres as a `services:` container in the workflow — tests hit a real database
- [ ] Run migrations from empty in CI; `alembic check` fails if models and migrations drift
- [ ] Leak test: render today's page and API response, assert none of the answer years appear

*Teaches: service containers in CI, and testing an invariant rather than a function.*

### Step 4 — Containers
- [ ] One image, three commands: `serve`, `generate`, `migrate` — migrations always
      ship with the code that expects them
- [ ] Multi-stage Dockerfile, slim base, non-root user
- [ ] `.dockerignore` — keep `.env` out of the image
- [ ] Tag by commit SHA, deploy by digest; never deploy `latest`
- [ ] Push to GHCR (or Artifact Registry — see Open decisions)
- [ ] `/healthz` (process is up) and `/readyz` (database reachable)
- [ ] Expect the classic failure: the server binds `127.0.0.1` inside the container and
      nothing reaches it. Bind `0.0.0.0` and read `PORT` from the environment.

*Teaches: registries, image tags as deploy units.*

### Step 5 — Hosting + real CD
- [ ] Pick a host (see Open decisions)
- [ ] Hosted Postgres — Neon or Supabase free tier
- [ ] Deploy on merge to `main`
- [ ] Authenticate Actions to the host with OIDC (Workload Identity Federation on GCP)
      instead of a stored key — no long-lived credential to leak or rotate
- [ ] Post-deploy smoke test: a scripted player hits `/readyz`, fetches today's puzzle,
      submits a guess, and checks the response contains no years
- [ ] Mark smoke-test plays so they don't count in player stats
- [ ] Automatic rollback when the smoke test fails
- [ ] Break a deploy on purpose and watch it roll back

*Teaches: deploy pipelines, health checks, rollbacks, keyless auth from CI.*

### Step 6 — Database migrations in the pipeline
- [ ] Migrations run as their own pipeline step before the new revision gets traffic
      — not on app startup, where several instances would race
- [ ] Features that force schema changes, each shipped as a migration:
      - streaks
      - "you beat 68% of today's players"
      - guess distribution chart
- [ ] Expand/contract: rename one column the safe way across several deploys
      (add new → write both → backfill → read new → drop old)
- [ ] The hard part: rollback restores code, not schema. Old code must keep working
      against the new schema. Decide whether you write downgrades or only roll forward.
- [ ] Restore a database backup once, before you need to

*Teaches: database migrations in CI/CD — the thing the proverb app had no reason to teach.*

### Step 7 — Daily content pipeline
- [ ] `schedule:` workflow generates **tomorrow's** puzzle with status `pending`
- [ ] It runs the deployed image (`generate`), not a fresh checkout — the same code that's live
- [ ] Record used events — the feed returns the same events for 13 October every year
- [ ] Reserve bank of approved puzzles; serve one when the day's puzzle isn't approved
- [ ] Alert when generation fails or the reserve runs low — a failure notification that
      actually reaches you. A missing puzzle is now a visible outage.
- [ ] Leave slack in the schedule — you've already seen scheduled runs start late

*Teaches: a content pipeline separate from the code pipeline; alerting that matters.*

### Step 8 — Approval gate
- [ ] GitHub Environment `puzzle-approval` with you as required reviewer; the job behind
      it flips tomorrow's puzzle from `pending` to `approved`
- [ ] Solo setup: leave "prevent self-review" off, or you can never approve
- [ ] Approval deadline: 00:00 UTC, when the puzzle goes live
- [ ] **Never print the answer in Actions logs or job summaries** — on a public repo anyone
      can read them. The job links to a token-protected preview page instead.
- [ ] Rejected or timed out → serve a reserve puzzle
- [ ] Rationale: the `selected` feed for 13 October alone includes a stampede, a plane
      crash and an assassination. "Order these five disasters" needs a human look.

*Teaches: manual gates in CD — a real need here, not a contrived one.*

### Step 9 — Staging vs production
- [ ] Second service + second database (a Neon branch works) for staging
- [ ] Merge → deploy to staging → smoke test → promote the **same image digest** to
      production. Build once, deploy many; never rebuild for prod.
- [ ] Environment-scoped secrets: same `DATABASE_URL` name, different value per environment
- [ ] Migrations hit staging first — a rehearsal for production

*Teaches: promotion between environments, environment-scoped secrets.*

### Step 10 — Accounts
Anonymous play stays the default — a login wall in front of a daily puzzle loses most
players. An account is how streaks and stats survive a new device.
- [ ] `users` table; `plays` gets a nullable `user_id` next to the anonymous player ID
- [ ] On first login, attach the cookie's plays and streak to the account
- [ ] Registration + login with email and password:
      - the framework's password hashing, never your own
      - email verification and password reset, which means sending email — a
        transactional mail provider, another secret, another free tier
- [ ] Login with Google (OpenID Connect):
      - OAuth client in Google Cloud Console, scopes `openid email profile` only — basic
        scopes skip Google's app verification review (check current rules)
      - publish the consent screen; in Testing mode only listed test users can sign in
      - one redirect URI per environment: local, staging, production
      - client secret is environment-scoped, like `DATABASE_URL` (Step 9)
      - if an email + password account already has that verified email, link the two
        instead of creating a duplicate
- [ ] Simplest start: Google-only. No passwords to store, no emails to send. Add email +
      password when someone asks for it.
- [ ] Sessions: Secure, HttpOnly, SameSite=Lax cookies; CSRF protection on every form
- [ ] Rate-limit login and registration
- [ ] Email addresses are personal data: a short privacy note, and a "delete my account"
      button that actually deletes
- [ ] Run the leak test (Step 3) logged in too — an account changes nothing about when
      answers are revealed

*Teaches: OAuth/OIDC, secrets whose values differ per environment, handling personal data.*

### Step 11 — Admin panel
- [ ] Roles: `player` and `admin` (later maybe `curator` — approves puzzles, can't manage
      users). Check the role on the server for every admin route and action; hiding the
      links is not access control.
- [ ] First admin via a CLI command in the image (`create-admin <email>`), not a
      hard-coded email or a signup rule
- [ ] Users: list, change role, disable
- [ ] Statistics — exclude smoke-test plays (Step 5):
      - players and plays per day, anonymous vs registered
      - solve rate and attempts used, per puzzle
      - which events get misplaced most — a difficulty signal for future picks
      - streaks and returning players
- [ ] Select/approve the 5 events for the next game:
      - the generator (Step 7) stores every usable candidate for the date, not just its five
      - the page shows candidates with their years — fine behind admin login, never on a
        public page
      - swap events in and out, edit the text (edits stay CC BY-SA)
      - re-run Step 1's fairness checks on the final five: no duplicate or too-close years
      - approval flips `pending` → `approved`, same 00:00 UTC deadline and reserve
        fallback as Step 8 — where you click approve is an Open decision
      - record who approved which puzzle, and when
- [ ] Decide what happens to Step 8's GitHub gate (see Open decisions)
- [ ] Tests: anonymous and player requests to admin routes get 403 (or a login redirect);
      the post-deploy smoke test checks it too

*Teaches: authorization as distinct from authentication; where a manual gate belongs —
pipeline or product.*

---

## Ideas / Backlog

Things to try once the base pipeline works. Not ordered.

### Deploys
- [ ] Canary: send 10% of traffic to the new revision, watch errors, then shift the rest
      (Cloud Run traffic splitting does this natively)
- [ ] Blue/green on a VM: two containers behind Caddy, flip the upstream
- [ ] Same app on a second host (Oracle VM) — see what's portable
- [ ] Deploy freeze around 00:00 UTC, when the puzzle rolls over
- [ ] Renovate or Dependabot, including the base image

### Game
- [ ] Player's local date instead of UTC (see Open decisions)
- [ ] Difficulty levels — wider year gaps are easier
- [ ] Puzzles from other language editions (`de`, `fr`, … feeds)
- [ ] Event images, only where the file is freely licensed (see Constraints)

### Operations
- [ ] Uptime monitor on `/readyz`
- [ ] Structured logs, error tracking (Sentry free tier)
- [ ] Rate limiting on the guess endpoint
- [ ] Load test the rollover spike (k6) — everyone's puzzle changes at once

---

## Open decisions

- **Framework.** Accounts, roles and an admin panel (Steps 10–11) change the weighing:
  - *FastAPI or Flask:* lightest, but login, sessions, roles and every admin page are
    yours to build (Authlib for Google; SQLAdmin gives basic CRUD screens).
  - *Django:* the closest Python match to Laravel + Filament — users, groups, permissions,
    sessions, CSRF and a CRUD admin site built in; `django-allauth` adds Google login.
    Its own migrations replace Alembic everywhere above (`makemigrations --check` does
    what `alembic check` does). The admin site is plainer than Filament: the stats
    dashboard and the puzzle picker would be custom staff-only pages.
  - *Laravel + Filament:* the best admin panel of the three (dashboard widgets, charts,
    policies), Socialite for Google, and you already know it. Cost: the Python tooling
    and CI from the proverb app don't carry over — Composer, Pest/PHPUnit, PHPStan, and a
    PHP-FPM + web server image. The pipeline lessons themselves transfer unchanged.
  - Suggested: Django. Same language and CI as the proverb app, and most of what you'd
    reach for Filament for comes built in.
- **Host.**
  - *Google Cloud Run + Neon:* containers in, revisions out — rollback and canary are
    built in, and you already have a GCP billing account from the proverb app. Scales
    to zero, so the first visitor after a quiet spell waits for a cold start. Expects
    images in Artifact Registry; using GHCR needs a remote-repository proxy — check
    current docs.
  - *Oracle Cloud Always Free VM:* Docker + Caddy, deploy over SSH. You build health
    checks, rollback and blue/green yourself, and patch the OS. More to learn, more
    to maintain.
  - Suggested: Cloud Run first, Oracle later as the second-host comparison.
  - Free tiers shift — verify before committing.
- **What "today" means.** UTC is simplest: one live puzzle, approval deadline 00:00 UTC.
  The player's local date is friendlier, but up to three puzzles are live at once
  (UTC−12 to UTC+14), the server must refuse dates further out than that, and tomorrow's
  puzzle must be approved by 10:00 UTC. Start with UTC.
- **Puzzle shape.** 5 events, 3 attempts? Per-position feedback, or only "N correct"?
- **Event pool.** Only today's date (fits "On this day") or any date (more variety,
  fewer yearly repeats)?
- **Puzzle approval once the admin panel exists.** Decide at Step 11.
  - *A — approve in the app:* the admin page's approve button flips the puzzle to
    `approved`; retire Step 8's GitHub gate for puzzles. Reuse a required-reviewer
    Environment to promote staging → production (Step 9) instead — a deploy, which is
    what Environment gates are built for. One place to review and approve.
  - *B — curate in the app, approve in GitHub:* the admin page is where you swap and edit
    events; Step 8's gate stays the approval, and its job links to the admin page instead
    of the token-protected preview. Keeps the content gate in the pipeline, with a run
    history in Actions. Costs two places to click: edit in one, approve in the other.

## Constraints

- **Licensing:** Wikipedia text is **CC BY-SA 4.0**. Credit Wikipedia and the license
  during play; link each event's articles after the reveal — article pages show the
  dates, so linking them earlier gives the answer away. Edited event text is a
  derivative and stays CC BY-SA.
- **Images:** the feed includes page thumbnails, but not every image on English
  Wikipedia is freely licensed. Check each file's license before showing it, or skip images.
- **User-Agent:** same Wikimedia policy as the proverb app — a descriptive UA with
  contact info.
- **Answers stay on the server** until the player solves or runs out of attempts.
  Every step has to keep that true; the Step 3 leak test enforces it.
