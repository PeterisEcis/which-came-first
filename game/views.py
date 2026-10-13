"""HTTP endpoints. Thin on purpose: parse, call GameService, send the presented state.

    GET  /                               the puzzle page
    GET  /api/puzzle/today               today's state for this player
    POST /api/puzzle/YYYY-MM-DD/guess    {"order": [event ids]} -> the new state

Responses depend on the player cookie, so none of them may be cached.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from game.players import PlayerRequest
from game.presenters import PuzzleStatePresenter
from game.rules import InvalidGuess
from game.services import GameService, PlayFinished, PuzzleNotFound, utc_today


@method_decorator([never_cache, ensure_csrf_cookie], name="dispatch")
class PuzzlePageView(View):
    """The page. It embeds the same state the API sends; puzzle.js renders it."""

    def get(self, request: PlayerRequest) -> HttpResponse:
        service = GameService()
        try:
            puzzle = service.todays_puzzle()
        except PuzzleNotFound:
            return render(request, "game/no_puzzle.html", {"day": utc_today()}, status=404)

        state = PuzzleStatePresenter().present(puzzle, service.play_for(puzzle, request.player_id))
        return render(request, "game/puzzle.html", {"day": puzzle.date, "state": state})


@method_decorator(never_cache, name="dispatch")
class TodayPuzzleApi(View):
    def get(self, request: PlayerRequest) -> JsonResponse:
        service = GameService()
        try:
            puzzle = service.todays_puzzle()
        except PuzzleNotFound as exc:
            return error(404, str(exc))

        state = PuzzleStatePresenter().present(puzzle, service.play_for(puzzle, request.player_id))
        return JsonResponse(state)


@method_decorator(never_cache, name="dispatch")
class GuessApi(View):
    def post(self, request: PlayerRequest, day: date) -> JsonResponse:
        service = GameService()
        try:
            order = self.parse_order(request.body)
            puzzle = service.puzzle_for(day)
            play = service.submit_guess(puzzle, request.player_id, order)
        except InvalidGuess as exc:
            return error(400, str(exc))
        except PuzzleNotFound as exc:
            return error(404, str(exc))
        except PlayFinished as exc:
            return error(409, str(exc))

        return JsonResponse(PuzzleStatePresenter().present(puzzle, play))

    @staticmethod
    def parse_order(body: bytes) -> Sequence[str]:
        """The `order` list from a `{"order": [event ids]}` body."""
        try:
            payload = json.loads(body)
        except ValueError:
            raise InvalidGuess('expected a JSON body: {"order": [event ids]}') from None

        order = payload.get("order") if isinstance(payload, dict) else None
        if not isinstance(order, list) or not all(isinstance(key, str) for key in order):
            raise InvalidGuess('expected a JSON body: {"order": [event ids]}')
        return order


def error(status: int, message: str) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)
