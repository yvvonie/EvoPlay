from __future__ import annotations

from copy import deepcopy
from typing import Any

from .base import BaseGame

LEVELS = {
    1: {
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
    }
}


class Sudoku(BaseGame):
    name = "sudoku"

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
        self.score = 0
        self.filled_cells = 0
        self.total_to_fill = 0
        self.mistakes = 0
        self.game_over = False
        self.won = False
        self.withdrawn = False
        self.history: list[dict[str, Any]] = []
        self.undo_available = False
        self._reset_log()
        self.reset()

    def reset(self) -> dict[str, Any]:
        self.current_level = 1
        self._load_level(self.current_level)
        return self.get_state()

    def _load_level(self, level: int) -> None:
        level_data = LEVELS.get(level, LEVELS[1])
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
        self.conflicts = [
            [False for _ in range(9)]
            for _ in range(9)
        ]
        self.game_over = False
        self.won = False
        self.withdrawn = False
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
        self.won = all(
            self.board[r][c] == self.solution[r][c]
            for r in range(9)
            for c in range(9)
        )
        if self.won:
            self.game_over = True

    def get_state(self) -> dict[str, Any]:
        return {
            "game": self.name,
            "board": deepcopy(self.board),
            "givens": deepcopy(self.givens),
            "fixed_cells": deepcopy(self.fixed_cells),
            "notes": deepcopy(self.notes),
            "conflicts": deepcopy(self.conflicts),
            "score": self.score,
            "filled_cells": self.filled_cells,
            "total_to_fill": self.total_to_fill,
            "mistakes": self.mistakes,
            "game_over": self.game_over,
            "won": self.won,
            "withdrawn": self.withdrawn,
            "valid_actions": self.valid_actions(),
            "undo_available": self.undo_available,
            "current_level": self.current_level,
            "max_level": self.max_level,
            "difficulty": self.difficulty,
        }

    def valid_actions(self) -> list[str]:
        if self.game_over:
            return []

        actions = ["withdraw"]
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

        if self.game_over:
            state = self.get_state()
            state["error"] = "Game is already over."
            return state

        if action == "undo":
            self._apply_undo()
            return self.get_state()

        if action == "withdraw":
            self.withdrawn = True
            self.game_over = True
            return self.get_state()

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
            changed = True
        else:
            state = self.get_state()
            state["error"] = f"Invalid action: {action}"
            return state

        if changed:
            self._refresh_state_metrics()
            self._save_history()

        return self.get_state()

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
            "Actions:\n"
            "- 'set_R_C_V': Put value V into row R, column C.\n"
            "- 'clear_R_C': Clear the selected editable cell.\n"
            "- 'note_R_C_V': Toggle pencil mark V in row R, column C.\n"
            "- 'undo': Revert the previous move.\n"
            "- 'withdraw': Give up the current puzzle."
        )
