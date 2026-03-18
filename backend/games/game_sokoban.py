"""Sokoban game implementation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, List, Tuple

from .base import BaseGame

# Map layout from image:
# #####
# #@  #
# # O$#
# # $ ###
# #   ..#
# #######

# Internal representation:
# ' ' = Floor
# '#' = Wall
# 'O' = Obstacle (treat as Wall for movement)
# '.' = Goal

INITIAL_MAP = [
    ['#', '#', '#', '#', '#', ' ', ' '],
    ['#', ' ', ' ', ' ', '#', ' ', ' '],
    ['#', ' ', 'O', ' ', '#', ' ', ' '],
    ['#', ' ', ' ', ' ', '#', '#', '#'],
    ['#', ' ', ' ', ' ', '.', '.', '#'],
    ['#', '#', '#', '#', '#', '#', '#'],
]

INITIAL_PLAYER_POS = [1, 1]
INITIAL_BOXES = [[2, 3], [3, 2]]
MAX_UNDOS = 1

class Sokoban(BaseGame):
    """Classic Sokoban box-pushing game."""

    name = "sokoban"

    def __init__(self) -> None:
        self.map: list[list[str]] = []
        self.player_pos: list[int] = []
        self.boxes: list[list[int]] = []
        self.score: int = 0
        self.game_over: bool = False
        self.won: bool = False
        self.undo_available: bool = True
        self.history: dict[str, Any] | None = None
        
        self.current_level: int = 1
        self.max_level: int = 2
        
        self._reset_log()
        self.reset()

    # ── BaseGame interface ──────────────────────────────────────────

    def get_state(self) -> dict[str, Any]:
        return {
            "game": self.name,
            "board": {
                "map": self.map,
                "player_pos": self.player_pos,
                "boxes": self.boxes
            },
            "score": self.score,
            "game_over": self.game_over,
            "won": self.won,
            "valid_actions": self.valid_actions(),
            "undo_available": self.undo_available,
            "current_level": self.current_level,
            "max_level": self.max_level
        }

    def apply_action(self, action: str) -> dict[str, Any]:
        action = action.strip().lower()

        if self.game_over and action != "next_level":
            state = self.get_state()
            state["error"] = "Game is already over."
            return state

        if action not in self.valid_actions():
            state = self.get_state()
            state["error"] = f"Invalid action: {action}"
            return state

        if action == "undo":
            self._apply_undo()
        elif action == "next_level":
            self.current_level += 1
            self._load_level(self.current_level)
        elif action in ["up", "down", "left", "right"]:
            self._move(action)
        
        state = self.get_state()
        self._record_log(action, state)
        return state

    def reset(self) -> dict[str, Any]:
        self._reset_log()
        self._load_level(self.current_level)
        return self.get_state()
        
    def _load_level(self, level: int) -> None:
        if level == 1:
            self.map = [
                ['#', '#', '#', '#', '#', '#', '#'],
                ['#', ' ', ' ', ' ', ' ', '.', '#'],
                ['#', '#', '#', '#', '#', '#', '#']
            ]
            self.player_pos = [1, 1]
            self.boxes = [[1, 3]]
        elif level == 2:
            self.map = deepcopy(INITIAL_MAP)
            self.player_pos = deepcopy(INITIAL_PLAYER_POS)
            self.boxes = deepcopy(INITIAL_BOXES)

        self.score = 0
        self.game_over = False
        self.won = False
        self.undo_available = True
        self.history = None

    def valid_actions(self) -> list[str]:
        if self.game_over:
            if self.won and self.current_level < self.max_level:
                return ["next_level"]
            return []
            
        actions = []
        
        if self.undo_available and self.history is not None:
            actions.append("undo")
            
        for direction in ["up", "down", "left", "right"]:
            if self._can_move(direction):
                actions.append(direction)
                    
        return actions

    def get_rules(self) -> str:
        return """Sokoban Game Rules

OBJECTIVE:
Push all boxes onto the goal squares.

GAMEPLAY:
- You control the player character (hardhat worker).
- You can move up, down, left, or right into empty spaces.
- You can push a single box by moving into it, provided the space behind the box is empty or a goal.
- You CANNOT pull boxes.
- You CANNOT push a box into a wall, the rope obstacle, or another box.
- You have 1 Undo available per game.

AVAILABLE ACTIONS:
- "up", "down", "left", "right": Move the player or push a box.
- "undo": Reverts the last move.
"""

    # ── Internal helpers ────────────────────────────────────────────

    def _save_state(self) -> None:
        """Save the current state to history."""
        self.history = {
            "player_pos": deepcopy(self.player_pos),
            "boxes": deepcopy(self.boxes),
            "score": self.score
        }

    def _apply_undo(self) -> None:
        """Revert to the previous state."""
        history = self.history
        if self.undo_available and history is not None:
            self.player_pos = deepcopy(history["player_pos"])
            self.boxes = deepcopy(history["boxes"])
            self.score = history["score"]
            self.undo_available = False # Only 1 undo allowed
            self.history = None

    def _get_delta(self, direction: str) -> tuple[int, int]:
        if direction == "up": return -1, 0
        if direction == "down": return 1, 0
        if direction == "left": return 0, -1
        if direction == "right": return 0, 1
        return 0, 0
        
    def _is_walkable(self, r: int, c: int) -> bool:
        if r < 0 or r >= len(self.map) or c < 0 or c >= len(self.map[0]):
            return False
        return self.map[r][c] in [' ', '.']

    def _get_box_index(self, r: int, c: int) -> int | None:
        for i, box in enumerate(self.boxes):
            if box[0] == r and box[1] == c:
                return i
        return None

    def _can_move(self, direction: str) -> bool:
        dr, dc = self._get_delta(direction)
        nr, nc = self.player_pos[0] + dr, self.player_pos[1] + dc
        
        if not self._is_walkable(nr, nc):
            return False
            
        box_idx = self._get_box_index(nr, nc)
        if box_idx is not None:
            # Check space behind box
            nnr, nnc = nr + dr, nc + dc
            if not self._is_walkable(nnr, nnc):
                return False
            if self._get_box_index(nnr, nnc) is not None:
                return False
                
        return True

    def _move(self, direction: str) -> None:
        if not self._can_move(direction):
            return
            
        self._save_state()
        
        dr, dc = self._get_delta(direction)
        nr, nc = self.player_pos[0] + dr, self.player_pos[1] + dc
        
        box_idx = self._get_box_index(nr, nc)
        if box_idx is not None:
            # Push the box
            box = self.boxes[box_idx]
            box[0] = box[0] + dr
            box[1] = box[1] + dc
            
        self.player_pos = [nr, nc]
        self.score += 1
        
        self._check_win_condition()

    def _check_win_condition(self) -> None:
        """Check if all boxes are on goals."""
        goals = []
        for r in range(len(self.map)):
            for c in range(len(self.map[r])):
                if self.map[r][c] == '.':
                    goals.append([r, c])
                    
        # Check if every box coordinates exists in goals coordinates
        boxes_on_goal = 0
        for box in self.boxes:
            for goal in goals:
                if box[0] == goal[0] and box[1] == goal[1]:
                    boxes_on_goal += 1
                    break
                    
        if boxes_on_goal == len(self.boxes) and len(self.boxes) == len(goals):
            self.won = True
            self.game_over = True
