from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

_agent_dir = Path(__file__).resolve().parent
_project_root = _agent_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.games.game_crossnumber import LEVELS as CROSSNUMBER_LEVELS
from backend.games.game_sudoku import LEVELS as SUDOKU_LEVELS


@dataclass
class Judgement:
    result: str
    reason: str
    progress: float
    details: dict[str, Any]


def fetch_state(backend_url: str, game: str, session_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{backend_url.rstrip('/')}/api/game/{game}/state",
        params={"session_id": session_id},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def notify_backend(backend_url: str, game: str, session_id: str, judgement: Judgement) -> None:
    requests.post(
        f"{backend_url.rstrip('/')}/api/game/{game}/agent_error",
        params={"session_id": session_id},
        json={"error": f"Auto-judged lose: {judgement.reason}", "judgement": asdict(judgement)},
        timeout=10,
    ).raise_for_status()


def mark_lose(backend_url: str, game: str, session_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{backend_url.rstrip('/')}/api/game/{game}/action",
        params={"session_id": session_id, "move": "withdraw"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def sudoku_signature(state: dict[str, Any]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(row) for row in state.get("board", []))


def crossnumber_signature(state: dict[str, Any]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(row) for row in state.get("cell_states", []))


def sudoku_progress(state: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    level = state.get("current_level", 1)
    level_data = SUDOKU_LEVELS.get(level, SUDOKU_LEVELS[1])
    board = state.get("board", [])
    fixed_cells = state.get("fixed_cells") or [
        [cell != 0 for cell in row]
        for row in level_data["puzzle"]
    ]
    solution = level_data["solution"]
    total_fillable = sum(
        1
        for r in range(9)
        for c in range(9)
        if not fixed_cells[r][c]
    )
    correct_cells = sum(
        1
        for r in range(9)
        for c in range(9)
        if not fixed_cells[r][c] and board[r][c] == solution[r][c]
    )
    filled_cells = sum(
        1
        for r in range(9)
        for c in range(9)
        if not fixed_cells[r][c] and board[r][c] != 0
    )
    is_full = all(cell != 0 for row in board for cell in row)
    progress = correct_cells / total_fillable if total_fillable else 1.0
    return progress, {
        "correct_cells": correct_cells,
        "filled_cells": filled_cells,
        "total_fillable": total_fillable,
        "full_board": is_full,
    }


def crossnumber_progress(state: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    grid = state.get("grid", [])
    cell_states = state.get("cell_states", [])
    row_targets = state.get("row_targets", [])
    col_targets = state.get("col_targets", [])
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    total_cells = rows * cols
    decided_cells = sum(
        1
        for r in range(rows)
        for c in range(cols)
        if cell_states[r][c] != 0
    )
    matched_rows = 0
    for r in range(rows):
        row_sum = sum(grid[r][c] for c in range(cols) if cell_states[r][c] == 1)
        if r < len(row_targets) and row_sum == row_targets[r]:
            matched_rows += 1
    matched_cols = 0
    for c in range(cols):
        col_sum = sum(grid[r][c] for r in range(rows) if cell_states[r][c] == 1)
        if c < len(col_targets) and col_sum == col_targets[c]:
            matched_cols += 1
    all_decided = total_cells > 0 and decided_cells == total_cells
    decided_ratio = decided_cells / total_cells if total_cells else 1.0
    constraint_total = len(row_targets) + len(col_targets)
    matched_ratio = (matched_rows + matched_cols) / constraint_total if constraint_total else 1.0
    progress = 0.6 * decided_ratio + 0.4 * matched_ratio
    return progress, {
        "decided_cells": decided_cells,
        "total_cells": total_cells,
        "matched_rows": matched_rows,
        "matched_cols": matched_cols,
        "row_target_count": len(row_targets),
        "col_target_count": len(col_targets),
        "all_decided": all_decided,
    }


def evaluate_sudoku_state(state: dict[str, Any]) -> Judgement | None:
    progress, details = sudoku_progress(state)
    if state.get("won"):
        return Judgement("win", "solved", 1.0, details)
    if state.get("withdrawn"):
        return Judgement("lose", "withdrawn", progress, details)
    if details["full_board"] and not state.get("won", False):
        return Judgement("lose", "full_board_incorrect", progress, details)
    if state.get("game_over") and not state.get("won", False):
        return Judgement("lose", "game_over_without_win", progress, details)
    return None


def evaluate_crossnumber_state(state: dict[str, Any]) -> Judgement | None:
    progress, details = crossnumber_progress(state)
    if state.get("won"):
        return Judgement("win", "solved", 1.0, details)
    if state.get("withdrawn"):
        return Judgement("lose", "withdrawn", progress, details)
    if details["all_decided"] and not state.get("won", False):
        return Judgement("lose", "all_cells_decided_incorrect", progress, details)
    if state.get("game_over") and not state.get("won", False):
        return Judgement("lose", "game_over_without_win", progress, details)
    return None


def evaluate_explicit_state(game: str, state: dict[str, Any]) -> Judgement | None:
    if game == "sudoku":
        return evaluate_sudoku_state(state)
    if game == "crossnumber":
        return evaluate_crossnumber_state(state)
    raise ValueError(f"Unsupported game: {game}")


def compute_progress(game: str, state: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    if game == "sudoku":
        return sudoku_progress(state)
    if game == "crossnumber":
        return crossnumber_progress(state)
    raise ValueError(f"Unsupported game: {game}")


def compute_signature(game: str, state: dict[str, Any]) -> tuple[tuple[int, ...], ...]:
    if game == "sudoku":
        return sudoku_signature(state)
    if game == "crossnumber":
        return crossnumber_signature(state)
    raise ValueError(f"Unsupported game: {game}")


class SessionJudge:
    def __init__(self, game: str, repeat_limit: int, stagnation_limit: int) -> None:
        self.game = game
        self.repeat_limit = repeat_limit
        self.stagnation_limit = stagnation_limit
        self.last_signature: tuple[tuple[int, ...], ...] | None = None
        self.best_progress = -1.0
        self.repeat_count = 0
        self.stagnation_count = 0

    def update(self, state: dict[str, Any]) -> Judgement:
        explicit = evaluate_explicit_state(self.game, state)
        if explicit is not None:
            return explicit

        progress, details = compute_progress(self.game, state)
        signature = compute_signature(self.game, state)

        if signature == self.last_signature:
            self.repeat_count += 1
        else:
            self.last_signature = signature
            self.repeat_count = 0

        if progress > self.best_progress:
            self.best_progress = progress
            self.stagnation_count = 0
        else:
            self.stagnation_count += 1

        details = {
            **details,
            "repeat_count": self.repeat_count,
            "repeat_limit": self.repeat_limit,
            "stagnation_count": self.stagnation_count,
            "stagnation_limit": self.stagnation_limit,
        }

        if self.repeat_count >= self.repeat_limit:
            return Judgement("lose", "repeat_state_loop", progress, details)
        if self.stagnation_count >= self.stagnation_limit:
            return Judgement("lose", "no_progress_stagnation", progress, details)
        return Judgement("ongoing", "ongoing", progress, details)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Judge whether a Sudoku/Crossnumber session should be treated as lose.")
    parser.add_argument("--backend-url", type=str, default="http://localhost:5001")
    parser.add_argument("--game", type=str, required=True, choices=["sudoku", "crossnumber"])
    parser.add_argument("--session-id", type=str, required=True)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--repeat-limit", type=int, default=5)
    parser.add_argument("--stagnation-limit", type=int, default=12)
    parser.add_argument("--notify-backend", action="store_true")
    parser.add_argument("--mark-lose", action="store_true")
    return parser.parse_args()


def print_judgement(judgement: Judgement) -> None:
    print(json.dumps(asdict(judgement), ensure_ascii=False, indent=2))


def main() -> int:
    args = parse_args()
    judge = SessionJudge(
        game=args.game,
        repeat_limit=args.repeat_limit,
        stagnation_limit=args.stagnation_limit,
    )

    while True:
        state = fetch_state(args.backend_url, args.game, args.session_id)
        judgement = judge.update(state)
        print_judgement(judgement)

        if judgement.result in {"win", "lose"}:
            if judgement.result == "lose":
                if args.notify_backend:
                    notify_backend(args.backend_url, args.game, args.session_id, judgement)
                if args.mark_lose and not state.get("game_over", False):
                    mark_lose(args.backend_url, args.game, args.session_id)
            return 0 if judgement.result == "win" else 2

        if not args.watch:
            return 1

        time.sleep(args.poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
