# ReasoningBank for EvoPlay

EvoPlay 的 `agent/reasoning_bank/` 是 [google-research/reasoning-bank](https://github.com/google-research/reasoning-bank) 论文里 memory 机制的精简移植，用于在 EvoPlay benchmark 上做实验。

---

## 1. 它是什么 / 跟 EvolutionAgent 有什么区别

| | `EvolutionAgent` | `ReasoningBankAgent` |
|---|---|---|
| 知识形态 | **一个**不停被重写的 strategy 文档（随集数累加，会 bloat） | **一组**离散的 memory items，每条都有 title/description/content |
| 反思 prompt | `simple`（rule list）或 `cel`（master rulebook） | `SUCCESSFUL_SI` / `FAILED_SI`（按本集胜负二选一） |
| 每集产出 | 全量重写 strategy | ≤3 条 memory items，**追加**到 bank |
| 注入 play 的方式 | 把整个 strategy 拼到 system prompt | 把 bank 里相关 items 拼到 system prompt |
| 检索 | 没有（始终用最新版） | 按 `(game, level)` 过滤 + 可选 recency 切片 + 总数上限 |

**没有 embedding 检索**——EvoPlay 单游戏单难度里所有 memory 同等相关，用文本相似度纯属浪费 API。需要按局面相似度检索的时候再单独写。

---

## 2. 文件结构

```
agent/reasoning_bank/
  __init__.py
  prompts.py        # SUCCESSFUL_SI / FAILED_SI（原论文照抄）
  memory.py         # MemoryBank：append-only JSONL 存储 + 过滤检索
  induce.py         # induce_memory_items() / parse_memory_items() / format_trajectory()
agent/reasoning_bank_agent.py   # ReasoningBankAgent（继承 EvolutionAgent）
```

---

## 3. 跑起来

最小命令：

```bash
OPENAI_KEY=$(grep OPENAI_API_KEY .env | cut -d= -f2)
conda run -n evoplay python agent/reasoning_bank_agent.py \
    --game fourinarow \
    --model gpt-5.4-nano \
    --api-key "$OPENAI_KEY" --api-base "" \
    --episodes 30 \
    --max-tokens 4096 \
    --play-prompt cel
```

跑完会得到：

```
evolution_logs/fourinarow/reasoning-bank-gpt-5.4-nano/<run_id>/
  api_calls_ep001.jsonl ... api_calls_epNNN.jsonl
  episodes.jsonl
  experience.jsonl
  memory_bank.jsonl   ← 新增：所有 induced memory items 都堆在这
  summary.csv
```

`evolution_logs/...` 这套日志格式跟 `EvolutionAgent` 完全一致，所以现成的工具（`view_game.py`、`export_results.py`、`find_sessions.py`）都能直接用。

---

## 4. CLI 参数一览

| 参数 | 默认 | 说明 |
|---|---|---|
| `--game` | `fourinarow` | 游戏名 |
| `--model` | 无 | play / induce 都用这个模型 |
| `--api-key` | 无 | 必填 |
| `--api-base` | 无 | OpenAI 直连传空串 `""`；SiliconFlow 等传完整 URL |
| `--episodes` | 30 | 跑几集 |
| `--max-tokens` | 4096 | play 调用的 max_tokens |
| `--play-prompt` | `cel` | `simple` 或 `cel`，跟 EvolutionAgent 同义 |
| `--bank-path` | `<log_dir>/memory_bank.jsonl` | bank 的 JSONL 路径。**跨 run 共享时把它指到一个固定位置** |
| `--retrieve-max-items` | 无上限 | 单次 play 最多注入多少条 items |
| `--retrieve-recent-episodes` | 无限制 | 只用最近 N 集 induced 的 items |
| `--subdir` | `reasoning-bank-<model>` | 覆盖日志目录名 |
| `--temperature`, `--no-thinking`, `--delay`, `--backend-url` | 同 EvolutionAgent | — |

---

## 5. Memory bank 的格式（JSONL）

`memory_bank.jsonl` 每行一个 episode 的 induce 结果：

```json
{
  "episode": 7,
  "game": "fourinarow",
  "level": null,
  "result": "LOSE",
  "score": "bot_win",
  "session_id": "<backend session id>",
  "query": "game=fourinarow | opponent_difficulty=hard",
  "memory_items": [
    "# Memory Item 1\n## Title ...\n## Description ...\n## Content ...",
    "# Memory Item 2\n..."
  ],
  "raw_induction": "<完整 LLM 输出，未解析>",
  "timestamp": "2026-05-04T..."
}
```

`memory_items` 是 markdown 字符串数组，retrieve 出来后直接拼接成 system prompt 的一部分。

---

## 6. 实用场景

### 6.1 跨 run 共用一个 bank（推荐）

让 bank 不断累积，像论文里那样跨 30 集甚至 100 集积累经验：

```bash
mkdir -p memories
conda run -n evoplay python agent/reasoning_bank_agent.py \
    --game fourinarow --model gpt-5.4-nano \
    --api-key "$OPENAI_KEY" --api-base "" \
    --episodes 30 --max-tokens 4096 --play-prompt cel \
    --bank-path memories/fourinarow.jsonl
```

下次再跑同一条命令，bank 是 append 的，会复用之前 induced 的所有 items。

### 6.2 只用最近 5 集的经验

```bash
... --bank-path memories/fourinarow.jsonl \
    --retrieve-recent-episodes 5
```

适合 strategy 漂移大的场景——只看最近几集，旧的过时洞见不再干扰。

### 6.3 卡住注入到 prompt 里的 item 总量

```bash
... --retrieve-max-items 10
```

避免 bank 长大后 play prompt 也跟着撑爆 context。

### 6.4 重置 bank
```bash
rm memories/fourinarow.jsonl
```

或在 bank-path 里写一个新的文件名，等于从零开始。

### 6.5 看 bank 里都积累了什么

```bash
# 多少条 items？
python -c "
import json
items = sum(len(json.loads(l)['memory_items']) for l in open('memories/fourinarow.jsonl'))
print(f'{items} items across {sum(1 for _ in open(\"memories/fourinarow.jsonl\"))} episodes')
"

# 看每集的 result + items 数：
jq -c '{ep: .episode, result: .result, n: (.memory_items | length)}' memories/fourinarow.jsonl
```

---

## 7. 当作库直接调用

不想跑整个 agent，只想拿 induce 出 items：

```python
from agent.reasoning_bank import induce_memory_items, MemoryBank

trajectory = [...]  # EvoPlay 格式的 list[dict]：每条有 step/actor/action/board

items, raw = induce_memory_items(
    trajectory=trajectory,
    status="LOSE",                       # 或 "WIN" / "DRAW"
    query="game=fourinarow | level=hard",
    model="gpt-5.4-nano",
    api_key="sk-...",
    api_base=None,                        # 走 OpenAI 直连
)

bank = MemoryBank("memories/fourinarow.jsonl")
bank.append({
    "episode": 1, "game": "fourinarow", "level": None,
    "result": "LOSE", "memory_items": items,
})

# 检索
items_for_prompt = bank.retrieve(game="fourinarow", max_items=10)
text = MemoryBank.format_for_prompt(items_for_prompt)
```

---

## 8. 跟 EvolutionAgent 怎么挑

- **想直接对比这两种 memory 方案在 EvoPlay 上的效果** → 跑两次相同 model + 相同 episodes，一边 `evolution_agent.py --reflect-prompt cel`，一边 `reasoning_bank_agent.py`，比较胜率与 strategy/bank 长度增长。
- **数据要长期累积、可以"开箱即用"于新 run** → ReasoningBank（append-only bank 自然支持）。
- **想做最小改动、保持现有实验脚本** → EvolutionAgent。

---

## 9. 不在这版里的东西

跟 google-research/reasoning-bank 原版相比，砍掉的是：

- ❌ Gemini / Vertex AI embedding（`memory_management.embed_query_with_gemini`）
- ❌ Qwen3-Embedding-8B（要 GPU + transformers）
- ❌ 余弦相似度检索 + 缓存 jsonl
- ❌ Parallel scaling（同时跑 K 条 trajectory 再做 self-contrast，对应 `pipeline_scaling.py`）
- ❌ Autoeval LLM-as-a-judge（EvoPlay 有 ground truth WIN/LOSE，不需要）
- ❌ WebArena / SWE-Bench 适配代码

如果将来需要按棋盘/局面相似度检索，建议**用游戏特征（如各列高度、几连）做规则匹配**，而不是把 board 文本喂 embedding 模型——后者对游戏语义太迟钝。
