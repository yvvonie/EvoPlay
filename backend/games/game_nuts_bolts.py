"""Nuts and Bolts game implementation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .base import BaseGame

# 3 full screws + 2 empty = 5 screws
NUM_SCREWS = 5
SCREW_CAPACITY = 3
MAX_UNDOS = 2

class NutsBolts(BaseGame):
    """Nuts and bolts sorting game."""

    name = "nuts_bolts"

    def __init__(self) -> None:
        self.screws: list[list[str]] = []
        self.score: int = 0
        self.game_over: bool = False
        self.won: bool = False
        self.undos_remaining: int = MAX_UNDOS
        self.history: list[dict[str, Any]] = []
        self.selected_screw: int | None = None
        self.current_level: int = 1
        self.max_level: int = 2
        self.screw_capacity: int = 3
        self.num_screws: int = NUM_SCREWS
        self._reset_log()
        self.reset()

    # ── BaseGame interface ──────────────────────────────────────────

    def get_state(self) -> dict[str, Any]:
        return {
            "game": self.name,
            "board": deepcopy(self.screws),
            "score": self.score,
            "game_over": self.game_over,
            "won": self.won,
            "valid_actions": self.valid_actions(),
            "undos_remaining": self.undos_remaining,
            "selected_screw": self.selected_screw,
            "current_level": self.current_level,
            "max_level": self.max_level,
            "screw_capacity": self.screw_capacity,
            "num_screws": self.num_screws
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
        elif action.startswith("select_"):
            screw_idx = int(action.split("_")[1])
            if self.selected_screw is None:
                # Select a source screw
                self.selected_screw = screw_idx
            else:
                # If clicking the same screw, deselect
                if self.selected_screw == screw_idx:
                    self.selected_screw = None
                else:
                    # Try to move from selected to new screw
                    moved = self._move(self.selected_screw, screw_idx)
                    if moved:
                        self.selected_screw = None
                        self.score += 10
                        self._check_win_condition()
                        if self.won:
                            self.game_over = True
                    else:
                        state = self.get_state()
                        state["error"] = "Invalid move."
                        return state
        
        state = self.get_state()
        self._record_log(action, state)
        return state

    def reset(self) -> dict[str, Any]:
        self._reset_log()
        self._load_level(self.current_level)
        return self.get_state()
        
    def _load_level(self, level: int) -> None:
        """Load the given level's configuration."""
        self.score = 0
        self.game_over = False
        self.won = False
        self.undos_remaining = MAX_UNDOS
        self.history = []
        self.selected_screw = None
        
        if level == 1:
            self.screw_capacity = 3
            self.num_screws = 5
            self.screws = [
                ['r', 'r', 'b'],
                ['r', 'y', 'y'],
                ['y', 'b', 'b'],
                [],
                []
            ]
        elif level == 2:
            self.screw_capacity = 4
            self.num_screws = 6
            self.screws = [
                ['b', 'b', 'b', 'r'],
                ['r', 'g', 'g', 'g'],
                ['r', 'r', 'b', 'y'],
                ['y', 'y', 'y', 'g'],
                [],
                []
            ]
            
        self._save_state()

    def valid_actions(self) -> list[str]:
        if self.game_over:
            if self.won and self.current_level < self.max_level:
                return ["next_level"]
            return []
            
        actions = []
        
        # Can undo if has undos and history has more than 1 state
        if self.undos_remaining > 0 and len(self.history) > 1:
            actions.append("undo")
            
        # Clicking a screw
        for i in range(self.num_screws):
            if self.selected_screw is None:
                # Can select a screw if it's not empty
                if len(self.screws[i]) > 0:
                    actions.append(f"select_{i}")
            else:
                # If a screw is selected, can click it again to deselect
                if i == self.selected_screw:
                    actions.append(f"select_{i}")
                # Can move to another screw if it's a valid move
                elif self._is_valid_move(self.selected_screw, i):
                    actions.append(f"select_{i}")
                    
        return actions

    def get_rules(self) -> str:
        return """Nuts and Bolts Game Rules

OBJECTIVE:
Sort all the colored nuts so that each screw contains only one color of nuts.

GAMEPLAY:
- You have 5 screws. Originally, 3 screws are filled with mixed nuts, and 2 are empty.
- Each screw can hold up to 3 nuts format Level 1 and 4 for Level 2.
- You can move the top nut from one screw to another.
- A nut can only be moved onto an empty screw, OR onto a screw where the top nut is the SAME COLOR.
- You cannot move a nut onto a full screw.
- You have 2 Undo moves available per game.

AVAILABLE ACTIONS:
- "select_X": Selects screw X (0-4 or 0-5) as a source, or moves the previously selected nut to screw X.
- "undo": Reverts the last move.
- "next_level": Go to the next level when won.
"""

    # ── Internal helpers ────────────────────────────────────────────

    def _save_state(self) -> None:
        """Save the current board state to history."""
        # Only keep the last state for Undo
        self.history.append({
            "board": deepcopy(self.screws),
            "score": self.score
        })

    def _apply_undo(self) -> None:
        """Revert to the previous state."""
        if self.undos_remaining > 0 and len(self.history) > 1:
            # Remove current state
            self.history.pop()
            # Restore previous state
            prev_state = self.history[-1]
            self.screws = deepcopy(prev_state["board"])
            self.score = deepcopy(prev_state["score"])
            self.undos_remaining -= 1
            self.selected_screw = None

    def _is_valid_move(self, src: int | None, dst: int) -> bool:
        """Check if moving top nut from src to dst is valid."""
        if src is None:
            return False
            
        if src == dst:
            return False
            
        if len(self.screws[src]) == 0:
            return False # Nothing to move
            
        if len(self.screws[dst]) >= self.screw_capacity:
            return False # Destination full
            
        if len(self.screws[dst]) == 0:
            return True # Target is empty, can move any color
            
        # Check if colors match
        src_color = self.screws[src][-1]
        dst_color = self.screws[dst][-1]
        
        return src_color == dst_color

    def _move(self, src: int | None, dst: int) -> bool:
        """Execute a move if valid."""
        if src is None or not self._is_valid_move(src, dst):
            return False
            
        # Save state BEFORE making the move
        self._save_state()
        
        nut = self.screws[src].pop()
        self.screws[dst].append(nut)
        
        return True

    def _check_win_condition(self) -> None:
        """Check if all nuts are sorted by color."""
        # Game is won if there are sufficient completed towers
        # and no partially filled towers.
        
        target_towers = 3 if self.current_level == 1 else 4
        completed_towers = 0
        
        for screw in self.screws:
            if len(screw) == 0:
                continue
                
            # If not empty, it must have full capacity 
            # and they must all be the same color
            if len(screw) == self.screw_capacity:
                first_color = screw[0]
                if all(n == first_color for n in screw):
                    completed_towers += 1
                else:
                    return # Not completed
            else:
                return # Not completed, sizes must be 0 or max capacity
                
        if completed_towers == target_towers:
            self.won = True
