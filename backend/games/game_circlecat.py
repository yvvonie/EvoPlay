"""Circle the Cat – hexagonal board game for EvoPlay."""

from __future__ import annotations

import random
from collections import deque
from copy import deepcopy
from typing import Any

from games.base import BaseGame


class CircleCat(BaseGame):
    """
    11x11 hexagonal grid game where the player places walls to trap a cat.
    The cat uses BFS-based smart pathfinding to escape to the boundary.
    Only "hard" difficulty (smart cat).
    """

    name = "circlecat"

    def __init__(self, size: int = 13):
        self.size = size
        self.cat: tuple[int, int] = (size // 2, size // 2)
        self.walls: set[tuple[int, int]] = set()
        self.board: list[list[str]] = []
        self.game_over: bool = False
        self.won: bool = False
        self.score: int = 0
        self.difficulty: str = "medium"
        self._seed: int | None = None
        self._reset_log()
        self._generate()

    # ── Board generation ───────────────────────────────────────────

    def _generate(self, seed: int | None = None):
        if seed is not None:
            self._seed = seed
        elif self._seed is None:
            self._seed = random.randint(0, 2**31)
        rng = random.Random(self._seed)

        center = self.size // 2
        self.board = [["0" for _ in range(self.size)] for _ in range(self.size)]
        self.cat = (center, center)
        self.board[center][center] = "C"
        self.walls = set()

        # --- Strategic wall placement (15 walls total) ---
        dist_map = self._bfs_distances(self.cat)

        # Layer 1: inner support (distance 2) — 3 walls
        inner_cells = [
            pos for pos, d in dist_map.items()
            if d == 2
            and 1 <= pos[0] < self.size - 1
            and 1 <= pos[1] < self.size - 1
            and pos != self.cat
        ]
        rng.shuffle(inner_cells)
        for i, j in inner_cells[:3]:
            self.board[i][j] = "1"
            self.walls.add((i, j))

        # Layer 2: broken ring (distance 3-4) — 5 walls scattered
        ring_cells = [
            pos for pos, d in dist_map.items()
            if d in (3, 4)
            and 1 <= pos[0] < self.size - 1
            and 1 <= pos[1] < self.size - 1
            and pos != self.cat
            and pos not in self.walls
        ]
        rng.shuffle(ring_cells)
        for i, j in ring_cells[:4]:
            self.board[i][j] = "1"
            self.walls.add((i, j))

        # Layer 3: outer walls (distance 5+) — 8 walls, spread across 4 quadrants
        # Divide board into 4 quadrants relative to cat center
        outer_cells = [
            pos for pos, d in dist_map.items()
            if d >= 5
            and 1 <= pos[0] < self.size - 1
            and 1 <= pos[1] < self.size - 1
            and pos != self.cat
            and pos not in self.walls
        ]
        # Split into quadrants: top-left, top-right, bottom-left, bottom-right
        quadrants = {q: [] for q in range(4)}
        for pos in outer_cells:
            r, c = pos
            qi = (0 if r < center else 2) + (0 if c < center else 1)
            quadrants[qi].append(pos)
        for q in quadrants:
            rng.shuffle(quadrants[q])
        # Place 2 walls per quadrant
        for q in range(4):
            for pos in quadrants[q][:2]:
                self.board[pos[0]][pos[1]] = "1"
                self.walls.add(pos)

        self.game_over = False
        self.won = False
        self.score = 0

        # Validate: simulate greedy player vs cat. If player can't win, regenerate.
        if not self._simulate_winnable():
            self._seed = rng.randint(0, 2**31)
            self._generate(self._seed)

    def _simulate_winnable(self) -> bool:
        """Simulate a greedy player (place wall to maximize cat distance) vs smart cat.
        Returns True if the greedy player wins within 50 turns."""
        from copy import deepcopy
        sim_board = deepcopy(self.board)
        sim_walls = set(self.walls)
        sim_cat = self.cat

        for _ in range(50):
            # Player turn: find best wall placement (maximize cat's BFS distance)
            best_wall = None
            best_dist = -1
            candidates = [
                (i, j)
                for i in range(1, self.size - 1)
                for j in range(1, self.size - 1)
                if sim_board[i][j] == "0" and (i, j) != sim_cat
            ]
            for wall in candidates:
                test_walls = sim_walls | {wall}
                dist = self._sim_bfs_to_exit(sim_cat, sim_board, test_walls)
                if dist > best_dist:
                    best_dist = dist
                    best_wall = wall

            if best_wall is None:
                return False

            sim_board[best_wall[0]][best_wall[1]] = "1"
            sim_walls.add(best_wall)

            # Check if cat is already trapped
            if self._sim_bfs_to_exit(sim_cat, sim_board, sim_walls) == float("inf"):
                return True

            # Cat turn: find best move using BFS
            neighbors = self.get_neighbors(sim_cat)
            valid_moves = [n for n in neighbors if sim_board[n[0]][n[1]] == "0"]

            if not valid_moves:
                return True  # cat trapped

            # Cat escapes immediately?
            for m in valid_moves:
                if self.is_boundary(m):
                    return False

            # Cat picks shortest BFS to exit
            best_move = valid_moves[0]
            min_d = float("inf")
            for m in valid_moves:
                d = self._sim_bfs_to_exit(m, sim_board, sim_walls)
                if d < min_d:
                    min_d = d
                    best_move = m

            sim_board[sim_cat[0]][sim_cat[1]] = "0"
            sim_board[best_move[0]][best_move[1]] = "C"
            sim_cat = best_move

            if self.is_boundary(sim_cat):
                return False

        return False  # didn't win in 50 turns

    def _sim_bfs_to_exit(self, start, board, walls) -> float:
        """BFS from start to boundary, respecting walls."""
        visited = {start}
        q = deque([(start, 0)])
        while q:
            pos, dist = q.popleft()
            if self.is_boundary(pos):
                return dist
            for nb in self.get_neighbors(pos):
                if nb not in visited and nb not in walls and board[nb[0]][nb[1]] != "1":
                    visited.add(nb)
                    q.append((nb, dist + 1))
        return float("inf")

    # ── Hex neighbours ─────────────────────────────────────────────

    def get_neighbors(self, pos: tuple[int, int]) -> list[tuple[int, int]]:
        r, c = pos
        if r % 2 == 0:
            offsets = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0), (1, 1)]
        else:
            offsets = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)]
        result = []
        for dr, dc in offsets:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.size and 0 <= nc < self.size:
                result.append((nr, nc))
        return result

    def is_boundary(self, pos: tuple[int, int]) -> bool:
        r, c = pos
        return r == 0 or r == self.size - 1 or c == 0 or c == self.size - 1

    # ── BFS distances from a position ─────────────────────────────

    def _bfs_distances(self, start: tuple[int, int]) -> dict[tuple[int, int], int]:
        """BFS from start, return distance map to all reachable cells (ignoring walls)."""
        dist = {start: 0}
        q = deque([start])
        while q:
            pos = q.popleft()
            for nb in self.get_neighbors(pos):
                if nb not in dist and 0 <= nb[0] < self.size and 0 <= nb[1] < self.size:
                    dist[nb] = dist[pos] + 1
                    q.append(nb)
        return dist

    # ── BFS distance to boundary ───────────────────────────────────

    def calculate_distance(self, pos: tuple[int, int], temp_walls: set) -> float:
        visited = {pos}
        q = deque([(pos[0], pos[1], 0)])
        while q:
            x, y, dist = q.popleft()
            if self.is_boundary((x, y)):
                return dist + 1
            for nx, ny in self.get_neighbors((x, y)):
                if (nx, ny) not in visited and (nx, ny) not in temp_walls and (nx, ny) != self.cat:
                    visited.add((nx, ny))
                    q.append((nx, ny, dist + 1))
        return float("inf")

    # ── Smart cat move (hard difficulty) ───────────────────────────

    def find_best_cat_move(self) -> tuple[int, int] | None:
        """Minimax: cat picks the move that minimizes its escape distance
        even after the player places the best possible wall."""
        current_pos = self.cat
        neighbors = self.get_neighbors(current_pos)
        valid_moves = [n for n in neighbors if self.board[n[0]][n[1]] == "0"]

        if not valid_moves:
            return None  # trapped

        # Check for immediate boundary escape
        for move in valid_moves:
            if self.is_boundary(move):
                return move

        best_move = valid_moves[0]  # fallback: always have a move if valid_moves is not empty
        best_worst_dist = float("inf")
        best_direct_dist = float("inf")

        for move in valid_moves:
            # Simulate cat moving here
            temp_walls = set(self.walls)
            temp_cat = move

            # Find all positions where player could place a wall
            possible_walls = [
                (i, j)
                for i in range(self.size)
                for j in range(self.size)
                if self.board[i][j] == "0"
                and (i, j) != temp_cat
                and (i, j) != current_pos
            ]

            if not possible_walls:
                # No walls can be placed — just use direct BFS
                dist = self.calculate_distance(temp_cat, temp_walls)
                if dist < best_worst_dist:
                    best_worst_dist = dist
                    best_move = move
                continue

            # Worst case: player places the wall that maximizes cat's distance
            worst_dist = 0
            for wall in possible_walls:
                new_walls = temp_walls | {wall}
                dist = self.calculate_distance(temp_cat, new_walls)
                if dist > worst_dist:
                    worst_dist = dist

            # Cat picks the move where the worst case is still minimal
            # Tiebreak: prefer shorter direct BFS distance (avoid oscillation)
            direct_dist = self._bfs_to_exit(move)
            if worst_dist < best_worst_dist or (worst_dist == best_worst_dist and direct_dist < best_direct_dist):
                best_worst_dist = worst_dist
                best_direct_dist = direct_dist
                best_move = move

        return best_move

    def _bfs_to_exit(self, start: tuple[int, int]) -> float:
        """BFS from start to nearest boundary empty cell, ignoring walls."""
        visited = {start, self.cat}
        q = deque([(start, 0)])
        while q:
            pos, dist = q.popleft()
            if self.is_boundary(pos):
                return dist
            for nb in self.get_neighbors(pos):
                if nb not in visited and self.board[nb[0]][nb[1]] != "1":
                    visited.add(nb)
                    q.append((nb, dist + 1))
        return float("inf")

    # ── Display board with E markers ───────────────────────────────

    def _display_board(self) -> list[list[str]]:
        """Return inner 9x9 board (skip outermost ring). Boundary of this visible
        area corresponds to row/col 1 and 9 of the internal 11x11 board."""
        return [row[1:-1] for row in self.board[1:-1]]

    # ── BaseGame interface ─────────────────────────────────────────

    def set_difficulty(self, difficulty: str) -> None:
        """No-op: only hard difficulty is available."""
        self.difficulty = "hard"

    def get_state(self) -> dict[str, Any]:
        # Offset cat_pos and valid_actions to match visible 9x9 coordinates
        vis_cat = [self.cat[0] - 1, self.cat[1] - 1]
        return {
            "board": self._display_board(),
            "game_over": self.game_over,
            "won": self.won,
            "score": self.score,
            "cat_pos": vis_cat,
            "valid_actions": self.valid_actions(),
            "difficulty": self.difficulty,
            "game": self.name,
        }

    def reset(self) -> dict[str, Any]:
        self._seed = random.randint(0, 2**31)
        self._generate(self._seed)
        self._reset_log()
        return self.get_state()

    def apply_action(self, action: str) -> dict[str, Any]:
        if self.game_over:
            return self.get_state()

        # Parse action (visible 9x9 coordinates, convert to internal 11x11)
        try:
            parts = action.strip().split()
            vr, vc = int(parts[0]), int(parts[1])
            r, c = vr + 1, vc + 1  # offset to internal coordinates
        except (ValueError, IndexError):
            state = self.get_state()
            state["error"] = f"Invalid action format: '{action}'. Use 'r c'."
            return state

        # Validate
        if not (1 <= r < self.size - 1 and 1 <= c < self.size - 1):
            state = self.get_state()
            state["error"] = f"Position ({vr},{vc}) is out of bounds."
            return state

        if self.board[r][c] != "0" or self.is_boundary((r, c)):
            state = self.get_state()
            state["error"] = f"Cannot place wall at ({r},{c})."
            return state

        # Place wall
        self.board[r][c] = "1"
        self.walls.add((r, c))

        # Cat's turn
        cat_move = self.find_best_cat_move()

        # Log format: "wall:vr,vc|cat:vr,vc" (visible coordinates)
        log_action = f"wall:{vr},{vc}"

        if cat_move is None:
            # Cat is trapped - player wins
            self.game_over = True
            self.won = True
            self.score = 1
            log_action += "|cat:trapped"
            state = self.get_state()
            self._record_log(log_action, state)
            return state

        cat_vr, cat_vc = cat_move[0] - 1, cat_move[1] - 1  # visible coords

        if self.is_boundary(cat_move):
            # Cat reaches exit - player loses
            old_r, old_c = self.cat
            self.board[old_r][old_c] = "0"
            self.board[cat_move[0]][cat_move[1]] = "C"
            self.cat = cat_move
            self.game_over = True
            self.won = False
            self.score = 0
            log_action += f"|cat:escaped({cat_vr},{cat_vc})"
            state = self.get_state()
            self._record_log(log_action, state)
            return state

        # Cat moves to new position
        old_r, old_c = self.cat
        self.board[old_r][old_c] = "0"
        self.board[cat_move[0]][cat_move[1]] = "C"
        self.cat = cat_move
        log_action += f"|cat:{cat_vr},{cat_vc}"

        # Check if cat has no path to boundary (fully enclosed)
        if self._bfs_to_exit(cat_move) == float("inf"):
            self.game_over = True
            self.won = True
            self.score = 1

        state = self.get_state()
        self._record_log(log_action, state)
        return state

    def valid_actions(self) -> list[str]:
        if self.game_over:
            return []
        actions = []
        # Only interior cells (not outer ring row 0/10, col 0/10)
        # Return visible 9x9 coordinates (offset by -1)
        for i in range(1, self.size - 1):
            for j in range(1, self.size - 1):
                if self.board[i][j] == "0" and not self.is_boundary((i, j)):
                    actions.append(f"{i - 1} {j - 1}")
        return actions

    def get_rules(self) -> str:
        return (
            "Below is a hexagonal board represented in a textual 11x11 grid. "
            "Each cell is labeled with a character: '1' = wall, 'C' = cat, '0' = empty space. "
            "Although shown as a square grid, each row is slightly offset from its neighbors in a hex layout, "
            "and each cell has up to six neighbors (not four or eight as in a square grid).\n\n"
            "HEXAGONAL NEIGHBORS:\n"
            "For a cell at coordinates (r, c):\n"
            "- If r is even: neighbors are (r-1,c), (r-1,c+1), (r,c-1), (r,c+1), (r+1,c), (r+1,c+1)\n"
            "- If r is odd: neighbors are (r-1,c-1), (r-1,c), (r,c-1), (r,c+1), (r+1,c-1), (r+1,c)\n\n"
            "RULES:\n"
            "- You and the cat take turns. On your turn, place a wall on any empty cell ('0') that is not on the boundary.\n"
            "- On the cat's turn, it moves to one of its adjacent empty cells.\n"
            "- If the cat reaches the boundary (row 0, row 10, col 0, or col 10), you lose.\n"
            "- If the cat has no path to reach the boundary, you win.\n\n"
            "AVAILABLE ACTIONS:\n"
            "- Action format: 'r c' (e.g., '3 5') to place a wall at row 3, column 5.\n"
            "- You can place a wall on any empty cell ('0') that is not on the boundary (row 0/10 or col 0/10).\n"
        )

    def restore_state(self, saved_state: dict[str, Any]) -> None:
        """Restore from saved state."""
        if "board" in saved_state:
            # Convert display board (with E) back to internal board (with 0)
            display_board = saved_state["board"]
            self.board = []
            self.walls = set()
            self.cat = (self.size // 2, self.size // 2)
            for i in range(len(display_board)):
                row = []
                for j in range(len(display_board[i])):
                    cell = display_board[i][j]
                    if cell == "1":
                        row.append("1")
                        self.walls.add((i, j))
                    elif cell == "C":
                        row.append("C")
                        self.cat = (i, j)
                    else:
                        row.append(cell)
                self.board.append(row)
        if "game_over" in saved_state:
            self.game_over = saved_state["game_over"]
        if "won" in saved_state:
            self.won = saved_state["won"]
        if "score" in saved_state:
            self.score = saved_state["score"]
