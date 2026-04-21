#!/usr/bin/env python3
"""View a single game trajectory.

Usage:
    # Normal session (via session_id or partial match)
    python view_game.py --session c8cd1ed6
    python view_game.py --session c8cd1ed6 --game othello6

    # Evolution run (view a specific episode)
    python view_game.py --run 20260419_225446
    python view_game.py --run 20260419_225446 --episode 5
    python view_game.py --run 20260419_225446 --episode 5 --show-reflection

    # Show LLM reasoning at each step
    python view_game.py --session c8cd1ed6 --show-llm
"""

import argparse
import csv
import glob
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_LOGS = PROJECT_ROOT / "backend" / "logs"
LLM_LOGS = PROJECT_ROOT / "backend" / "llm_logs"
EVOLUTION_LOGS = PROJECT_ROOT / "evolution_logs"


# ── Normal session viewer ─────────────────────────────────────────────


def find_session_file(session_query: str, game: str | None = None):
    """Find a game log file matching the session_id (supports partial match)."""
    patterns = []
    if game:
        patterns.append(str(BACKEND_LOGS / game / "**" / f"*{session_query}*.csv"))
    else:
        patterns.append(str(BACKEND_LOGS / "**" / f"*{session_query}*.csv"))

    matches = []
    for p in patterns:
        matches.extend(glob.glob(p, recursive=True))

    # Exclude resume/round files that are pure prefixes, but prefer completed ones
    matches = sorted(set(matches))
    return matches


def view_normal_session(session_query: str, game_filter: str | None, show_llm: bool):
    matches = find_session_file(session_query, game_filter)
    if not matches:
        print(f"No session found matching '{session_query}'"
              + (f" in game {game_filter}" if game_filter else ""))
        return

    if len(matches) > 1:
        print(f"Multiple matches ({len(matches)}):")
        for m in matches:
            print(f"  {m}")
        print("\nShowing first match:")

    game_log = matches[0]
    print(f"=== {game_log} ===\n")

    with open(game_log) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("Empty file.")
        return

    # Header
    first = rows[0]
    last = rows[-1]
    print(f"Game:       {first.get('game', '?')}")
    print(f"Player:     {first.get('player', '?')}")
    print(f"Difficulty: {first.get('difficulty', '?')}")
    print(f"Started:    {first.get('timestamp', '?')}")
    print(f"Ended:      {last.get('timestamp', '?')}")
    print(f"Total rows: {len(rows)}")
    print(f"Final score: {last.get('score', '?')}")
    print(f"Game over:   {last.get('game_over', '?')}")
    print("─" * 80)

    # Load LLM log if requested
    llm_rows = {}
    if show_llm:
        # Session id is filename before _r suffix
        sid = Path(game_log).stem.split("_r")[0]
        game_name = first.get("game", "")
        player = first.get("player", "").replace("/", "_").replace("\\", "_")
        # Try new structure first
        new_llm_path = LLM_LOGS / game_name / player / sid / "llm_responses.csv"
        old_llm_path = LLM_LOGS / game_name / f"{sid}.csv"
        llm_path = new_llm_path if new_llm_path.exists() else old_llm_path
        if llm_path.exists():
            with open(llm_path) as f:
                for lr in csv.DictReader(f):
                    llm_rows[lr["step"]] = lr
            print(f"LLM log: {llm_path.name} ({len(llm_rows)} entries)")
        else:
            print(f"(LLM log not found at {new_llm_path} or {old_llm_path})")
        print("─" * 80)

    # Print each step
    for row in rows:
        step = row.get("step", "?")
        action = row.get("action", "?")
        score = row.get("score", "?")
        board = row.get("board", "")
        print(f"Step {step}: action={action}  score={score}")

        # Pretty-print board
        if board:
            try:
                b = json.loads(board)
                for r in b:
                    print("  " + " ".join(str(c).rjust(4) for c in r))
            except Exception:
                print(f"  {board}")

        # LLM info
        if show_llm and step in llm_rows:
            lr = llm_rows[step]
            print(f"  [LLM] raw=\"{lr.get('raw_response', '')}\" "
                  f"parsed=\"{lr.get('parsed_action', '')}\" "
                  f"fallback={lr.get('fallback', '')} "
                  f"tokens={lr.get('input_tokens', '?')}/{lr.get('output_tokens', '?')}")

        print()


# ── Evolution run viewer ──────────────────────────────────────────────


def find_evolution_run(run_id: str):
    """Find an evolution run directory by run_id (supports partial match)."""
    matches = list(EVOLUTION_LOGS.glob(f"*/*/{run_id}*"))
    matches = [m for m in matches if m.is_dir()]
    return matches


def view_evolution_run(run_id: str, episode: int | None, show_reflection: bool):
    matches = find_evolution_run(run_id)
    if not matches:
        print(f"No evolution run found matching '{run_id}'")
        return

    if len(matches) > 1:
        print(f"Multiple matches ({len(matches)}):")
        for m in matches:
            print(f"  {m}")
        print("\nShowing first match:")

    run_dir = matches[0]
    print(f"=== {run_dir} ===\n")

    # Summary
    summary_path = run_dir / "summary.csv"
    if summary_path.exists():
        with open(summary_path) as f:
            summary_rows = list(csv.DictReader(f))
        wins = sum(1 for r in summary_rows if r["result"] == "WIN")
        losses = sum(1 for r in summary_rows if r["result"] == "LOSE")
        draws = sum(1 for r in summary_rows if r["result"] == "DRAW")
        total = len(summary_rows)
        print(f"Total episodes: {total}  |  {wins}W / {losses}L / {draws}D")
        print("─" * 80)
        for r in summary_rows:
            marker = "→" if episode and int(r["episode"]) == episode else " "
            print(f"{marker} Ep {r['episode']:>2}: {r['result']:<5} "
                  f"steps={r['steps']:>3} fallbacks={r['fallbacks']:>2} "
                  f"tokens={r['input_tokens']}/{r['output_tokens']} "
                  f"strategy_len={r['strategy_length']}")
        print()

    if episode is None:
        print("(Specify --episode N to view a specific game's trajectory.)")
        return

    # Episode detail
    episodes_path = run_dir / "episodes.jsonl"
    if not episodes_path.exists():
        print(f"episodes.jsonl not found in {run_dir}")
        return

    target = None
    with open(episodes_path) as f:
        for line in f:
            ep = json.loads(line)
            if ep["episode"] == episode:
                target = ep
                break

    if not target:
        print(f"Episode {episode} not found.")
        return

    print("═" * 80)
    print(f"  EPISODE {episode} — {target['result']} in {target['steps']} steps")
    print("═" * 80)

    # Strategy before
    if show_reflection:
        print(f"\n── Strategy BEFORE this episode ({len(target.get('strategy_before', ''))} chars) ──")
        print(target.get("strategy_before", "") or "(empty)")
        print()

    # Trajectory
    print("\n── TRAJECTORY ──")
    for step in target["trajectory"]:
        print(f"\nStep {step['step']}: action={step['action']}"
              f" score={step.get('score', '?')} fallback={step['fallback']}")
        if step.get("raw_response"):
            print(f"  [LLM raw] \"{step['raw_response']}\"")
        if step.get("reasoning"):
            reasoning_preview = step["reasoning"][:300].replace("\n", " ")
            print(f"  [LLM reasoning] {reasoning_preview}...")
        board = step.get("board", [])
        if board:
            for r in board:
                print("  " + " ".join(str(c).rjust(2) for c in r))

    # Strategy after / reflection reasoning
    if show_reflection:
        print(f"\n── Strategy AFTER this episode ({len(target.get('strategy_after', ''))} chars) ──")
        print(target.get("strategy_after", "") or "(empty)")

        if target.get("reflection_reasoning"):
            print(f"\n── Reflection thinking process ──")
            print(target["reflection_reasoning"][:1000] + "..." if len(target["reflection_reasoning"]) > 1000 else target["reflection_reasoning"])


# ── PDF Export ────────────────────────────────────────────────────────


def render_step_image(game_name: str, board: list, step_info: dict, out_path: str):
    """Render a single board state as an image. Uses game's render() method."""
    # Add project root to path to import backend games
    if str(PROJECT_ROOT / "backend") not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))

    if game_name == "fourinarow":
        from games.game_fourinarow import FourInARow
        g = FourInARow.__new__(FourInARow)
        g.board = board
        rendered_path = g.render()
    elif game_name == "othello6":
        from games.game_othello6 import Othello6
        g = Othello6.__new__(Othello6)
        g.board = board
        g.size = 6
        rendered_path = g.render()
    else:
        # Generic text-based fallback image
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.axis("off")
        board_str = "\n".join(" ".join(str(c) for c in row) for row in board)
        ax.text(0.5, 0.5, board_str, ha="center", va="center", family="monospace", fontsize=14)
        plt.savefig(out_path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return out_path

    # Copy rendered to out_path (game.render writes to cache)
    import shutil
    shutil.copy(rendered_path, out_path)
    return out_path


def export_episode_to_pdf(run_dir: Path, episode: int, output_path: str | None = None):
    """Export a single episode's full trajectory as a PDF."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_LEFT

    # Load episode data
    episodes_path = run_dir / "episodes.jsonl"
    target = None
    with open(episodes_path) as f:
        for line in f:
            ep = json.loads(line)
            if ep["episode"] == episode:
                target = ep
                break

    if not target:
        print(f"Episode {episode} not found.")
        return

    # Determine game from run_dir path: evolution_logs/<game>/<model>/<run_id>
    game_name = run_dir.parent.parent.name
    model_name = run_dir.parent.name

    # Output path
    if output_path is None:
        output_path = str(run_dir / f"episode_{episode:03d}.pdf")

    # Image cache dir
    img_cache = run_dir / f"ep{episode:03d}_images"
    img_cache.mkdir(exist_ok=True)

    # Render each step to an image
    print(f"Rendering {len(target['trajectory'])} step images...")
    step_images = []
    for step in target["trajectory"]:
        step_num = step["step"]
        img_path = img_cache / f"step_{step_num:03d}.png"
        board = step.get("board", [])
        if not board:
            continue
        render_step_image(game_name, board, step, str(img_path))
        step_images.append((step, img_path))
        print(f"  Step {step_num} rendered")

    # Build PDF
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                             leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                             topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(name="Body", parent=styles["Normal"],
                                  fontSize=9, alignment=TA_LEFT)
    elements = []

    # Title page
    elements.append(Paragraph(f"<b>Game: {game_name}</b>", styles["Title"]))
    elements.append(Paragraph(f"Model: {model_name}", styles["Heading2"]))
    elements.append(Paragraph(f"Episode {episode} — Result: {target['result']} in {target['steps']} steps",
                              styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))

    # Strategy before (truncated)
    strat_before = target.get("strategy_before", "")
    if strat_before:
        elements.append(Paragraph("<b>Strategy Before Episode:</b>", styles["Heading3"]))
        # Escape HTML
        safe_text = strat_before.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        elements.append(Paragraph(safe_text, body_style))
        elements.append(Spacer(1, 0.2 * inch))

    elements.append(PageBreak())

    # One page per step
    for step, img_path in step_images:
        step_num = step["step"]
        action = step.get("action", "?")
        score = step.get("score", "?")
        fallback = step.get("fallback", False)
        raw = step.get("raw_response", "")

        elements.append(Paragraph(f"<b>Step {step_num}</b>  action={action}  score={score}"
                                    + (f"  [FALLBACK]" if fallback else ""),
                                    styles["Heading2"]))

        # Image
        elements.append(Image(str(img_path), width=5 * inch, height=5 * inch,
                                kind="proportional"))

        # LLM raw response
        if raw:
            safe_raw = str(raw).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_raw = safe_raw[:500]  # truncate
            elements.append(Paragraph(f"<b>LLM raw response:</b> \"{safe_raw}\"", body_style))

        elements.append(PageBreak())

    # Strategy after
    strat_after = target.get("strategy_after", "")
    if strat_after:
        elements.append(Paragraph("<b>Strategy After Episode:</b>", styles["Heading2"]))
        safe_text = strat_after.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        elements.append(Paragraph(safe_text, body_style))

    print(f"Building PDF...")
    doc.build(elements)
    print(f"Saved to: {output_path}")


# ── Main ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="View a single game trajectory")
    parser.add_argument("--session", "-s", help="Session ID (partial match ok) for normal game")
    parser.add_argument("--game", "-g", help="Game name filter")
    parser.add_argument("--show-llm", action="store_true", help="Show LLM responses for each step")

    parser.add_argument("--run", "-r", help="Evolution run_id (partial match ok)")
    parser.add_argument("--episode", "-e", type=int, help="Specific episode number to view")
    parser.add_argument("--show-reflection", action="store_true", help="Show strategy before/after + reflection reasoning")
    parser.add_argument("--pdf", action="store_true", help="Export episode as PDF with board images")
    parser.add_argument("--output", "-o", help="Output PDF path (default: <run_dir>/episode_NNN.pdf)")

    args = parser.parse_args()

    if args.run and args.episode and args.pdf:
        matches = find_evolution_run(args.run)
        if not matches:
            print(f"No evolution run found matching '{args.run}'")
            return
        export_episode_to_pdf(matches[0], args.episode, args.output)
    elif args.run:
        view_evolution_run(args.run, args.episode, args.show_reflection)
    elif args.session:
        view_normal_session(args.session, args.game, args.show_llm)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
