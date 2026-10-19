"""The container's entry point: `docker run IMAGE [COMMAND [ARGS...]]`.

    serve      the web server, on 0.0.0.0:$PORT (default 8000). The default.
    migrate    apply the database migrations, then exit
    generate   store a day's puzzle, then exit: `generate --date 2026-10-20`.
               The same command and flags as `manage.py generate_puzzle`.

Anything else goes to manage.py, so `docker run -it IMAGE createsuperuser` works.

One image runs all three, so migrations and the generator always run the code of
the server they ship with (todo.md, Step 4).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence

DEFAULT_PORT = "8000"


def command_line(argv: Sequence[str], environ: Mapping[str, str]) -> list[str]:
    """The program and arguments that `docker run IMAGE *argv` runs."""
    command, *args = argv or ["serve"]
    manage = [sys.executable, "manage.py"]

    if command == "serve":
        port = environ.get("PORT", DEFAULT_PORT)
        return [
            "gunicorn",
            "config.wsgi",
            # 0.0.0.0, every interface. 127.0.0.1 inside a container is the
            # container's own loopback, which nothing outside it can reach.
            f"--bind=0.0.0.0:{port}",
            "--access-logfile=-",
            # Worker heartbeats go to memory: on a container's disk-backed /tmp
            # a slow write can get a healthy worker killed.
            "--worker-tmp-dir=/dev/shm",
            # The socket is for managing a long-running server by hand. A
            # container is replaced, not managed, and its user has no home
            # directory to put the socket in.
            "--no-control-socket",
            *args,
        ]
    if command == "migrate":
        # Nobody is at a keyboard to answer a prompt.
        return [*manage, "migrate", "--no-input", *args]
    if command == "generate":
        return [*manage, "generate_puzzle", *args]
    return [*manage, command, *args]


def main() -> None:
    program = command_line(sys.argv[1:], os.environ)
    # Replace this process rather than start a child: the server becomes the
    # container's main process and gets the stop signal itself, and the
    # container exits with the command's own exit code.
    os.execvp(program[0], program)


if __name__ == "__main__":
    main()
