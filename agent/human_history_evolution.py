"""Human-history evolution — LLM plays, watches a human game, reflects, plays again.

Flow:
  Episode k (1 ≤ k ≤ N):
    - LLM plays a game with the current strategy
    - LLM watches human CSV k and reflects → updates strategy
  Episode N+1:
    - LLM plays one more game with the final strategy (no reflection)

Total: (N + 1) episodes, N reflections (each reading one human CSV). LLM never
reflects on its own games, so it never sees its own past play.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from agent.evolution_agent import EvolutionAgent


def _parse_board(raw: str) -> list:
    return ast.literal_eval(raw)


def load_human_session(csv_path: Path) -> tuple[list[dict], str, str]:
    """Convert one human CSV into (trajectory, result, first_timestamp).

    Each CSV row (one actor's move) becomes its own trajectory step, labeled
    with actor="self" for human moves and actor="opponent" for bot moves.
    Board is the post-move board of that same row.
    """
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return [], "UNKNOWN", ""

    first_ts = rows[0]["timestamp"]

    trajectory = []
    step_counter = 0
    for row in rows:
        actor_raw, _, action_val = row["action"].partition(":")
        if actor_raw == "human":
            traj_actor = "self"
        elif actor_raw == "bot":
            traj_actor = "opponent"
        else:
            # "wall" or other non-move rows — skip
            continue

        step_counter += 1
        trajectory.append({
            "step": step_counter,
            "actor": traj_actor,
            "action": action_val.strip(),
            "fallback": False,
            "raw_response": "",
            "reasoning": "",
            "board": _parse_board(row["board"]),
            "score": row["score"],
            "game_over": row["game_over"].strip().lower() == "true",
            "input_tokens": 0,
            "output_tokens": 0,
        })

    final_score = rows[-1]["score"]
    if final_score == "human_win":
        result = "WIN"
    elif final_score == "bot_win":
        result = "LOSE"
    elif final_score == "draw":
        result = "DRAW"
    else:
        result = f"score={final_score}"

    return trajectory, result, first_ts


def discover_human_sessions(game: str, human: str) -> list[Path]:
    base = _project_root / "human_data" / game / human
    if not base.exists():
        raise FileNotFoundError(f"No human_data at {base}")

    files = sorted(base.glob("*.csv"))
    dated = []
    for p in files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                first_row = next(reader, None)
            ts = first_row["timestamp"] if first_row else ""
        except Exception:
            ts = ""
        dated.append((ts, p))
    dated.sort(key=lambda x: x[0])
    return [p for _, p in dated]


def _write_summary(summary_path, summary_rows):
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)


def main():
    parser = argparse.ArgumentParser(description="Interleave LLM play with reflection on human games")
    parser.add_argument("--game", default="fourinarow")
    parser.add_argument("--human", required=True, help="Subfolder under human_data/<game>/ (e.g. Yuzu)")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--backend-url", default="http://localhost:5001")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--no-thinking", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--play-prompt", choices=["simple", "cel"], default="cel")
    parser.add_argument("--reflect-prompt", choices=["simple", "cel"], default="cel")
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
        play_prompt_style=args.play_prompt,
        reflect_prompt_style=args.reflect_prompt,
    )
    model_dir = args.model.replace("/", "_") + f"-human-{args.human}"
    agent.log_dir = _project_root / "evolution_logs" / args.game / model_dir / agent.run_id
    agent.log_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'#'*60}")
    print(f"  Human-history Evolution (interleave)")
    print(f"  Game: {args.game}  |  Human: {args.human}  |  Model: {args.model}")
    print(f"  Play prompt: {args.play_prompt}  |  Reflect prompt: {args.reflect_prompt}")
    print(f"  Log dir: {agent.log_dir}")
    print(f"{'#'*60}")

    rules = agent._get_rules()

    csvs = discover_human_sessions(args.game, args.human)
    print(f"Found {len(csvs)} human sessions for {args.human}")
    for p in csvs:
        print(f"  - {p.name}")

    episode_log_path = agent.log_dir / "episodes.jsonl"
    experience_log_path = agent.log_dir / "experience.jsonl"
    summary_path = agent.log_dir / "summary.csv"
    summary_rows = []

    from agent.llm import api_logger

    # Valid human trajectories (skip any empty files)
    human_games = []
    for p in csvs:
        traj, res, first_ts = load_human_session(p)
        if traj:
            human_games.append((p, traj, res, first_ts))
        else:
            print(f"[skip] {p.name}: empty")

    total_episodes = len(human_games) + 1

    for ep in range(1, total_episodes + 1):
        is_last = (ep == total_episodes)
        print(f"\n{'='*60}\n  Episode {ep}/{total_episodes}\n{'='*60}")

        # ── LLM plays ──
        agent._init_episode_log(ep)
        api_logger.set_log_file(agent.log_dir / f"api_calls_ep{ep:03d}.jsonl")
        ep_data = agent.play_episode(ep, rules)

        llm_trajectory = ep_data["trajectory"]
        llm_result = ep_data["result"]
        llm_steps = ep_data["steps"]
        total_input = sum(s["input_tokens"] for s in llm_trajectory)
        total_output = sum(s["output_tokens"] for s in llm_trajectory)
        fallbacks = sum(1 for s in llm_trajectory if s["fallback"])

        # ── Reflect on the next human game (if any) ──
        if not is_last:
            csv_path, h_traj, h_result, h_ts = human_games[ep - 1]
            print(f"\n  Watching human game {ep}/{len(human_games)}: {csv_path.name} ({h_result}, {sum(1 for s in h_traj if s.get('actor')=='self')} human moves)")

            own_moves = sum(1 for s in h_traj if s.get("actor") == "self")
            human_ep_data = {
                "episode": ep,
                "result": h_result,
                "score": f"human_source:{csv_path.name}",
                "steps": own_moves,
                "trajectory": h_traj,
                "session_id": csv_path.stem,
            }
            new_strategy, old_strategy, reflection_reasoning = agent.reflect(
                human_ep_data, ep, rules=rules
            )
            human_csv_name = csv_path.name
            human_result = h_result
        else:
            agent._close_episode_log()  # no reflect => close manually
            new_strategy = agent.strategy
            old_strategy = agent.strategy
            reflection_reasoning = ""
            h_traj = []
            human_csv_name = None
            human_result = None

        # ── Write combined episode log ──
        with open(episode_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "episode": ep,
                "llm": {
                    "result": llm_result,
                    "score": ep_data["score"],
                    "steps": llm_steps,
                    "session_id": ep_data["session_id"],
                    "trajectory": llm_trajectory,
                },
                "human": {
                    "csv_file": human_csv_name,
                    "result": human_result,
                    "trajectory": h_traj,
                } if not is_last else None,
                "strategy_before": old_strategy,
                "strategy_after": new_strategy,
                "reflection_reasoning": reflection_reasoning,
                "reflected": not is_last,
                "timestamp": datetime.now().isoformat(),
            }, ensure_ascii=False) + "\n")

        with open(experience_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "episode": ep,
                "llm_result": llm_result,
                "human_csv": human_csv_name,
                "human_result": human_result,
                "reflected": not is_last,
                "strategy": new_strategy,
                "strategy_length": len(new_strategy),
            }, ensure_ascii=False) + "\n")

        summary_rows.append({
            "episode": ep,
            "llm_result": llm_result,
            "llm_steps": llm_steps,
            "fallbacks": fallbacks,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "reflected_on": human_csv_name or "",
            "human_result": human_result or "",
            "strategy_length": len(new_strategy),
        })
        _write_summary(summary_path, summary_rows)

    # ── Tally ──
    wins = sum(1 for r in summary_rows if r["llm_result"] == "WIN")
    losses = sum(1 for r in summary_rows if r["llm_result"] == "LOSE")
    draws = sum(1 for r in summary_rows if r["llm_result"] == "DRAW")
    print(f"\n{'#'*60}")
    print(f"  LLM record: {wins}W / {losses}L / {draws}D across {len(summary_rows)} episodes")
    print(f"  Logs: {agent.log_dir}")
    print(f"{'#'*60}")


if __name__ == "__main__":
    main()
