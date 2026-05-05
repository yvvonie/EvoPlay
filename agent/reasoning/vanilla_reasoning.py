"""Vanilla iterative reasoning - simplest LLM reasoning implementation.

This is a straightforward iterative reasoning process:
1. Receive game state and rules
2. Build a prompt
3. Call language model via unified LLM interface
4. Return the action

No complex agent structures, just simple prompt → LLM → action.
"""

from __future__ import annotations

import json
from typing import Any

from agent.llm import LLM
from .base import Reasoning


class VanillaReasoning(Reasoning):
    """
    Simple vanilla iterative reasoning.
    
    Process:
    1. Build prompt from game state + rules + valid actions
    2. Call LLM via unified interface
    3. Return action
    
    That's it. No agent structures, no complex logic.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",  # Default model (check OpenAI docs for latest)
        api_key: str | None = None,
        api_provider: str | None = None,
        api_base: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 50,
        no_thinking: bool = False,
        extra_headers: dict | None = None,
        use_cot: bool = False,
        multimodal: bool = False,
    ):
        """
        Initialize vanilla reasoning.

        Args:
            model: Model name (e.g., "gpt-4", "claude-3-sonnet-20240229")
            api_key: API key (optional, reads from .env if not provided)
            api_provider: Provider name (openai, anthropic, etc.) - auto-detected if None
            api_base: API base URL (for local models like Ollama)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Max tokens in response
        """
        self.use_cot = use_cot
        self.multimodal = multimodal
        # Initialize unified LLM interface
        self.llm = LLM(
            model=model,
            api_key=api_key,
            api_provider=api_provider,
            api_base=api_base,
            temperature=temperature,
            max_tokens=max_tokens,
            no_thinking=no_thinking,
            extra_headers=extra_headers,
        )
    
    def reason(self, game_state: dict[str, Any], valid_actions: list[str], rules: str = "") -> str:
        """
        Vanilla iterative reasoning: prompt → LLM → action.
        
        Args:
            game_state: Current game state (board, score, etc.)
            valid_actions: List of valid actions (e.g., ["up", "down", "left", "right"])
            rules: Game rules text
            
        Returns:
            Action string (one of valid_actions)
        """
        # Build prompt
        game_name = game_state.get("game", "unknown")
        board = game_state.get("board", [])
        score = game_state.get("score", 0)
        
        # Include rules in prompt if provided
        rules_section = ""
        if rules:
            rules_section = f"\n\nGAME RULES:\n{rules}\n"
        
        # Build game-specific extra context and board formatting
        extra_context = ""
        board_str = self._format_board(board)
        state_json = json.dumps(game_state, ensure_ascii=False, indent=2)

        if game_name == "mergefall":
            next_tile = game_state.get("next_tile", "?")
            extra_context = f"\nNext tile to drop: {next_tile}\n"
        elif game_name == "fourinarow":
            pass  # use default board format
        elif game_name == "crossnumber":
            extra_context = (
                f"\nrow_targets: {game_state.get('row_targets', [])}\n"
                f"col_targets: {game_state.get('col_targets', [])}\n"
                f"row_current_sums: {game_state.get('row_current_sums', [])}\n"
                f"col_current_sums: {game_state.get('col_current_sums', [])}\n"
                f"lives: {game_state.get('lives')}/{game_state.get('max_lives')}\n"
                f"undos_remaining: {game_state.get('undos_remaining')}/{game_state.get('max_undos')}\n"
                f"last_feedback: {game_state.get('last_feedback')}\n"
                f"last_mismatch: {game_state.get('last_mismatch')}\n"
            )
        elif game_name == "sudoku":
            extra_context = (
                f"\nfilled_cells: {game_state.get('filled_cells')}/{game_state.get('total_to_fill')}\n"
                f"mistakes: {game_state.get('mistakes')}\n"
                f"lives: {game_state.get('lives')}/{game_state.get('max_lives')}\n"
                f"last_feedback: {game_state.get('last_feedback')}\n"
                f"last_mismatch: {game_state.get('last_mismatch')}\n"
            )

        actions_str = ', '.join(valid_actions)

        if game_name == "fourinarow":
            board_label = "Current board (1=you, 2=opponent, 0=empty):"
        else:
            board_label = "Current board:"

        prompt = f"""You are playing the game "{game_name}".{rules_section}

{board_label}
{board_str}
{extra_context}
IMPORTANT: You MUST choose exactly one action from this list (copy it exactly):
[{actions_str}]

Pick the best action. Respond with ONLY the action string, nothing else."""
        system_message = "You are a game-playing AI agent. Respond with only the action string."

        try:
            # Retry the LLM call up to 20 times if output is not a valid action
            MAX_INVALID_RETRIES = 20
            attempt = 0
            raw_response = ""
            action = ""
            fallback = False
            last_usage = {"input_tokens": 0, "output_tokens": 0}

            while attempt < MAX_INVALID_RETRIES:
                # Multimodal: render board as image and build visual prompt
                if self.multimodal and hasattr(game_state, '__getitem__'):
                    image_path = self._render_board(game_name, game_state)
                    if image_path:
                        mm_prompt = self._build_multimodal_prompt(game_name, game_state, valid_actions, rules)
                        mm_system = "You are a good game player. First give your analysis, then output your answer in the required format."
                        response = self._multimodal_call(mm_prompt, image_path, mm_system)
                    else:
                        response = self.llm.simple_call(prompt, system_message=system_message)
                else:
                    response = self.llm.simple_call(prompt, system_message=system_message)

                raw_response = response.strip()

                # Parse "Answer: xxx" format if CoT
                action = raw_response
                if "Answer:" in raw_response:
                    action = raw_response.split("Answer:")[-1].strip()
                elif "answer:" in raw_response:
                    action = raw_response.split("answer:")[-1].strip()

                # Accumulate usage
                call_usage = getattr(self.llm, "last_usage", {"input_tokens": 0, "output_tokens": 0})
                last_usage = {
                    "input_tokens": last_usage["input_tokens"] + call_usage.get("input_tokens", 0),
                    "output_tokens": last_usage["output_tokens"] + call_usage.get("output_tokens", 0),
                }

                # Validate that the action is in valid_actions
                if action in valid_actions:
                    break  # Success

                attempt += 1
                print(f"Warning: Model returned invalid action '{action}' (attempt {attempt}/{MAX_INVALID_RETRIES})")

            # If still invalid after all retries, fallback to first valid action
            if action not in valid_actions:
                print(f"Exhausted {MAX_INVALID_RETRIES} retries, falling back to first valid action")
                action = valid_actions[0] if valid_actions else ""
                fallback = True

            # Store last response details for logging
            self.last_raw_response = raw_response
            self.last_action = action
            self.last_fallback = fallback
            self.last_usage = last_usage

            return action

        except Exception as e:
            print(f"Error calling model ({self.llm.model}): {e}")
            self.last_raw_response = f"ERROR: {e}"
            self.last_action = ""
            self.last_fallback = True
            raise RuntimeError(f"LLM call failed: {e}") from e
    
    def _format_board(self, board: Any) -> str:
        """Format board for display in prompt."""
        if isinstance(board, list):
            if len(board) > 0 and isinstance(board[0], list):
                # 2D board
                return "\n".join(" ".join(str(cell) for cell in row) for row in board)
            else:
                # 1D board
                return " ".join(str(cell) for cell in board)
        return str(board)

    def _format_fourinarow(self, board: list) -> str:
        """Format Four in a Row board with X/O symbols and column numbers."""
        cols = len(board[0]) if board else 7
        symbol = {0: ".", 1: "X", 2: "O"}
        header = "  " + " ".join(str(c) for c in range(cols))
        rows = []
        for r, row in enumerate(board):
            rows.append(f"{r} " + " ".join(symbol.get(cell, str(cell)) for cell in row))
        return header + "\n" + "\n".join(rows)

    # ── Multimodal support ────────────────────────────────────────

    def _build_multimodal_prompt(self, game_name: str, game_state: dict, valid_actions: list, rules: str) -> str:
        """Build a multimodal prompt where the board is shown as an image, not text."""
        actions_str = ', '.join(valid_actions)

        if game_name == "fourinarow":
            return (
                "You are a good game player. I'll give you a game board as a picture and rules.\n"
                "Your task is:\n"
                "- First, give your answer according to the game board and rules.\n"
                "- Second, output the answer in the required format. The last line of your response "
                "should be in the following format: 'Answer: $YOUR_ANSWER' (without quotes), "
                "where YOUR_ANSWER is your final answer, e.g. 'Answer: 3'\n\n"
                "In the board shown, the red circles labeled 'You' are your pieces, "
                "the black circles labeled 'Bot' are the opponent's pieces, "
                "and the white circles are empty spaces. "
                "The column numbers (0-6) are shown at the top of the board.\n\n"
                "RULES:\n"
                "- This is a 6-row × 7-column vertical grid. Pieces drop to the lowest empty cell in the chosen column.\n"
                "- You and the bot take turns. You move first.\n"
                "- First to connect 4 pieces in a row (horizontally, vertically, or diagonally) wins.\n\n"
                f"Valid columns: [{actions_str}]\n\n"
                "Choose a column number to drop your piece. "
                "The last line of your response should be 'Answer: X', where X is the column number."
            )

        if game_name == "othello6":
            return (
                "You are a good game player. I'll give you a game board as a picture and rules.\n"
                "Your task is:\n"
                "- First, give your answer according to the game board and rules.\n"
                "- Second, output the answer in the required format. The last line of your response "
                "should be in the following format: 'Answer: $YOUR_ANSWER' (without quotes), "
                "where YOUR_ANSWER is your final answer, e.g. 'Answer: 2 3'\n\n"
                "In the board shown, the black circles labeled 'You' are your pieces, "
                "the white circles labeled 'Bot' are the opponent's pieces, "
                "and empty green cells are available spaces. "
                "Small dots indicate valid moves you can make. "
                "Row numbers (0-5) are on the left, column numbers (0-5) are at the top.\n\n"
                "RULES:\n"
                "- This is a 6×6 Othello (Reversi) board.\n"
                "- Place a piece to outflank and flip the opponent's pieces in any direction (horizontal, vertical, diagonal).\n"
                "- You must flip at least one opponent piece per move.\n"
                "- The game ends when neither player can move. The player with more pieces wins.\n\n"
                f"Valid moves: [{actions_str}]\n\n"
                "Choose a position as 'row col'. "
                "The last line of your response should be 'Answer: R C', where R is the row and C is the column."
            )

        # Default: use text rules + image
        return (
            f"You are a good game player. I'll give you a game board as a picture and rules.\n"
            f"Your task is:\n"
            f"- First, give your answer according to the game board and rules.\n"
            f"- Second, output the answer in the required format. The last line of your response "
            f"should be in the following format: 'Answer: $YOUR_ANSWER' (without quotes).\n\n"
            f"{rules}\n\n"
            f"Valid actions: [{actions_str}]\n\n"
            f"Choose the best action. The last line of your response should be 'Answer: X', "
            f"where X is your chosen action."
        )

    def _render_board(self, game_name: str, game_state: dict) -> str | None:
        """Render board as image via backend game's render() method. Returns file path or None."""
        import requests
        try:
            # Call backend to render the board
            board = game_state.get("board", [])
            # Use a temporary game instance to render
            if game_name == "fourinarow":
                from games.game_fourinarow import FourInARow
                temp = FourInARow.__new__(FourInARow)
                temp.board = board
                return temp.render()
            elif game_name == "othello6":
                from games.game_othello6 import Othello6
                temp = Othello6.__new__(Othello6)
                temp.board = board
                temp.size = 6
                return temp.render()
        except Exception as e:
            print(f"  [Multimodal] Failed to render: {e}")
        return None

    def _multimodal_call(self, prompt: str, image_path: str, system_message: str) -> str:
        """Call LLM with text prompt + image."""
        import base64

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        })

        return self.llm.call(messages)
