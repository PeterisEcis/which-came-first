"""Puzzle generator for the daily "which came first?" game.

Turns one date's entries in Wikipedia's "On this day" feed into a puzzle: five
events that can be put in order fairly, with their years and article links.

Plain Python, no Django. The game service (Step 2) imports it, and a management
command there takes over from `cli.py`; nothing in here has to change for that.

Layout of the package:

    config.py         settings, from CLI flags, the environment and .env
    models.py         plain dataclasses passed between stages
    http_client.py    retry-safe HTTP with a policy-compliant User-Agent
    feed.py           fetches the feed and parses it into events
    cleaning.py       drops events that give a year away, tidies the rest
    fairness.py       rules for which events can share a puzzle
    selection.py      picks the day's events, the same way every time
    generator.py      wires the stages above into one call
    serialization.py  a puzzle as JSON
    storage.py        puzzle files on disk, and the idempotency check
    cli.py            argument parsing, logging, exit codes
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
