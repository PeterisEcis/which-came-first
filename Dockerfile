# syntax=docker/dockerfile:1

# The game service. One image runs the web server, the migrations and the
# puzzle generator:
#
#     docker run IMAGE                  # serve, on 0.0.0.0:$PORT (default 8000)
#     docker run IMAGE migrate
#     docker run IMAGE generate --date 2026-10-20
#
# See config/entrypoint.py. Configuration comes from the environment, as listed
# at the top of config/settings.py; WCF_CONTACT too, for `generate`.

# --- Build: dependencies and static files -------------------------------------
# Debian named, not just "slim": a new Debian release changes the system
# libraries under Python, and that should be a commit, not a surprise rebuild.
FROM python:3.13-slim-trixie AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app

# The dependencies alone first, so a change to the code reuses this layer. Only
# the list from pyproject.toml, not the project itself: the code runs from
# /app, as it does from a checkout.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import tomllib; print(*tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies'], sep='\n')" \
        > /tmp/requirements.txt \
 && pip install -r /tmp/requirements.txt

COPY . .

# Copies the CSS and JS into staticfiles/ under hashed names, compressed, with
# the manifest that maps one to the other. Settings refuse to load without a
# secret key; this one exists only for this command.
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --no-input

# --- Runtime --------------------------------------------------------------------
FROM python:3.13-slim-trixie

ENV PATH=/opt/venv/bin:$PATH \
    # Logs reach the host as they happen, not when a buffer fills.
    PYTHONUNBUFFERED=1 \
    # The code belongs to root (below), so there is nowhere to write these.
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --system --no-create-home --shell /usr/sbin/nologin app

COPY --from=build /opt/venv /opt/venv
COPY --from=build /app /app
WORKDIR /app

# Not root. The files above stay root's, so the server can read its own code
# but not change it.
USER app

EXPOSE 8000
ENTRYPOINT ["python", "-m", "config.entrypoint"]
CMD ["serve"]
