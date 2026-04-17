from __future__ import annotations

from copy import deepcopy
from typing import Any

from .base import BaseGame

LEVELS = {
    1: {
        "difficulty": "easy",
        "puzzle": [
            [0, 0, 9, 4, 3, 7, 1, 5, 0],
            [4, 7, 1, 5, 2, 6, 0, 3, 8],
            [0, 3, 6, 0, 0, 9, 2, 7, 4],
            [9, 4, 0, 2, 6, 5, 8, 1, 3],
            [6, 0, 8, 9, 1, 3, 7, 4, 5],
            [0, 1, 5, 0, 0, 0, 6, 2, 0],
            [8, 6, 4, 7, 5, 2, 0, 9, 0],
            [0, 5, 2, 3, 9, 8, 0, 6, 7],
            [7, 0, 3, 0, 4, 1, 5, 8, 2],
        ],
        "solution": [
            [2, 8, 9, 4, 3, 7, 1, 5, 6],
            [4, 7, 1, 5, 2, 6, 9, 3, 8],
            [5, 3, 6, 1, 8, 9, 2, 7, 4],
            [9, 4, 7, 2, 6, 5, 8, 1, 3],
            [6, 2, 8, 9, 1, 3, 7, 4, 5],
            [3, 1, 5, 8, 7, 4, 6, 2, 9],
            [8, 6, 4, 7, 5, 2, 3, 9, 1],
            [1, 5, 2, 3, 9, 8, 4, 6, 7],
            [7, 9, 3, 6, 4, 1, 5, 8, 2],
        ],
    },
    2: {
        "difficulty": "easy",
        "puzzle": [
            [6, 8, 9, 7, 0, 3, 0, 2, 1],
            [0, 3, 1, 0, 8, 6, 7, 9, 0],
            [7, 5, 0, 9, 2, 0, 3, 6, 0],
            [9, 7, 3, 0, 6, 4, 8, 5, 2],
            [4, 0, 6, 8, 7, 0, 9, 1, 3],
            [5, 1, 8, 0, 9, 2, 6, 0, 0],
            [1, 4, 5, 6, 3, 7, 2, 8, 9],
            [8, 0, 0, 0, 0, 9, 1, 3, 7],
            [3, 9, 7, 2, 0, 8, 5, 4, 6],
        ],
        "solution": [
            [6, 8, 9, 7, 5, 3, 4, 2, 1],
            [2, 3, 1, 4, 8, 6, 7, 9, 5],
            [7, 5, 4, 9, 2, 1, 3, 6, 8],
            [9, 7, 3, 1, 6, 4, 8, 5, 2],
            [4, 2, 6, 8, 7, 5, 9, 1, 3],
            [5, 1, 8, 3, 9, 2, 6, 7, 4],
            [1, 4, 5, 6, 3, 7, 2, 8, 9],
            [8, 6, 2, 5, 4, 9, 1, 3, 7],
            [3, 9, 7, 2, 1, 8, 5, 4, 6],
        ],
    },
    3: {
        "difficulty": "easy",
        "puzzle": [
            [0, 7, 0, 1, 6, 4, 5, 8, 9],
            [0, 0, 8, 7, 0, 9, 2, 4, 6],
            [6, 9, 4, 8, 2, 5, 0, 0, 0],
            [0, 4, 0, 0, 9, 6, 3, 0, 1],
            [5, 3, 1, 4, 0, 2, 9, 6, 7],
            [9, 2, 6, 0, 0, 7, 4, 5, 8],
            [4, 1, 0, 6, 7, 3, 8, 0, 5],
            [7, 0, 5, 9, 0, 0, 6, 0, 2],
            [3, 6, 9, 0, 5, 8, 7, 1, 4],
        ],
        "solution": [
            [2, 7, 3, 1, 6, 4, 5, 8, 9],
            [1, 5, 8, 7, 3, 9, 2, 4, 6],
            [6, 9, 4, 8, 2, 5, 1, 7, 3],
            [8, 4, 7, 5, 9, 6, 3, 2, 1],
            [5, 3, 1, 4, 8, 2, 9, 6, 7],
            [9, 2, 6, 3, 1, 7, 4, 5, 8],
            [4, 1, 2, 6, 7, 3, 8, 9, 5],
            [7, 8, 5, 9, 4, 1, 6, 3, 2],
            [3, 6, 9, 2, 5, 8, 7, 1, 4],
        ],
    },
    4: {
        "difficulty": "easy",
        "puzzle": [
            [0, 4, 5, 7, 1, 2, 0, 8, 0],
            [2, 0, 7, 0, 6, 3, 1, 4, 0],
            [3, 1, 0, 5, 4, 9, 2, 6, 0],
            [8, 6, 0, 2, 3, 5, 0, 0, 9],
            [7, 2, 0, 9, 8, 4, 0, 3, 6],
            [0, 5, 0, 1, 0, 6, 0, 2, 4],
            [0, 3, 9, 4, 2, 1, 6, 0, 8],
            [4, 7, 2, 0, 5, 8, 3, 0, 1],
            [0, 8, 6, 3, 0, 7, 4, 5, 0],
        ],
        "solution": [
            [6, 4, 5, 7, 1, 2, 9, 8, 3],
            [2, 9, 7, 8, 6, 3, 1, 4, 5],
            [3, 1, 8, 5, 4, 9, 2, 6, 7],
            [8, 6, 4, 2, 3, 5, 7, 1, 9],
            [7, 2, 1, 9, 8, 4, 5, 3, 6],
            [9, 5, 3, 1, 7, 6, 8, 2, 4],
            [5, 3, 9, 4, 2, 1, 6, 7, 8],
            [4, 7, 2, 6, 5, 8, 3, 9, 1],
            [1, 8, 6, 3, 9, 7, 4, 5, 2],
        ],
    },
    5: {
        "difficulty": "medium",
        "puzzle": [
            [2, 0, 0, 0, 0, 0, 3, 0, 8],
            [5, 0, 6, 2, 0, 3, 0, 9, 1],
            [0, 3, 9, 0, 0, 0, 0, 5, 0],
            [0, 0, 0, 5, 0, 4, 0, 2, 6],
            [3, 6, 2, 8, 0, 9, 5, 7, 0],
            [4, 9, 5, 6, 7, 2, 1, 0, 0],
            [1, 0, 0, 0, 6, 7, 2, 4, 0],
            [9, 7, 0, 4, 2, 8, 6, 1, 5],
            [6, 0, 4, 9, 5, 1, 0, 3, 7],
        ],
        "solution": [
            [2, 4, 1, 7, 9, 5, 3, 6, 8],
            [5, 8, 6, 2, 4, 3, 7, 9, 1],
            [7, 3, 9, 1, 8, 6, 4, 5, 2],
            [8, 1, 7, 5, 3, 4, 9, 2, 6],
            [3, 6, 2, 8, 1, 9, 5, 7, 4],
            [4, 9, 5, 6, 7, 2, 1, 8, 3],
            [1, 5, 8, 3, 6, 7, 2, 4, 9],
            [9, 7, 3, 4, 2, 8, 6, 1, 5],
            [6, 2, 4, 9, 5, 1, 8, 3, 7],
        ],
    },
    6: {
        "difficulty": "medium",
        "puzzle": [
            [7, 0, 0, 0, 1, 0, 0, 5, 0],
            [1, 0, 2, 5, 4, 8, 0, 0, 0],
            [0, 4, 0, 0, 0, 0, 2, 0, 1],
            [0, 0, 3, 7, 0, 1, 5, 0, 4],
            [4, 0, 7, 0, 5, 0, 0, 1, 2],
            [2, 5, 0, 4, 3, 9, 8, 7, 6],
            [3, 2, 5, 1, 9, 4, 0, 0, 0],
            [0, 1, 0, 3, 6, 7, 9, 2, 5],
            [9, 7, 6, 0, 0, 0, 1, 4, 3],
        ],
        "solution": [
            [7, 3, 9, 6, 1, 2, 4, 5, 8],
            [1, 6, 2, 5, 4, 8, 7, 3, 9],
            [5, 4, 8, 9, 7, 3, 2, 6, 1],
            [6, 8, 3, 7, 2, 1, 5, 9, 4],
            [4, 9, 7, 8, 5, 6, 3, 1, 2],
            [2, 5, 1, 4, 3, 9, 8, 7, 6],
            [3, 2, 5, 1, 9, 4, 6, 8, 7],
            [8, 1, 4, 3, 6, 7, 9, 2, 5],
            [9, 7, 6, 2, 8, 5, 1, 4, 3],
        ],
    },
    7: {
        "difficulty": "medium",
        "puzzle": [
            [0, 0, 3, 0, 5, 0, 4, 9, 1],
            [9, 1, 0, 4, 7, 0, 0, 0, 6],
            [4, 6, 0, 0, 9, 0, 8, 0, 0],
            [6, 0, 1, 9, 0, 0, 0, 4, 0],
            [5, 0, 4, 7, 3, 0, 6, 0, 0],
            [8, 0, 0, 0, 6, 4, 0, 7, 0],
            [2, 5, 7, 3, 4, 6, 9, 1, 0],
            [3, 0, 0, 5, 1, 7, 2, 0, 4],
            [1, 4, 6, 0, 0, 9, 0, 5, 0],
        ],
        "solution": [
            [7, 8, 3, 6, 5, 2, 4, 9, 1],
            [9, 1, 2, 4, 7, 8, 5, 3, 6],
            [4, 6, 5, 1, 9, 3, 8, 2, 7],
            [6, 7, 1, 9, 8, 5, 3, 4, 2],
            [5, 2, 4, 7, 3, 1, 6, 8, 9],
            [8, 3, 9, 2, 6, 4, 1, 7, 5],
            [2, 5, 7, 3, 4, 6, 9, 1, 8],
            [3, 9, 8, 5, 1, 7, 2, 6, 4],
            [1, 4, 6, 8, 2, 9, 7, 5, 3],
        ],
    },
    8: {
        "difficulty": "hard",
        "puzzle": [
            [0, 0, 0, 0, 5, 8, 6, 0, 0],
            [8, 6, 9, 2, 0, 1, 0, 0, 0],
            [0, 2, 5, 0, 4, 6, 0, 1, 0],
            [0, 0, 0, 0, 2, 3, 0, 6, 0],
            [5, 0, 0, 6, 8, 7, 2, 0, 1],
            [0, 0, 0, 4, 0, 0, 0, 0, 3],
            [0, 5, 2, 0, 0, 0, 0, 0, 9],
            [0, 1, 8, 3, 0, 0, 0, 0, 4],
            [4, 3, 0, 8, 9, 0, 0, 2, 6],
        ],
        "solution": [
            [3, 4, 1, 7, 5, 8, 6, 9, 2],
            [8, 6, 9, 2, 3, 1, 4, 7, 5],
            [7, 2, 5, 9, 4, 6, 3, 1, 8],
            [1, 8, 4, 5, 2, 3, 9, 6, 7],
            [5, 9, 3, 6, 8, 7, 2, 4, 1],
            [2, 7, 6, 4, 1, 9, 5, 8, 3],
            [6, 5, 2, 1, 7, 4, 8, 3, 9],
            [9, 1, 8, 3, 6, 2, 7, 5, 4],
            [4, 3, 7, 8, 9, 5, 1, 2, 6],
        ],
    },
    9: {
        "difficulty": "hard",
        "puzzle": [
            [0, 0, 8, 3, 9, 6, 4, 0, 1],
            [0, 3, 0, 0, 2, 1, 0, 0, 0],
            [0, 1, 6, 4, 0, 8, 0, 0, 0],
            [0, 9, 0, 0, 6, 0, 1, 7, 8],
            [0, 0, 0, 9, 8, 0, 0, 0, 0],
            [0, 8, 0, 0, 1, 7, 0, 0, 0],
            [0, 0, 0, 8, 3, 5, 9, 4, 0],
            [0, 0, 5, 6, 0, 9, 8, 0, 0],
            [8, 0, 9, 0, 4, 0, 0, 3, 6],
        ],
        "solution": [
            [7, 5, 8, 3, 9, 6, 4, 2, 1],
            [9, 3, 4, 7, 2, 1, 6, 8, 5],
            [2, 1, 6, 4, 5, 8, 7, 9, 3],
            [5, 9, 3, 2, 6, 4, 1, 7, 8],
            [1, 6, 7, 9, 8, 3, 2, 5, 4],
            [4, 8, 2, 5, 1, 7, 3, 6, 9],
            [6, 2, 1, 8, 3, 5, 9, 4, 7],
            [3, 4, 5, 6, 7, 9, 8, 1, 2],
            [8, 7, 9, 1, 4, 2, 5, 3, 6],
        ],
    },
    10: {
        "difficulty": "hard",
        "puzzle": [
            [4, 6, 0, 0, 0, 0, 7, 3, 8],
            [9, 0, 8, 0, 0, 0, 0, 0, 4],
            [0, 3, 7, 0, 0, 1, 9, 6, 0],
            [6, 0, 0, 0, 1, 7, 0, 5, 2],
            [0, 4, 0, 8, 0, 0, 0, 7, 1],
            [0, 7, 0, 0, 0, 4, 0, 9, 3],
            [0, 0, 0, 0, 4, 0, 3, 0, 0],
            [0, 2, 6, 5, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 6, 5, 8, 0],
        ],
        "solution": [
            [4, 6, 1, 9, 2, 5, 7, 3, 8],
            [9, 5, 8, 7, 6, 3, 2, 1, 4],
            [2, 3, 7, 4, 8, 1, 9, 6, 5],
            [6, 8, 9, 3, 1, 7, 4, 5, 2],
            [5, 4, 3, 8, 9, 2, 6, 7, 1],
            [1, 7, 2, 6, 5, 4, 8, 9, 3],
            [7, 9, 5, 1, 4, 8, 3, 2, 6],
            [8, 2, 6, 5, 3, 9, 1, 4, 7],
            [3, 1, 4, 2, 7, 6, 5, 8, 9],
        ],
    }
}


class Sudoku(BaseGame):
    name = "sudoku"
    MAX_LIVES = 3

    def __init__(self) -> None:
        self.current_level = 1
        self.max_level = len(LEVELS)
        self.difficulty = "easy"
        self.board: list[list[int]] = []
        self.givens: list[list[int]] = []
        self.solution: list[list[int]] = []
        self.fixed_cells: list[list[bool]] = []
        self.notes: list[list[list[int]]] = []
        self.conflicts: list[list[bool]] = []
        self.candidates: list[list[list[int]]] = []
        self.score = 0
        self.filled_cells = 0
        self.total_to_fill = 0
        self.mistakes = 0
        self.game_over = False
        self.won = False
        self.withdrawn = False
        self.lives = self.MAX_LIVES
        self.last_feedback: str | None = None
        self.last_mismatch: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = []
        self.undo_available = False
        self._reset_log()
        self.reset()

    def reset(self) -> dict[str, Any]:
        current_data = LEVELS.get(self.current_level, LEVELS[1])
        if current_data.get("difficulty", "easy") != self.difficulty:
            for lvl, data in LEVELS.items():
                if data.get("difficulty", "easy") == self.difficulty:
                    self.current_level = lvl
                    break
        
        self._load_level(self.current_level)
        return self.get_state()

    def set_difficulty(self, difficulty: str) -> None:
        self.difficulty = difficulty
        start_level = {"easy": 1, "medium": 5, "hard": 8}.get(difficulty, 1)
        if start_level in LEVELS:
            self.current_level = start_level
        else:
            self.current_level = 1

    def _load_level(self, level: int) -> None:
        level_data = LEVELS.get(level, LEVELS[1])
        self.current_level = level if level in LEVELS else 1
        self.difficulty = level_data.get("difficulty", "easy")
        self.givens = deepcopy(level_data["puzzle"])
        self.solution = deepcopy(level_data["solution"])
        self.board = deepcopy(level_data["puzzle"])
        self.fixed_cells = [
            [cell != 0 for cell in row]
            for row in self.givens
        ]
        self.notes = [
            [[] for _ in range(9)]
            for _ in range(9)
        ]
        self.candidates = [
            [[] for _ in range(9)]
            for _ in range(9)
        ]
        self.conflicts = [
            [False for _ in range(9)]
            for _ in range(9)
        ]
        self.game_over = False
        self.won = False
        self.withdrawn = False
        self.lives = self.MAX_LIVES
        self.last_feedback = None
        self.last_mismatch = None
        self.history = []
        self._refresh_state_metrics()
        self._save_history()

    def _save_history(self) -> None:
        self.history.append({
            "board": deepcopy(self.board),
            "notes": deepcopy(self.notes),
            "score": self.score,
            "filled_cells": self.filled_cells,
            "mistakes": self.mistakes,
        })
        self.undo_available = len(self.history) > 1

    def _apply_undo(self) -> None:
        if len(self.history) <= 1:
            return
        self.history.pop()
        last_state = self.history[-1]
        self.board = deepcopy(last_state["board"])
        self.notes = deepcopy(last_state["notes"])
        self.score = last_state["score"]
        self.filled_cells = last_state["filled_cells"]
        self.mistakes = last_state["mistakes"]
        self.game_over = False
        self.won = False
        self.withdrawn = False
        self._refresh_state_metrics()
        self.undo_available = len(self.history) > 1

    def _refresh_state_metrics(self) -> None:
        self.candidates = [
            [[] for _ in range(9)]
            for _ in range(9)
        ]
        self.conflicts = [
            [False for _ in range(9)]
            for _ in range(9)
        ]

        for r in range(9):
            positions: dict[int, list[tuple[int, int]]] = {}
            for c in range(9):
                value = self.board[r][c]
                if value != 0:
                    positions.setdefault(value, []).append((r, c))
            for cells in positions.values():
                if len(cells) > 1:
                    for row, col in cells:
                        self.conflicts[row][col] = True

        for c in range(9):
            positions: dict[int, list[tuple[int, int]]] = {}
            for r in range(9):
                value = self.board[r][c]
                if value != 0:
                    positions.setdefault(value, []).append((r, c))
            for cells in positions.values():
                if len(cells) > 1:
                    for row, col in cells:
                        self.conflicts[row][col] = True

        for box_r in range(0, 9, 3):
            for box_c in range(0, 9, 3):
                positions: dict[int, list[tuple[int, int]]] = {}
                for r in range(box_r, box_r + 3):
                    for c in range(box_c, box_c + 3):
                        value = self.board[r][c]
                        if value != 0:
                            positions.setdefault(value, []).append((r, c))
                for cells in positions.values():
                    if len(cells) > 1:
                        for row, col in cells:
                            self.conflicts[row][col] = True

        self.total_to_fill = sum(
            1
            for r in range(9)
            for c in range(9)
            if not self.fixed_cells[r][c]
        )
        self.filled_cells = sum(
            1
            for r in range(9)
            for c in range(9)
            if not self.fixed_cells[r][c] and self.board[r][c] != 0
        )
        self.score = sum(
            1
            for r in range(9)
            for c in range(9)
            if not self.fixed_cells[r][c] and self.board[r][c] == self.solution[r][c]
        )
        self.mistakes = sum(
            1
            for r in range(9)
            for c in range(9)
            if not self.fixed_cells[r][c] and self.conflicts[r][c]
        )
        for r in range(9):
            for c in range(9):
                if self.fixed_cells[r][c] or self.board[r][c] != 0:
                    continue
                self.candidates[r][c] = self._legal_candidates(r, c)
        self.won = all(
            self.board[r][c] == self.solution[r][c]
            for r in range(9)
            for c in range(9)
        )
        if self.won:
            self.game_over = True

    def _legal_candidates(self, row: int, col: int) -> list[int]:
        if self.fixed_cells[row][col] or self.board[row][col] != 0:
            return []

        used = set()
        for c in range(9):
            value = self.board[row][c]
            if value != 0:
                used.add(value)
        for r in range(9):
            value = self.board[r][col]
            if value != 0:
                used.add(value)

        box_row = (row // 3) * 3
        box_col = (col // 3) * 3
        for r in range(box_row, box_row + 3):
            for c in range(box_col, box_col + 3):
                value = self.board[r][c]
                if value != 0:
                    used.add(value)

        return [value for value in range(1, 10) if value not in used]

    def get_state(self) -> dict[str, Any]:
        return {
            "game": self.name,
            "board": deepcopy(self.board),
            "givens": deepcopy(self.givens),
            "fixed_cells": deepcopy(self.fixed_cells),
            "notes": deepcopy(self.notes),
            "conflicts": deepcopy(self.conflicts),
            "candidates": deepcopy(self.candidates),
            "score": self.score,
            "filled_cells": self.filled_cells,
            "total_to_fill": self.total_to_fill,
            "mistakes": self.mistakes,
            "lives": self.lives,
            "max_lives": self.MAX_LIVES,
            "game_over": self.game_over,
            "won": self.won,
            "withdrawn": self.withdrawn,
            "valid_actions": self.valid_actions(),
            "undo_available": self.undo_available,
            "last_feedback": self.last_feedback,
            "last_mismatch": self.last_mismatch,
            "current_level": self.current_level,
            "max_level": self.max_level,
            "difficulty": self.difficulty,
        }

    def valid_actions(self) -> list[str]:
        if self.game_over:
            if self.won and self.current_level < self.max_level:
                return ["next_level"]
            return []

        actions = []
        if self.undo_available:
            actions.append("undo")

        for r in range(9):
            for c in range(9):
                if self.fixed_cells[r][c]:
                    continue
                actions.append(f"clear_{r}_{c}")
                current = self.board[r][c]
                if current == 0:
                    for value in range(1, 10):
                        actions.append(f"set_{r}_{c}_{value}")
                        actions.append(f"note_{r}_{c}_{value}")
                else:
                    for value in range(1, 10):
                        if value != current:
                            actions.append(f"set_{r}_{c}_{value}")
        return actions

    def apply_action(self, action: str) -> dict[str, Any]:
        action = action.strip().lower()
        action_step = self._steps + 1

        if self.game_over and action != "next_level":
            state = self.get_state()
            state["error"] = "Game is already over."
            return state

        if action == "next_level":
            self.current_level += 1
            self._load_level(self.current_level)
            state = self.get_state()
            self._record_log(action, state)
            return state

        if action == "undo":
            self._apply_undo()
            self.last_feedback = f"Step {action_step}: undo used."
            self.last_mismatch = None
            state = self.get_state()
            self._record_log(action, state)
            return state

        parts = action.split("_")
        changed = False

        if len(parts) == 3 and parts[0] == "clear":
            _, r_text, c_text = parts
            row = int(r_text)
            col = int(c_text)
            if self.fixed_cells[row][col]:
                state = self.get_state()
                state["error"] = "Fixed cells cannot be edited."
                return state
            if self.board[row][col] != 0 or self.notes[row][col]:
                self.board[row][col] = 0
                self.notes[row][col] = []
                changed = True

        elif len(parts) == 4 and parts[0] == "set":
            _, r_text, c_text, value_text = parts
            row = int(r_text)
            col = int(c_text)
            value = int(value_text)
            if self.fixed_cells[row][col]:
                state = self.get_state()
                state["error"] = "Fixed cells cannot be edited."
                return state
            if value < 1 or value > 9:
                state = self.get_state()
                state["error"] = "Value must be between 1 and 9."
                return state
            if self.board[row][col] != value or self.notes[row][col]:
                self.board[row][col] = value
                self.notes[row][col] = []
                if value != self.solution[row][col]:
                    self.lives -= 1
                    self.last_mismatch = {
                        "step": action_step,
                        "action": action,
                        "row": row,
                        "col": col,
                        "expected": self.solution[row][col],
                        "actual": value,
                        "hearts_remaining": self.lives,
                    }
                    self.last_feedback = (
                        f"Step {action_step}: action '{action}' mismatches solution, -1 heart. "
                        f"Hearts left: {self.lives}. Please use undo."
                    )
                    if self.lives <= 0:
                        self.lives = 0
                        self.game_over = True
                else:
                    self.last_feedback = None
                    self.last_mismatch = None
                changed = True

        elif len(parts) == 4 and parts[0] == "note":
            _, r_text, c_text, value_text = parts
            row = int(r_text)
            col = int(c_text)
            value = int(value_text)
            if self.fixed_cells[row][col]:
                state = self.get_state()
                state["error"] = "Fixed cells cannot be edited."
                return state
            if self.board[row][col] != 0:
                state = self.get_state()
                state["error"] = "Clear the cell before editing notes."
                return state
            if value < 1 or value > 9:
                state = self.get_state()
                state["error"] = "Value must be between 1 and 9."
                return state
            if value in self.notes[row][col]:
                self.notes[row][col].remove(value)
            else:
                self.notes[row][col].append(value)
                self.notes[row][col].sort()
            self.last_feedback = None
            self.last_mismatch = None
            changed = True
        else:
            state = self.get_state()
            state["error"] = f"Invalid action: {action}"
            return state

        if changed:
            self._refresh_state_metrics()
            self._save_history()
        state = self.get_state()
        if self.last_feedback and self.last_mismatch:
            state["error"] = self.last_feedback
        self._record_log(action, state)
        return state

    def serialize(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": {
                "current_level": self.current_level,
                "board": deepcopy(self.board),
                "notes": deepcopy(self.notes),
                "score": self.score,
                "filled_cells": self.filled_cells,
                "mistakes": self.mistakes,
                "lives": self.lives,
                "game_over": self.game_over,
                "won": self.won,
                "withdrawn": self.withdrawn,
                "difficulty": self.difficulty,
                "history": deepcopy(self.history),
            },
            "session_id": self._session_id,
            "player_name": self._player_name,
            "difficulty": self.difficulty,
            "steps": self._steps,
        }

    def restore_state(self, saved_state: dict[str, Any]) -> None:
        self.current_level = saved_state.get("current_level", 1)
        self.difficulty = saved_state.get("difficulty", "easy")
        self._load_level(self.current_level)
        self.board = deepcopy(saved_state.get("board", self.board))
        self.notes = deepcopy(saved_state.get("notes", self.notes))
        self.history = deepcopy(saved_state.get("history", self.history))
        self.game_over = saved_state.get("game_over", False)
        self.won = saved_state.get("won", False)
        self.withdrawn = saved_state.get("withdrawn", False)
        self.lives = saved_state.get("lives", self.MAX_LIVES)
        self._refresh_state_metrics()
        if self.withdrawn:
            self.game_over = True
        elif self.won:
            self.game_over = True
        self.undo_available = len(self.history) > 1

    def get_rules(self) -> str:
        return (
            "Sudoku Rules:\n"
            "1. Fill every empty cell with a number from 1 to 9.\n"
            "2. Each row must contain every number 1-9 exactly once.\n"
            "3. Each column must contain every number 1-9 exactly once.\n"
            "4. Each 3x3 box must contain every number 1-9 exactly once.\n"
            "5. Given cells cannot be changed.\n"
            "6. IMPORTANT PENALTY RULE (Hearts): You start with 3 hearts. If you make a 'set' action that conflicts with the hidden solution, you lose 1 heart. If you reach 0 hearts, you lose the game immediately.\n"
            "7. IMPORTANT RECOVERY RULE (Undo): If you make a mistake and get an error feedback, you MUST use the 'undo' action immediately to recover.\n"
            "Actions:\n"
            "- 'set_R_C_V': Put value V into row R, column C.\n"
            "- 'clear_R_C': Clear the selected editable cell.\n"
            "- 'note_R_C_V': Toggle pencil mark V in row R, column C.\n"
            "- 'undo': Revert the previous move.\n"
            "- 'next_level': Go to the next level after winning the current one."
        )
