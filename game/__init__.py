"""The game service: today's puzzle, players' guesses, and the page they play on.

Layout of the app:

    rules.py         the rules of a round, no Django: feedback, status, share text
    models.py        puzzles, their events, and plays
    importer.py      stores a generated puzzle: start order and public event ids
    services.py      game actions: find the day's puzzle, record a guess
    presenters.py    what a player may see -- the one place answers are let out
    players.py       the anonymous player cookie
    views.py         the page and the JSON API
    management/      `manage.py generate_puzzle`
    templates/, static/   the page, its styles, and the drag-to-reorder script
"""
