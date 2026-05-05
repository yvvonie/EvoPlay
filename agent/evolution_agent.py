"""Evolution Agent — minimal self-play with reflection for human-LLM comparison.

Design principles:
- Frozen model (no fine-tuning, no GRPO)
- Only change between episodes: accumulated experience text in prompt
- After each game, LLM reflects on the full trajectory
- Reflection summary is appended to experience buffer
- Same opponent as humans (minimax hard)

Usage:
    python agent/evolution_agent.py \
        --game fourinarow --model openai/Qwen/Qwen3.5-9B \
        --api-key KEY --api-base URL \
        --episodes 30 --no-thinking
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import requests

from agent.reasoning import VanillaReasoning


class EvolutionAgent:
    """Minimal agent that plays repeatedly and accumulates experience."""

    def __init__(
        self,
        game: str,
        model: str,
        api_key: str,
        api_base: str,
        backend_url: str = "http://localhost:5001",
        max_tokens: int = 4096,
        no_thinking: bool = False,
        temperature: float = 0.7,
        reflect_model: str | None = None,
        reflect_api_key: str | None = None,
        reflect_api_base: str | None = None,
        multimodal: bool = False,
        play_prompt_style: str = "simple",       # "simple" (vanilla) or "cel" (structured <reason>/<answer>)
        reflect_prompt_style: str = "simple",    # "simple" (rule list) or "cel" (Master Rulebook)
        subdir: str | None = None,               # override log sub-directory name under evolution_logs/<game>/
    ):
        self.game = game
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.backend_url = backend_url
        self.max_tokens = max_tokens
        self.no_thinking = no_thinking
        self.temperature = temperature

        # Reflection model (optional override). Defaults to play model.
        self.reflect_model = reflect_model or model
        self.reflect_api_key = reflect_api_key or api_key
        self.reflect_api_base = reflect_api_base if reflect_api_base is not None else api_base

        self.multimodal = multimodal
        self.play_prompt_style = play_prompt_style
        self.reflect_prompt_style = reflect_prompt_style

        # Use VanillaReasoning for game play (identical prompts)
        self.reasoning = VanillaReasoning(
            model=model,
            api_key=api_key,
            api_provider=None,
            api_base=api_base,
            temperature=temperature,
            max_tokens=max_tokens,
            no_thinking=no_thinking,
            multimodal=multimodal,
        )

        # Strategic knowledge — a single document that gets refined each episode
        self.strategy: str = ""  # starts empty (tabula rasa)
        self.game_history: list[dict] = []  # win/loss record for context

        # Logging — each run gets its own folder
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        if subdir:
            model_dir_name = subdir
        else:
            model_dir_name = model.replace("/", "_")
            if multimodal:
                model_dir_name += "-multimodal"
        self.log_dir = _project_root / "evolution_logs" / game / model_dir_name / self.run_id
        self.log_dir.mkdir(parents=True, exist_ok=True)

    # ── LLM Call ──────────────────────────────────────────────────

    MAX_RETRIES = 20
    TIMEOUT = 120

    def _call_llm(self, messages: list[dict], purpose: str = "unknown", max_tokens: int | None = None) -> tuple:
        """Call LLM via direct HTTP. Max 20 retries, 120s timeout, full logging.

        Uses the reflection model/key/base if purpose == "reflection", otherwise play model.
        """
        import json as _json
        import urllib.request

        is_reflection = (purpose == "reflection")
        if is_reflection:
            model_name = self.reflect_model
            api_key = self.reflect_api_key
            api_base = self.reflect_api_base
        else:
            model_name = self.model
            api_key = self.api_key
            api_base = self.api_base

        if model_name.startswith("openai/"):
            model_name = model_name[7:]

        # If no api_base set for the model (e.g. openai), build URL from default
        if not api_base:
            api_base = "https://api.openai.com/v1"

        url = api_base.rstrip("/") + "/chat/completions"
        body = {
            "model": model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if self.no_thinking:
            body["enable_thinking"] = False

        # GPT-5 series models require max_completion_tokens
        if model_name.startswith("gpt-5") or model_name.startswith("o1") or model_name.startswith("o3"):
            body["max_completion_tokens"] = body.pop("max_tokens")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        attempt = 0
        while attempt < self.MAX_RETRIES:
            try:
                req = urllib.request.Request(
                    url, data=_json.dumps(body).encode(), headers=headers
                )
                resp = urllib.request.urlopen(req, timeout=self.TIMEOUT)
                result = _json.loads(resp.read())

                msg = result["choices"][0]["message"]
                content = msg.get("content", "") or ""
                reasoning = msg.get("reasoning_content", "") or ""
                usage = result.get("usage", {})

                # Log success
                self._log_api_call({
                    "status": "success",
                    "purpose": purpose,
                    "attempt": attempt + 1,
                    "input": messages,
                    "output_content": content,
                    "output_reasoning": reasoning,
                    "usage": usage,
                })

                # Strip thinking tags
                if "</think>" in content:
                    content = content.split("</think>")[-1]

                return content.strip(), reasoning, usage

            except Exception as e:
                attempt += 1
                wait = min(2 ** attempt, 60)
                print(f"  [LLM] Error (attempt {attempt}/{self.MAX_RETRIES}): {e} — retrying in {wait}s")

                # Log failure
                self._log_api_call({
                    "status": "error",
                    "purpose": purpose,
                    "attempt": attempt,
                    "input": messages,
                    "error": str(e),
                })

                if attempt >= self.MAX_RETRIES:
                    raise RuntimeError(f"API call failed after {self.MAX_RETRIES} retries: {e}")
                time.sleep(wait)

    def _init_episode_log(self, episode: int):
        """Create a per-episode API call log file."""
        log_path = self.log_dir / f"api_calls_ep{episode:03d}.jsonl"
        self._episode_log_file = open(log_path, "a", encoding="utf-8")

    def _close_episode_log(self):
        """Close the per-episode log file."""
        if hasattr(self, "_episode_log_file") and self._episode_log_file:
            self._episode_log_file.close()
            self._episode_log_file = None

    def _log_api_call(self, entry: dict):
        """Write an API call log entry to the current episode's log file."""
        if not hasattr(self, "_episode_log_file") or not self._episode_log_file:
            return
        entry["timestamp"] = datetime.now().isoformat()
        entry["model"] = self.model
        self._episode_log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._episode_log_file.flush()

    # ── Game Interaction ──────────────────────────────────────────

    def _reset_game(self) -> dict:
        """Reset the game and get initial state."""
        player_name = self.model + "-evo"
        res = requests.get(
            f"{self.backend_url}/api/game/{self.game}/reset",
            params={"difficulty": "hard", "player_name": player_name},
        )
        return res.json()

    def _get_rules(self) -> str:
        res = requests.get(f"{self.backend_url}/api/game/{self.game}/rules")
        return res.json().get("rules", "")

    def _apply_action(self, action: str, session_id: str) -> dict:
        res = requests.get(
            f"{self.backend_url}/api/game/{self.game}/action",
            params={
                "move": action,
                "session_id": session_id,
                "auto_bot": "true",
                "player_name": self.model + "-evo",
            },
        )
        return res.json()

    def _apply_action_split(
        self, action: str, session_id: str, board_before: list
    ) -> tuple[list, dict]:
        """Apply one turn and return (board_after_self_move, final_state).

        For games whose apply_action chains human+bot together (e.g. fourinarow),
        we simulate the self-move on board_before to get the intermediate board.
        For games that expose /bot_move separately (bot_pending=True), we use that.
        """
        res = requests.get(
            f"{self.backend_url}/api/game/{self.game}/action",
            params={
                "move": action,
                "session_id": session_id,
                "auto_bot": "false",
                "player_name": self.model + "-evo",
            },
        )
        state = res.json()

        # Two-phase path (othello6, tictactoe set bot_pending=True)
        if state.get("bot_pending") and not state.get("game_over"):
            board_after_self = state.get("board", [])
            res_bot = requests.get(
                f"{self.backend_url}/api/game/{self.game}/bot_move",
                params={"session_id": session_id, "player_name": self.model + "-evo"},
            )
            return board_after_self, res_bot.json()

        # Single-phase path — apply_action already played the bot too (fourinarow).
        # Simulate own move on board_before so we can still show the intermediate board.
        board_after_self = self._simulate_own_move(board_before, action)
        return board_after_self, state

    def _simulate_own_move(self, board_before: list, action: str) -> list:
        """Return the board as it would look after ONLY our own move.

        Game-specific. Currently implemented for fourinarow. For other games,
        falls back to the pre-move board (we won't render an intermediate step).
        """
        if self.game == "fourinarow":
            try:
                col = int(action)
            except Exception:
                return [row[:] for row in board_before]
            new_board = [row[:] for row in board_before]
            for r in range(len(new_board) - 1, -1, -1):
                if new_board[r][col] == 0:
                    new_board[r][col] = 1
                    return new_board
            return new_board
        return [row[:] for row in board_before]

    @staticmethod
    def _derive_opponent_action(before: list, after: list) -> str:
        """Find the cell that changed from 0 to 2 (for fourinarow-style games)."""
        if not before or not after:
            return "?"
        try:
            for r in range(len(before)):
                for c in range(len(before[0])):
                    if before[r][c] == 0 and after[r][c] == 2:
                        return str(c)
        except Exception:
            pass
        return "?"

    def _get_state(self, session_id: str) -> dict:
        res = requests.get(
            f"{self.backend_url}/api/game/{self.game}/state",
            params={"session_id": session_id},
        )
        return res.json()

    # ── Prompt Building ───────────────────────────────────────────

    def _inject_strategy_into_rules(self, rules: str) -> str:
        """Inject current strategy into the rules text so VanillaReasoning includes it."""
        if not self.strategy:
            return rules
        return rules + (
            "\n\nYOUR STRATEGIC KNOWLEDGE (learned from previous games):\n"
            + self.strategy
        )

    def _build_play_prompt(self, state: dict, rules: str, valid_actions: list[str]) -> list[dict]:
        """Play-phase prompt. Preserves the original vanilla prompt (rules, board,
        state JSON, valid actions list, final instruction) and appends CEL-style
        structured reasoning instructions requiring <reason>...</reason><answer>...</answer> output.
        """
        game_name = self.game
        board = state.get("board", [])
        score = state.get("score", 0)
        actions_str = ', '.join(valid_actions)

        rules_section = f"\n\nGAME RULES:\n{rules}\n" if rules else ""

        # Board formatting (same as vanilla_reasoning)
        if isinstance(board, list) and len(board) > 0 and isinstance(board[0], list):
            board_str = "\n".join(" ".join(str(cell) for cell in row) for row in board)
        elif isinstance(board, list):
            board_str = " ".join(str(cell) for cell in board)
        else:
            board_str = str(board)

        # Game-specific extras (same as vanilla_reasoning)
        extra_context = ""
        if game_name == "mergefall":
            extra_context = f"\nNext tile to drop: {state.get('next_tile', '?')}\n"

        if game_name == "fourinarow":
            board_label = "Current board (1=you, 2=opponent, 0=empty):"
        else:
            board_label = "Current board:"

        # Strategy injection
        strategy_section = ""
        if self.strategy:
            strategy_section = (
                f"\n\nYOUR STRATEGIC KNOWLEDGE (learned from previous games):\n"
                f"{self.strategy}\n"
            )

        # ── Original vanilla body + CEL-style structured reasoning ──
        system = (
            "You are a game-playing AI agent. Reason step by step about the best "
            "move, then output your decision in the required structured format."
        )

        user = f"""You are playing the game "{game_name}".{rules_section}
{strategy_section}
{board_label}
{board_str}
{extra_context}
IMPORTANT: You MUST choose exactly one action from this list (copy it exactly):
[{actions_str}]

**Instructions:**
1. **Analyze State:** Summarize the current state.
2. **Predict Long-term Value of Outcomes (Value Function Evaluation):** Evaluate the strategic value and potential of the current state for the future.
3. **Predict Immediate Consequences (World Model Simulation):** For top 2 candidate actions, predict their consequences using a "result-because" structure.
4. **Select the Best Action:** Based on the predicted consequences, choose the action that leads to the most advantageous future state.

Your response must strictly follow the format below:

<reason>
**1. Analysis of the Current State:**
[Summary of the board state.]

**2. Prediction of the Value of Current States:**
[Provide an assessment of the current state's strategic value.]
- **Value:** High value. Securing guaranteed points creates a dominant position for winning.

**3. Prediction of Immediate Consequences:**
[Analyze ONLY the top 2 candidate actions using the "result-because" structure.]
- **Action A:** ...
- **Action B:** ...
</reason>
<answer>YOUR_CHOSEN_ACTION</answer>

Pick the best action. YOUR_CHOSEN_ACTION inside <answer> must be EXACTLY one of the valid actions listed above (copy it exactly)."""

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _parse_play_response(self, raw: str, valid_actions: list[str]) -> tuple:
        """Extract action from <answer>...</answer> / Answer: / raw. Returns (action, fallback)."""
        import re
        # Try <answer>...</answer>
        m = re.search(r"<answer>(.*?)</answer>", raw, re.DOTALL | re.IGNORECASE)
        if m:
            action = m.group(1).strip()
        elif "Answer:" in raw:
            action = raw.rsplit("Answer:", 1)[-1].strip()
        elif "answer:" in raw:
            action = raw.rsplit("answer:", 1)[-1].strip()
        else:
            action = raw.strip()

        # Clean up: take first line, strip punctuation
        action = action.split("\n")[0].strip().strip(".,;:!?\"'() ")
        return action, (action not in valid_actions)

    def _build_reflection_prompt(self, trajectory: list[dict], result: str, episode: int, rules: str = "") -> list[dict]:
        """Build the prompt for post-game reflection.

        The LLM should output an UPDATED version of its overall strategy document,
        not just a summary of this game. The strategy should evolve — keep what works,
        revise what doesn't, add new insights.

        Includes the game rules (same as vanilla_reasoning play prompt) to anchor
        the reflection in the actual game's mechanics rather than abstract notions.
        """
        # Format trajectory — each step belongs to one actor (self or opponent)
        traj_text = ""
        for step in trajectory:
            actor = step.get("actor")
            if actor == "self":
                label = f"Your move: {step['action']}"
            elif actor == "opponent":
                label = f"Opponent's move: {step['action']}"
            else:
                # Backward compat with un-labeled trajectories
                label = f"Action={step['action']}"
            traj_text += f"Step {step['step']} [{label}]  Board after this move:\n"
            board = step.get("board", [])
            traj_text += "\n".join(" ".join(str(c) for c in row) for row in board) + "\n\n"

        # Game rules section — anchor the reflection in actual game mechanics
        rules_section = ""
        if rules:
            rules_section = f"GAME RULES:\n{rules}\n\n"

        # Game history summary
        history_text = ""
        if self.game_history:
            recent = self.game_history[-10:]  # last 10 games
            wins = sum(1 for g in recent if g["result"] == "WIN")
            losses = sum(1 for g in recent if g["result"] == "LOSE")
            draws = sum(1 for g in recent if g["result"] == "DRAW")
            history_text = f"Recent record (last {len(recent)} games): {wins}W / {losses}L / {draws}D\n\n"

        # Current strategy
        current_strategy = ""
        if self.strategy:
            current_strategy = (
                f"YOUR CURRENT STRATEGY DOCUMENT:\n"
                f"---\n{self.strategy}\n---\n\n"
            )
        else:
            current_strategy = "YOUR CURRENT STRATEGY DOCUMENT:\n(empty — this is your first game)\n\n"

        if self.reflect_prompt_style == "cel":
            # CEL-style: structured <rule><game_rules>...<strategic>...</strategic></rule>
            system = (
                f"You are a chief scientific strategist and master tactician for the game \"{self.game}\". "
                f"Your mission is to analyze field data from game trajectories to distill and refine "
                f"the **Master Rulebook** of this game.\n\n"
                f"You will be presented with the current game trajectory (and your accumulated prior "
                f"knowledge from previous games). Your primary task is to perform a deep, comparative "
                f"analysis to understand the fundamental principles of victory and defeat. You must act "
                f"as a grand strategist, looking for universal patterns and high-level causal relationships. "
                f"Your goal is to synthesize these insights to produce the next generation's Master Rulebook, "
                f"making it more robust, accurate, and effective.\n\n"
                f"[Core Principles]\n"
                f"- **Think Long-Term:** Focus on universal, strategic truths that are consistently validated "
                f"across many diverse scenarios. Ignore circumstantial flukes.\n"
                f"- **Learn from Contrast:** The most critical insights come from identifying the key strategic "
                f"differences that separate winners from losers.\n"
                f"- **Synthesize and Consolidate:** Your output must be a single, unified, and improved Master "
                f"Rulebook. Do not simply copy rules; forge a more perfect theory from all available evidence.\n"
                f"- **Be Authoritative and Concise:** Your rules should be stated as clear, definitive principles.\n"
                f"- **Ground in Game Mechanics:** All rules must reference concrete elements of \"{self.game}\" "
                f"(pieces, board layout, winning conditions). Avoid abstract terminology that doesn't belong to this game.\n\n"
                f"**Your output MUST be a single, consolidated `<rule>` block representing the new Master Rulebook.**"
            )
            user = (
                f"You are playing the game \"{self.game}\".\n\n"
                f"{rules_section}"
                f"A game just ended. Result: {result}\n\n"
                f"{history_text}"
                f"{current_strategy}"
                f"GAME TRAJECTORY (human vs bot moves, each step shows board after that move):\n{traj_text}\n"
                f"Based on the official game rules, your current Master Rulebook (if any), and this game's trajectory, "
                f"produce an UPDATED Master Rulebook. Use the exact format below — nothing outside the <rule>...</rule> block:\n\n"
                f"<rule>\n"
                f"<game_rules>\n"
                f"**1. Symbol Meanings:** [Define the unchanging, intrinsic properties of game elements.]\n"
                f"**2. Information & Interpretation:** [Define how elements reliably inform about the game state.]\n"
                f"**3. Gameplay & Actions:** [Define the core mechanics and interactions.]\n"
                f"**4. Action Effects:** [Describe the predictable outcomes of actions.]\n"
                f"**5. Game Objective & Termination:** [State the ultimate win/loss conditions.]\n"
                f"</game_rules>\n"
                f"<strategic>\n"
                f"**1. Core Strategies:** [Describe foundational, high-level strategic priorities that lead to victory.]\n"
                f"**2. Tactical Tips:** [List widely applicable, advantageous situational plays.]\n"
                f"</strategic>\n"
                f"</rule>"
            )
        else:
            # Simple style: plain numbered rule list
            system = (
                f"You are playing the game \"{self.game}\" and maintaining a compact list "
                f"of strategic rules specific to this game. "
                f"The rules must be actionable principles grounded in the game's actual mechanics "
                f"(pieces, board size, winning conditions, movement rules) — "
                f"NOT abstract strategic concepts that don't reference concrete game elements."
            )
            user = (
                f"You are playing the game \"{self.game}\".\n\n"
                f"{rules_section}"
                f"A game just ended. Result: {result}\n\n"
                f"{history_text}"
                f"{current_strategy}"
                f"GAME TRAJECTORY (human vs bot moves, each step shows board after that move):\n{traj_text}\n"
                f"Produce an UPDATED rule list. Requirements:\n"
                f"- Output ONLY a numbered list of rules (no headings, no preamble, no game analysis).\n"
                f"- Each rule is ONE sentence, imperative form (e.g., 'Block opponent's 3-in-a-row immediately.').\n"
                f"- Rules must be SPECIFIC to this game's mechanics — reference concrete elements "
                f"(columns, rows, pieces, sizes) from the rules above.\n"
                f"- If a rule from the current list is still valid, keep it (optionally reword for clarity).\n"
                f"- If a new insight emerged from this game, add a rule.\n"
                f"- If an old rule is wrong, redundant, or uses terminology that doesn't match this game, remove it.\n"
            )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    # ── Single Episode ────────────────────────────────────────────

    def play_episode(self, episode: int, rules: str) -> dict:
        """Play one complete game episode."""
        print(f"\n{'='*50}")
        print(f"  Episode {episode}")
        print(f"  Strategy length: {len(self.strategy)} chars, Games played: {len(self.game_history)}")
        print(f"{'='*50}")

        # Init per-episode API call log
        self._init_episode_log(episode)

        # Also set the shared api_logger for VanillaReasoning calls
        from agent.llm import api_logger
        api_logger.set_log_file(self.log_dir / f"api_calls_ep{episode:03d}.jsonl")

        # Reset game
        state = self._reset_game()
        session_id = state.get("session_id", "")
        trajectory = []
        step = 0

        MAX_INVALID_RETRIES = 20
        augmented_rules = self._inject_strategy_into_rules(rules)

        while not state.get("game_over", False):
            valid_actions = state.get("valid_actions", [])
            if not valid_actions:
                break

            raw_response = ""
            action = ""
            fallback = False
            reasoning_content = ""
            total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

            if self.play_prompt_style == "cel":
                # CEL-style: structured <reason>/<answer> format, evolution-owned LLM call
                messages = self._build_play_prompt(state, rules, valid_actions)

                for invalid_attempt in range(MAX_INVALID_RETRIES):
                    raw_response, reasoning_content, usage = self._call_llm(messages, purpose="play")
                    total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                    total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

                    action, is_invalid = self._parse_play_response(raw_response, valid_actions)
                    if not is_invalid:
                        break
                    print(f"  Step {step+1}: Invalid '{action}' (retry {invalid_attempt+1}/{MAX_INVALID_RETRIES})")
                    self._log_api_call({
                        "status": "invalid_output",
                        "purpose": "play",
                        "attempt": invalid_attempt + 1,
                        "parsed_action": action,
                        "valid_actions": valid_actions,
                        "raw_response": raw_response,
                    })

                if action not in valid_actions:
                    action = valid_actions[0]
                    fallback = True
                    print(f"  Step {step+1}: Exhausted retries, fallback to '{action}'")
                    self._log_api_call({
                        "status": "fallback",
                        "purpose": "play",
                        "parsed_action": action,
                        "valid_actions": valid_actions,
                        "note": f"Exhausted {MAX_INVALID_RETRIES} retries, using first valid action",
                    })
            else:
                # Simple style: delegate to VanillaReasoning (identical to normal agent)
                action = self.reasoning.reason(state, valid_actions, augmented_rules)
                raw_response = getattr(self.reasoning, "last_raw_response", "")
                fallback = getattr(self.reasoning, "last_fallback", False)
                llm = getattr(self.reasoning, "llm", None)
                reasoning_content = getattr(llm, "last_reasoning", "") if llm else ""
                usage = getattr(self.reasoning, "last_usage", {})
                total_usage = {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                }
                if fallback:
                    print(f"  Step {step+1}: Invalid '{raw_response}', fallback to '{action}'")

            # Apply own move + bot move, capturing both boards separately
            board_before = state.get("board", [])
            board_after_self, new_state = self._apply_action_split(
                action, session_id, board_before
            )
            board_after_opp = new_state.get("board", [])

            # Own move step
            step += 1
            trajectory.append({
                "step": step,
                "actor": "self",
                "action": action,
                "fallback": fallback,
                "raw_response": raw_response,
                "reasoning": reasoning_content,
                "board": board_after_self,
                "score": 0,
                "game_over": board_after_self == board_after_opp and new_state.get("game_over", False),
                "input_tokens": total_usage["prompt_tokens"],
                "output_tokens": total_usage["completion_tokens"],
            })

            # Opponent move step (only if the bot actually moved)
            bot_played = board_after_self != board_after_opp
            if bot_played:
                opp_action = self._derive_opponent_action(board_after_self, board_after_opp)
                step += 1
                trajectory.append({
                    "step": step,
                    "actor": "opponent",
                    "action": opp_action,
                    "fallback": False,
                    "raw_response": "",
                    "reasoning": "",
                    "board": board_after_opp,
                    "score": new_state.get("score", 0),
                    "game_over": new_state.get("game_over", False),
                    "input_tokens": 0,
                    "output_tokens": 0,
                })

            state = new_state
            print(f"  Turn {step}: self='{action}' "
                  f"{'opp=' + opp_action if bot_played else '(own move ended game)'} "
                  f"score={state.get('score', 0)} game_over={state.get('game_over', False)}")

        # Determine result
        score = state.get("score", "")
        if score in ("human_win",):
            result = "WIN"
        elif score in ("bot_win",):
            result = "LOSE"
        elif score in ("draw",):
            result = "DRAW"
        else:
            result = f"score={score}"

        own_moves = sum(1 for s in trajectory if s.get("actor") == "self")
        print(f"\n  Result: {result} in {own_moves} own moves ({len(trajectory)} total steps)")

        return {
            "episode": episode,
            "result": result,
            "score": score,
            "steps": own_moves,
            "trajectory": trajectory,
            "session_id": session_id,
        }

    def reflect(self, episode_data: dict, episode: int, rules: str = "") -> str:
        """Post-game reflection — update the strategy document."""
        print(f"  Reflecting on episode {episode}...")

        messages = self._build_reflection_prompt(
            episode_data["trajectory"],
            episode_data["result"],
            episode,
            rules=rules,
        )
        new_strategy, reasoning, _usage = self._call_llm(messages, purpose="reflection", max_tokens=8192)

        # Update strategy
        old_strategy = self.strategy
        self.strategy = new_strategy

        # Track game history
        self.game_history.append({
            "episode": episode,
            "result": episode_data["result"],
            "steps": episode_data["steps"],
        })

        print(f"  Strategy updated ({len(new_strategy)} chars):")
        preview = new_strategy[:200].replace("\n", " ")
        print(f"    {preview}...")

        # Close per-episode log
        self._close_episode_log()

        return new_strategy, old_strategy, reasoning

    # ── Main Loop ─────────────────────────────────────────────────

    def run(self, num_episodes: int = 30, delay: float = 1.0):
        """Run the full evolution experiment."""
        print(f"{'#'*60}")
        print(f"  Evolution Experiment")
        print(f"  Game: {self.game}")
        print(f"  Model: {self.model}")
        print(f"  Episodes: {num_episodes}")
        print(f"  Thinking: {'off' if self.no_thinking else 'on'}")
        print(f"  Log dir: {self.log_dir}")
        print(f"{'#'*60}")

        rules = self._get_rules()

        # Episode log
        episode_log_path = self.log_dir / f"episodes.jsonl"
        experience_log_path = self.log_dir / f"experience.jsonl"
        summary_path = self.log_dir / f"summary.csv"

        summary_rows = []

        for ep in range(1, num_episodes + 1):
            # Play
            ep_data = self.play_episode(ep, rules)

            # Reflect — update strategy document
            new_strategy, old_strategy, reflection_reasoning = self.reflect(ep_data, ep, rules=rules)

            # Log episode
            with open(episode_log_path, "a", encoding="utf-8") as f:
                log_entry = {
                    "episode": ep,
                    "result": ep_data["result"],
                    "score": ep_data["score"],
                    "steps": ep_data["steps"],
                    "session_id": ep_data["session_id"],
                    "trajectory": ep_data["trajectory"],
                    "strategy_before": old_strategy,
                    "strategy_after": new_strategy,
                    "reflection_reasoning": reflection_reasoning,
                    "timestamp": datetime.now().isoformat(),
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            # Log strategy evolution
            with open(experience_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "episode": ep,
                    "result": ep_data["result"],
                    "strategy": new_strategy,
                    "strategy_length": len(new_strategy),
                }, ensure_ascii=False) + "\n")

            # Summary row
            total_input = sum(s["input_tokens"] for s in ep_data["trajectory"])
            total_output = sum(s["output_tokens"] for s in ep_data["trajectory"])
            fallbacks = sum(1 for s in ep_data["trajectory"] if s["fallback"])

            summary_rows.append({
                "episode": ep,
                "result": ep_data["result"],
                "steps": ep_data["steps"],
                "fallbacks": fallbacks,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "strategy_length": len(self.strategy),
            })

            # Write summary CSV
            with open(summary_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
                writer.writeheader()
                writer.writerows(summary_rows)

            print(f"  Logged to {episode_log_path.name}")

            if delay > 0:
                time.sleep(delay)

        # Final summary
        print(f"\n{'#'*60}")
        print(f"  EXPERIMENT COMPLETE — {num_episodes} episodes")
        print(f"{'#'*60}")
        wins = sum(1 for r in summary_rows if r["result"] == "WIN")
        losses = sum(1 for r in summary_rows if r["result"] == "LOSE")
        draws = sum(1 for r in summary_rows if r["result"] == "DRAW")
        print(f"  Results: {wins}W / {losses}L / {draws}D")
        print(f"  Logs: {self.log_dir}")


def main():
    parser = argparse.ArgumentParser(description="Evolution Agent — self-play with reflection")
    parser.add_argument("--game", default="fourinarow", help="Game name")
    parser.add_argument("--model", default="openai/Qwen/Qwen3.5-9B", help="Model name")
    parser.add_argument("--api-key", required=True, help="API key")
    parser.add_argument("--api-base", required=True, help="API base URL")
    parser.add_argument("--backend-url", default="http://localhost:5001")
    parser.add_argument("--episodes", type=int, default=30, help="Number of episodes")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--no-thinking", action="store_true")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--temperature", type=float, default=0.7)
    # Optional: separate model for reflection phase
    parser.add_argument("--reflect-model", help="Model to use for reflection (default: same as --model)")
    parser.add_argument("--reflect-api-key", help="API key for reflection model")
    parser.add_argument("--reflect-api-base", help="API base URL for reflection model (leave unset for OpenAI)")
    parser.add_argument("--multimodal", action="store_true", help="Use multimodal mode (send board as image)")
    parser.add_argument("--play-prompt", choices=["simple", "cel"], default="simple",
                        help="Play-phase prompt style: 'simple' (vanilla) or 'cel' (structured <reason>/<answer>)")
    parser.add_argument("--reflect-prompt", choices=["simple", "cel"], default="simple",
                        help="Reflection prompt style: 'simple' (rule list) or 'cel' (Master Rulebook)")
    parser.add_argument("--subdir", help="Override the log subdirectory name under evolution_logs/<game>/")
    args = parser.parse_args()

    agent = EvolutionAgent(
        game=args.game,
        model=args.model,
        api_key=args.api_key,
        api_base=args.api_base,
        backend_url=args.backend_url,
        max_tokens=args.max_tokens,
        no_thinking=args.no_thinking,
        temperature=args.temperature,
        reflect_model=args.reflect_model,
        reflect_api_key=args.reflect_api_key,
        reflect_api_base=args.reflect_api_base,
        multimodal=args.multimodal,
        play_prompt_style=args.play_prompt,
        reflect_prompt_style=args.reflect_prompt,
        subdir=args.subdir,
    )
    agent.run(num_episodes=args.episodes, delay=args.delay)


if __name__ == "__main__":
    main()
