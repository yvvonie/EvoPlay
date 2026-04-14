import copy
from typing import Any, Dict, List, Optional
from .base import BaseGame

LEVELS = {
    1: {
        "difficulty": "easy",
        "grid": [
            [5, 1, 6, 2],
            [8, 2, 4, 2],
            [2, 2, 2, 6],
            [1, 9, 9, 2]
        ],
        "row_targets": [1, 2, 4, 3],
        "col_targets": [3, 3, 2, 2]
    },
    2: {
        "difficulty": "easy",
        "grid": [
            [8, 2, 3, 1],
            [8, 1, 8, 3],
            [1, 8, 9, 1],
            [1, 1, 8, 3]
        ],
        "row_targets": [4, 4, 1, 1],
        "col_targets": [2, 1, 3, 4]
    },
    3: {
        "difficulty": "easy",
        "grid": [
            [3, 1, 4, 2],
            [2, 5, 1, 3],
            [1, 4, 2, 5],
            [4, 2, 3, 1]
        ],
        "row_targets": [6, 6, 8, 6],
        "col_targets": [8, 8, 3, 7]
    },
    4: {
        "difficulty": "easy",
        "grid": [
            [2, 2, 1, 2],
            [7, 2, 4, 4],
            [2, 1, 6, 2],
            [1, 2, 1, 1]
        ],
        "row_targets": [5, 4, 3, 3],
        "col_targets": [5, 1, 6, 3]
    },
    5: {
        "difficulty": "medium",
        "grid": [
            [3, 3, 4, 4],
            [5, 4, 2, 5],
            [5, 2, 6, 2],
            [6, 2, 9, 8]
        ],
        "row_targets": [3, 2, 2, 2],
        "col_targets": [3, 2, 2, 2]
    },
    6: {
        "difficulty": "medium",
        "grid": [
            [1, 5, 1, 6, 6],
            [3, 7, 6, 7, 2],
            [1, 3, 3, 2, 2],
            [5, 1, 6, 8, 3],
            [8, 2, 1, 1, 7]
        ],
        "row_targets": [7, 3, 2, 6, 1],
        "col_targets": [9, 6, 1, 1, 2]
    },
    7: {
        "difficulty": "medium",
        "grid": [
            [1, 4, 4, 5],
            [4, 8, 4, 5],
            [8, 5, 5, 3],
            [3, 9, 8, 5]
        ],
        "row_targets": [5, 8, 8, 9],
        "col_targets": [1, 17, 9, 3],
        "solution_states": [
            [1, -1, 1, -1],
            [-1, 1, -1, -1],
            [-1, -1, 1, 1],
            [-1, 1, -1, -1]
        ]
    },
    8: {
        "difficulty": "hard",
        "grid": [
            [4, 6, 5, 4, 7, 2],
            [9, 5, 8, 1, 3, 3],
            [1, 5, 3, 3, 3, 3],
            [8, 1, 5, 4, 9, 6],
            [1, 5, 8, 6, 2, 3],
            [6, 7, 6, 9, 8, 2]
        ],
        "row_targets": [9, 1, 15, 10, 9, 14],
        "col_targets": [7, 6, 16, 18, 3, 8]
    },
    9: {
        "difficulty": "hard",
        "grid": [
            [4, 6, 9, 2, 9, 6],
            [6, 1, 5, 6, 6, 6],
            [7, 5, 9, 9, 1, 1],
            [1, 5, 2, 9, 7, 6],
            [7, 6, 2, 7, 2, 7],
            [7, 9, 6, 6, 6, 4]
        ],
        "row_targets": [18, 12, 6, 3, 24, 22],
        "col_targets": [1, 12, 24, 19, 18, 11],
        "solution_states": [
            [-1, -1,  1, -1,  1, -1],
            [-1,  1,  1,  1, -1, -1],
            [-1,  1, -1, -1,  1, -1],
            [ 1, -1,  1, -1, -1, -1],
            [-1,  1,  1,  1,  1,  1],
            [-1, -1,  1,  1,  1,  1]
        ]
    },
    10: {
        "difficulty": "hard",
        "grid": [
            [4, 3, 7, 9, 6, 7],
            [4, 2, 9, 1, 2, 7],
            [3, 3, 5, 5, 4, 5],
            [2, 5, 3, 6, 4, 6],
            [4, 2, 1, 2, 4, 2],
            [8, 7, 5, 5, 4, 4]
        ],
        "row_targets": [11, 10, 6, 10, 7, 16],
        "col_targets": [13, 17, 9, 3, 4, 14],
        "solution_states": [
            [ 1, -1, -1, -1, -1,  1],
            [-1,  1, -1,  1, -1,  1],
            [ 1,  1, -1, -1, -1, -1],
            [ 1,  1,  1, -1, -1, -1],
            [ 1, -1,  1,  1, -1, -1],
            [-1,  1,  1, -1,  1, -1]
        ]
    }
}

class Crossnumber(BaseGame):
    name = "crossnumber"
    
    def __init__(self):
        self.max_level = len(LEVELS)
        self.current_level = 1
        self.difficulty = "easy"
        self.grid = []
        self.row_targets = []
        self.col_targets = []
        # cell_states: 0 = unknown, 1 = confirm, -1 = erase
        self.cell_states = []
        self.rows = 0
        self.cols = 0
        self.score = 0
        self.game_over = False
        self.won = False
        self.withdrawn = False
        self.history = []
        self.undo_available = False
        self._reset_log()
        self.reset()
        
    def reset(self) -> Dict[str, Any]:
        self._load_level(self.current_level)
        return self.get_state()

    def set_difficulty(self, difficulty: str) -> None:
        self.difficulty = difficulty
        start_level = {"easy": 1, "medium": 5, "hard": 8}.get(difficulty, 1)
        if start_level in LEVELS:
            self.current_level = start_level
        else:
            self.current_level = 1

    def _load_level(self, level: int):
        if level not in LEVELS:
            level = 1
        self.current_level = level
        level_data = LEVELS[level]
        self.difficulty = level_data.get("difficulty", "easy")
        self.grid = copy.deepcopy(level_data["grid"])
        self.row_targets = list(level_data["row_targets"])
        self.col_targets = list(level_data["col_targets"])
        self.rows = len(self.grid)
        self.cols = len(self.grid[0]) if self.rows > 0 else 0
        self.cell_states = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self.score = 0
        self.game_over = False
        self.won = False
        self.withdrawn = False
        self.history = []
        self._save_state_to_history()
        
    def _save_state_to_history(self):
        self.history.append({
            "cell_states": copy.deepcopy(self.cell_states),
            "score": self.score
        })
        self.undo_available = len(self.history) > 1

    def _apply_undo(self):
        if len(self.history) > 1:
            self.history.pop()  # Remove current
            last_state = self.history[-1]
            self.cell_states = copy.deepcopy(last_state["cell_states"])
            self.score = last_state["score"]
            self.game_over = False
            self.won = False
            self.withdrawn = False
            self.undo_available = len(self.history) > 1
            
    def get_state(self) -> Dict[str, Any]:
        return {
            "grid": self.grid,
            "row_targets": self.row_targets,
            "col_targets": self.col_targets,
            "cell_states": self.cell_states,
            "rows": self.rows,
            "cols": self.cols,
            "score": self.score,
            "game_over": self.game_over,
            "won": self.won,
            "withdrawn": self.withdrawn,
            "valid_actions": self.valid_actions(),
            "undo_available": self.undo_available,
            "current_level": self.current_level,
            "max_level": self.max_level,
            "difficulty": self.difficulty
        }
        
    def get_rules(self) -> str:
        return (
            "Crossnumber (Cross Sums) Rules:\n"
            "1. You are given a grid of numbers, along with target sums for each row and column.\n"
            "2. Your goal is to mark every cell as either 'confirm' (keep) or 'erase' (remove).\n"
            "3. The sum of the 'confirmed' numbers in each row must exactly match the row's target.\n"
            "4. The sum of the 'confirmed' numbers in each column must exactly match the column's target.\n"
            "5. To win, ALL cells must be marked (no 'unknown' cells), and all row/column sums must be correct.\n"
            "Actions:\n"
            "- 'confirm_R_C': Mark the cell at row R, column C as confirmed.\n"
            "- 'erase_R_C': Mark the cell at row R, column C as erased.\n"
            "- 'clear_R_C': Reset the cell at row R, column C to unknown.\n"
            "- 'undo': Undo the last move.\n"
            "- 'withdraw': Give up the current level."
        )
        
    def valid_actions(self) -> List[str]:
        if self.game_over:
            if (self.won or self.withdrawn) and self.current_level < self.max_level:
                return ["next_level"]
            return []
            
        actions = ["withdraw"]
        if self.undo_available:
            actions.append("undo")
            
        for r in range(self.rows):
            for c in range(self.cols):
                state = self.cell_states[r][c]
                if state != 1:
                    actions.append(f"confirm_{r}_{c}")
                if state != -1:
                    actions.append(f"erase_{r}_{c}")
                if state != 0:
                    actions.append(f"clear_{r}_{c}")
                    
        return actions
        
    def apply_action(self, action: str) -> Dict[str, Any]:
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
            return self.get_state()
            
        if action == "withdraw":
            self.withdrawn = True
            self.game_over = True
            return self.get_state()
            
        if action == "next_level":
            self.current_level += 1
            self._load_level(self.current_level)
            return self.get_state()
            
        # Parse confirm/erase/clear
        parts = action.split("_")
        if len(parts) == 3:
            cmd, r_str, c_str = parts
            r, c = int(r_str), int(c_str)
            if cmd == "confirm":
                self.cell_states[r][c] = 1
            elif cmd == "erase":
                self.cell_states[r][c] = -1
            elif cmd == "clear":
                self.cell_states[r][c] = 0
                
        self.score += 1 # small reward for doing an action
        self._save_state_to_history()
        self._check_win_condition()
        
        return self.get_state()
        
    def _check_win_condition(self):
        # Check if any cell is unknown
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cell_states[r][c] == 0:
                    return # Still playing
                    
        # Check row sums
        for r in range(self.rows):
            row_sum = 0
            for c in range(self.cols):
                if self.cell_states[r][c] == 1:
                    row_sum += self.grid[r][c]
            if row_sum != self.row_targets[r]:
                return # Incorrect sum, not won yet
                
        # Check col sums
        for c in range(self.cols):
            col_sum = 0
            for r in range(self.rows):
                if self.cell_states[r][c] == 1:
                    col_sum += self.grid[r][c]
            if col_sum != self.col_targets[c]:
                return # Incorrect sum
                
        self.won = True
        self.game_over = True
        self.score += 100 # Win bonus
