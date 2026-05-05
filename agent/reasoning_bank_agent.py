"""ReasoningBank agent — EvoPlay port of google-research/reasoning-bank.

Same outer loop as EvolutionAgent (play episode → reflect → repeat) but the
strategy state is replaced by a structured memory bank:
  - After each episode, induce ≤3 memory items via SUCCESSFUL_SI / FAILED_SI
    prompts and append them (with episode metadata) to a JSONL bank.
  - At the start of the next episode, retrieve items filtered by (game, level)
    and inject them into the play prompt as the agent's "strategic knowledge".

No embedding-based retrieval — the EvoPlay benchmark fixes the task per run, so
filter-by-game/level + recency is enough. See docstring of `MemoryBank`.

Usage:
    python agent/reasoning_bank_agent.py \\
        --game fourinarow --model gpt-5.4-nano \\
        --api-key "$OPENAI_API_KEY" --api-base "" \\
        --episodes 30 --play-prompt cel \\
        --bank-path memories/fourinarow.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from agent.evolution_agent import EvolutionAgent
from agent.reasoning_bank import MemoryBank, induce_memory_items


class ReasoningBankAgent(EvolutionAgent):
    """EvolutionAgent with discrete memory items instead of a single strategy doc."""

    def __init__(
        self,
        *args,
        bank_path: str | None = None,
        retrieve_max_items: int | None = None,
        retrieve_recent_episodes: int | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if bank_path is None:
            bank_path = str(self.log_dir / "memory_bank.jsonl")
        self.bank = MemoryBank(bank_path)
        self.retrieve_max_items = retrieve_max_items
        self.retrieve_recent_episodes = retrieve_recent_episodes
        self._current_level: int | str | None = None  # filled per episode
        # Pre-populate strategy from any existing bank entries so the first
        # episode benefits from prior runs against the same JSONL.
        self._refresh_strategy_from_bank()

    # ── Bank-driven strategy injection ──────────────────────────────

    def _refresh_strategy_from_bank(self) -> None:
        items = self.bank.retrieve(
            game=self.game,
            level=self._current_level,
            max_items=self.retrieve_max_items,
            most_recent_episodes=self.retrieve_recent_episodes,
        )
        if items:
            header = (
                f"You have {len(items)} memory items from prior episodes. "
                f"Use them as guidance — they describe what worked or what to avoid."
            )
            self.strategy = header + "\n\n" + MemoryBank.format_for_prompt(items)
        else:
            self.strategy = ""

    def _reset_game(self) -> dict:
        """Hook the parent's reset so we can refresh strategy AFTER seeing the
        new game state (and the current_level it exposes for level-based games).
        Avoids hitting /reset twice per episode."""
        state = super()._reset_game()
        self._current_level = state.get("current_level")
        self._refresh_strategy_from_bank()
        return state

    # ── Replace reflect: induce memory items, append to bank ────────

    def reflect(self, episode_data: dict, episode: int, rules: str = ""):
        """Induce ReasoningBank-style items and append to the bank.

        Returns the same 3-tuple shape as EvolutionAgent.reflect so the
        existing run-loop logging code keeps working.
        """
        print(f"  Inducing memory items for episode {episode}...")

        result = episode_data.get("result", "")
        trajectory = episode_data.get("trajectory", [])
        query = self._build_query(episode_data)

        items, raw = induce_memory_items(
            trajectory=trajectory,
            status=result,
            query=query,
            llm_call=lambda messages, max_tokens=None: self._call_llm(
                messages, purpose="induce_memory", max_tokens=max_tokens or 2048
            ),
        )

        old_strategy = self.strategy

        # Persist to bank with metadata so we can filter later.
        entry = {
            "episode": episode,
            "game": self.game,
            "level": self._current_level,
            "result": result,
            "score": episode_data.get("score"),
            "session_id": episode_data.get("session_id"),
            "query": query,
            "memory_items": items,
            "raw_induction": raw,
            "timestamp": datetime.now().isoformat(),
        }
        self.bank.append(entry)

        # Track played-game stats (mirrors EvolutionAgent.reflect bookkeeping).
        self.game_history.append({
            "episode": episode,
            "result": result,
            "steps": episode_data.get("steps", 0),
        })

        # Refresh strategy doc for log purposes (next episode will refresh again).
        self._refresh_strategy_from_bank()

        if items:
            preview = items[0][:200].replace("\n", " ")
            print(f"  Bank now has {len(self.bank)} items total — first new: {preview}...")
        else:
            print(f"  No memory items extracted for episode {episode} (raw output ignored)")

        # Close the per-episode API call log file (mirrors EvolutionAgent.reflect)
        self._close_episode_log()

        return self.strategy, old_strategy, raw

    # ── Helpers ─────────────────────────────────────────────────────

    def _build_query(self, episode_data: dict) -> str:
        """Build a short task description used by the induce prompt."""
        bits = [f"game={self.game}"]
        if self._current_level is not None:
            bits.append(f"level={self._current_level}")
        bits.append(f"opponent_difficulty=hard")
        return " | ".join(bits)


def main():
    parser = argparse.ArgumentParser(description="ReasoningBank agent (EvoPlay port)")
    parser.add_argument("--game", default="fourinarow")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--backend-url", default="http://localhost:5001")
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--no-thinking", action="store_true")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--play-prompt", choices=["simple", "cel"], default="cel")
    parser.add_argument("--bank-path", help="JSONL memory bank path. Defaults to <log_dir>/memory_bank.jsonl.")
    parser.add_argument("--retrieve-max-items", type=int, default=None,
                        help="Cap total items injected into play prompt (default: no cap)")
    parser.add_argument("--retrieve-recent-episodes", type=int, default=None,
                        help="Only include items from the most-recent N episodes (default: all)")
    parser.add_argument("--subdir", help="Override log subdirectory under evolution_logs/<game>/")
    args = parser.parse_args()

    agent = ReasoningBankAgent(
        game=args.game,
        model=args.model,
        api_key=args.api_key,
        api_base=args.api_base,
        backend_url=args.backend_url,
        max_tokens=args.max_tokens,
        no_thinking=args.no_thinking,
        temperature=args.temperature,
        play_prompt_style=args.play_prompt,
        reflect_prompt_style="simple",  # not used; reflect is overridden
        subdir=args.subdir or f"reasoning-bank-{args.model.replace('/', '_')}",
        bank_path=args.bank_path,
        retrieve_max_items=args.retrieve_max_items,
        retrieve_recent_episodes=args.retrieve_recent_episodes,
    )
    agent.run(num_episodes=args.episodes, delay=args.delay)


if __name__ == "__main__":
    main()
