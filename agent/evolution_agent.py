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

    def _build_reflection_prompt(self, trajectory: list[dict], result: str, episode: int, rules: str = "") -> list[dict]:
        """Build the prompt for post-game reflection.

        The LLM should output an UPDATED version of its overall strategy document,
        not just a summary of this game. The strategy should evolve — keep what works,
        revise what doesn't, add new insights.

        Includes the game rules (same as vanilla_reasoning play prompt) to anchor
        the reflection in the actual game's mechanics rather than abstract notions.
        """
        # Format trajectory
        traj_text = ""
        for step in trajectory:
            traj_text += f"Step {step['step']}: Action={step['action']}, Board after:\n"
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

        # Inject strategy into rules for VanillaReasoning
        augmented_rules = self._inject_strategy_into_rules(rules)

        while not state.get("game_over", False):
            valid_actions = state.get("valid_actions", [])
            if not valid_actions:
                break

            # Use VanillaReasoning (identical prompt to vanilla agent)
            action = self.reasoning.reason(state, valid_actions, augmented_rules)

            # Get logging info from reasoning
            raw_response = getattr(self.reasoning, "last_raw_response", "")
            fallback = getattr(self.reasoning, "last_fallback", False)
            llm = getattr(self.reasoning, "llm", None)
            reasoning_content = getattr(llm, "last_reasoning", "") if llm else ""
            usage = getattr(self.reasoning, "last_usage", {})

            if fallback:
                print(f"  Step {step+1}: Invalid '{raw_response}', fallback to '{action}'")

            # Apply action
            new_state = self._apply_action(action, session_id)
            step += 1

            trajectory.append({
                "step": step,
                "action": action,
                "fallback": fallback,
                "raw_response": raw_response,
                "reasoning": reasoning_content,
                "board": new_state.get("board", []),
                "score": new_state.get("score", 0),
                "game_over": new_state.get("game_over", False),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            })

            state = new_state
            print(f"  Step {step}: action='{action}' score={state.get('score', 0)} "
                  f"game_over={state.get('game_over', False)}")

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

        print(f"\n  Result: {result} in {step} steps")

        return {
            "episode": episode,
            "result": result,
            "score": score,
            "steps": step,
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
    )
    agent.run(num_episodes=args.episodes, delay=args.delay)


if __name__ == "__main__":
    main()
