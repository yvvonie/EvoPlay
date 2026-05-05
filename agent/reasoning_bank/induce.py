"""Induce ReasoningBank-style memory items from an EvoPlay episode trajectory.

Two ways to call this:
  1. With a callable `llm_call(messages) -> (content, reasoning, usage)` — fits
     EvolutionAgent._call_llm.
  2. As a standalone HTTP call by passing model/api_key/api_base.

Trajectory format expected (matches what EvolutionAgent.play_episode emits and
what agent/human_history_evolution.py emits): a list of dicts with keys
`step`, `actor` ("self" or "opponent"), `action`, `board`, optional
`reasoning` / `raw_response`.
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Callable

from .prompts import SUCCESSFUL_SI, FAILED_SI


def _board_to_str(board) -> str:
    if not board:
        return ""
    if isinstance(board, list) and board and isinstance(board[0], list):
        return "\n".join(" ".join(str(c) for c in row) for row in board)
    if isinstance(board, dict):
        try:
            return json.dumps(board, ensure_ascii=False)
        except Exception:
            return str(board)
    return str(board)


def format_trajectory(trajectory: list[dict]) -> str:
    """Render a trajectory as text for the memory-induction prompt.

    Mirrors the upstream `<think>...<action>...` style, with an explicit
    actor label and the post-move board snapshot.
    """
    blocks: list[str] = []
    for step in trajectory:
        actor = step.get("actor")
        action = step.get("action", "")
        board_str = _board_to_str(step.get("board"))
        if actor == "self":
            think = step.get("reasoning") or step.get("raw_response") or ""
            think = think.strip()
            blocks.append(
                f"<think>\n{think}\n</think>\n"
                f"<action actor=\"self\">{action}</action>\n"
                f"Board after your move:\n{board_str}"
            )
        elif actor == "opponent":
            blocks.append(
                f"<action actor=\"opponent\">{action}</action>\n"
                f"Board after opponent move:\n{board_str}"
            )
        else:
            # Older trajectories without actor label
            blocks.append(f"<action>{action}</action>\nBoard after:\n{board_str}")
    return "\n\n".join(blocks)


def parse_memory_items(raw: str) -> list[str]:
    """Split the LLM's markdown into individual memory-item strings.

    Each chunk starts with `# Memory Item N`. We tolerate stray code-fence
    wrappers (```) and missing trailing newlines.
    """
    text = raw.strip()
    # Strip leading / trailing fenced markers
    text = re.sub(r"^```[a-zA-Z]*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)

    # Split keeping the headers
    parts = re.split(r"(?m)^(?=#\s*Memory Item\s*\d+)", text)
    items = [p.strip() for p in parts if p.strip().startswith("# Memory Item")]
    return items


def induce_memory_items(
    trajectory: list[dict],
    status: str,
    query: str,
    *,
    llm_call: Callable | None = None,
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    temperature: float = 1.0,
    max_tokens: int = 2048,
) -> tuple[list[str], str]:
    """Run the induce-memory step. Returns (memory_items, raw_llm_output).

    `status` should be one of "WIN", "LOSE", "DRAW", or any falsy → treated as
    failure. Pass `llm_call` to reuse the host agent's HTTP+retry path; otherwise
    pass model/api_key/api_base and we'll run a one-shot HTTP call.
    """
    is_success = (str(status).upper() == "WIN")
    system_msg = SUCCESSFUL_SI if is_success else FAILED_SI

    user_msg = (
        f"**Query:** {query}\n\n"
        f"**Trajectory:**\n{format_trajectory(trajectory)}\n\n"
        f"**Outcome:** {status}"
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    if llm_call is not None:
        raw, _reasoning, _usage = llm_call(messages, max_tokens=max_tokens)
    else:
        if not model:
            raise ValueError("Either llm_call or model must be provided.")
        raw = _direct_chat(
            messages, model=model, api_key=api_key,
            api_base=api_base, temperature=temperature, max_tokens=max_tokens,
        )

    return parse_memory_items(raw), raw


def _direct_chat(
    messages: list[dict],
    *,
    model: str,
    api_key: str | None,
    api_base: str | None,
    temperature: float,
    max_tokens: int,
) -> str:
    """Minimal one-shot HTTP call to a Chat Completions endpoint."""
    base = (api_base or "https://api.openai.com/v1").rstrip("/")
    url = base + "/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if model.startswith(("gpt-5", "o1", "o3")):
        body["max_completion_tokens"] = body.pop("max_tokens")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    return (result["choices"][0]["message"].get("content") or "").strip()
