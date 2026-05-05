"""ReasoningBank-style memory store for EvoPlay.

A flat append-only JSONL bank of induced memory items. No embeddings, no
similarity retrieval — for a single-game/single-difficulty benchmark every
item is equally relevant, so we filter by (game, level) and slice by recency.
"""

from __future__ import annotations

import json
from pathlib import Path


class MemoryBank:
    """Append-only JSONL store of memory items keyed by (game, level)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: list[dict] = []  # one entry per induction (per episode)
        self.load()

    def load(self) -> None:
        self.entries.clear()
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    def append(self, entry: dict) -> None:
        """Append one induction record (the full episode meta + memory_items list)."""
        self.entries.append(entry)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def retrieve(
        self,
        game: str | None = None,
        level: int | str | None = None,
        max_items: int | None = None,
        most_recent_episodes: int | None = None,
    ) -> list[str]:
        """Return a flat list of memory-item strings.

        - Filter by game/level when provided.
        - Optionally keep only the most-recent N episodes' items.
        - Optionally cap the total number of items returned.
        """
        keep = list(self.entries)
        if game is not None:
            keep = [e for e in keep if e.get("game") == game]
        if level is not None:
            keep = [e for e in keep if str(e.get("level", "")) == str(level)]
        if most_recent_episodes is not None:
            keep = keep[-most_recent_episodes:]

        flat: list[str] = []
        for entry in keep:
            for item in entry.get("memory_items", []):
                if isinstance(item, str) and item.strip():
                    flat.append(item.strip())

        if max_items is not None:
            # Take from the tail so newer items take priority.
            flat = flat[-max_items:]
        return flat

    @staticmethod
    def format_for_prompt(items: list[str]) -> str:
        """Concatenate items into a block ready to drop into a system / play prompt."""
        if not items:
            return ""
        return "\n\n".join(items)

    def __len__(self) -> int:
        return sum(len(e.get("memory_items", [])) for e in self.entries)
