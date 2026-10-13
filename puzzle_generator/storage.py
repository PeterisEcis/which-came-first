"""Puzzle files on disk, one per date: `{root}/YYYY-MM-DD.json`.

Step 2 replaces this with a database table. Until then it gives the generator
the idempotency a daily job needs: a date that has a file is done, and a rerun
leaves it alone unless forced.

Files are written to a temporary sibling and renamed into place, so an
interrupted run never leaves a half-written puzzle that looks finished.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

from puzzle_generator.models import Puzzle
from puzzle_generator.serialization import PuzzleSerializer


class PuzzleStore:
    def __init__(self, root: Path, serializer: PuzzleSerializer | None = None) -> None:
        self.root = root
        self.serializer = serializer or PuzzleSerializer()

    def path_for(self, day: date) -> Path:
        return self.root / f"{day.isoformat()}.json"

    def exists(self, day: date) -> bool:
        return self.path_for(day).is_file()

    def save(self, puzzle: Puzzle) -> Path:
        """Write `puzzle`, replacing any earlier file for its date."""
        path = self.path_for(puzzle.puzzle_date)
        path.parent.mkdir(parents=True, exist_ok=True)

        # In the destination directory, so the rename stays on one volume and is
        # atomic. mkstemp rather than NamedTemporaryFile: the file must outlive
        # the handle.
        descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".part"
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(self.serializer.to_json(puzzle))
            os.replace(temp_path, path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
        return path
