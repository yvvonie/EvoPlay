# 在 EvoPlay 里调用大模型

项目里调 LLM 的入口主要是 [agent/llm.py](../agent/llm.py) 的 `LLM` 类——所有 reasoning 模块、agent、evolution 都从它走。下面讲怎么用、有哪些坑。

---

## 1. 一句话调用

```python
from agent.llm import LLM

llm = LLM(
    model="gpt-5.4-nano",
    api_key="sk-...",
)
text = llm.call(
    messages=[{"role": "user", "content": "Pick a column 0-6 to drop a piece."}],
    system_message="You are a Connect-4 agent.",
)
print(text)
```

`call()` 返回一个**字符串**——content 部分。reasoning（如果 provider 给了）存在 `llm.last_reasoning`，token 用量在 `llm.last_usage`。

---

## 2. 支持哪些 provider

provider 是从 model 名前缀**自动检测**的：

| Model 前缀 | Provider | api_base |
|---|---|---|
| `gpt-*`, `o1-*`, `o3-*`, `azure/...` | OpenAI | 不填或 `""` |
| `claude-*` | Anthropic | 不填 |
| `gemini-*` | Gemini | 不填 |
| `ollama/*` | Ollama | 本地 URL |
| `openai/Qwen/...`, 任意自定义 | 走 OpenAI 协议 | **填 SiliconFlow / vLLM 的 base URL** |

调 SiliconFlow 上的 Qwen：

```python
llm = LLM(
    model="openai/Qwen/Qwen3-8B",      # 注意 openai/ 前缀
    api_key="sk-silicon-...",
    api_base="https://api.siliconflow.cn/v1",
    no_thinking=True,                    # 关掉 thinking，省 max_tokens
)
```

> `api_base` 一旦设置，`call()` 会**走纯 HTTP 直连**（绕过 litellm），因为 litellm 会丢掉 `reasoning_content` 字段。

---

## 3. 关键参数

```python
LLM(
    model: str,                      # 必填
    api_key: str | None = None,      # 不填读环境变量
    api_provider: str | None = None, # 不填自动从 model 推断
    api_base: str | None = None,     # 自定义 endpoint
    temperature: float = 0.7,
    max_tokens: int = 1000,
    no_thinking: bool = False,       # Qwen3 / DeepSeek-R1 等思考模型可关
    extra_headers: dict | None = None,
)
```

调用时还能临时覆写：

```python
llm.call(messages=[...], temperature=0.0, max_tokens=4096)
```

---

## 4. 必须知道的几个坑

### 4.1 GPT-5.x / o1 / o3 用 `max_completion_tokens`
代码已经按 model 名前缀自动切换：

```python
if model.startswith(("gpt-5", "o1", "o3")):
    body["max_completion_tokens"] = body.pop("max_tokens")
```

你直接传 `max_tokens` 就行，不用关心。

### 4.2 思考模型的 token 黑洞
Qwen3-Thinking、DeepSeek-R1 等模型默认会先吐一大段 `reasoning_content` 再给 content。如果 `max_tokens` 太小，思考阶段就把额度用完了，content 是空。

两个解法：
- `no_thinking=True`（OpenAI 兼容协议下传 `enable_thinking=false`，部分 provider 支持）
- 或者把 `max_tokens` 调大到 8192+

### 4.3 `</think>` 标签自动剥离
如果模型把 reasoning 写在 `<think>...</think>` 里再给最终答案，`call()` 会自动只返回 `</think>` 后面的部分。如果你想要原始内容，看 `llm.last_reasoning`。

### 4.4 重试和超时
默认 **20 次重试**、单次 **120 秒超时**，指数退避（最多 60s）。所有失败都打到 `api_logger`（见下文）。要改 → 改 [agent/llm.py](../agent/llm.py) 顶部的 `MAX_RETRIES` / `TIMEOUT`。

### 4.5 设了 `api_base` 后只看 OpenAI 兼容
`_direct_api_call` 假定 endpoint 兼容 OpenAI Chat Completions 协议（`POST /chat/completions`，body 用 `messages` / `temperature` / `max_tokens`）。SiliconFlow / vLLM / TGI / together.ai 都行；Vertex AI、Bedrock 不行。

---

## 5. API 调用日志

`agent/llm.py` 里有个全局 `api_logger`——所有 `LLM.call()` 的成功和失败都会被记录：

```python
from agent.llm import api_logger

api_logger.set_log_file("api_calls.jsonl")  # 开始记
# ... 你的 LLM 调用 ...
api_logger.set_log_file(None)               # 停止
```

每行一个 JSON：

```json
{"type":"api_call","status":"success","model":"gpt-5.4-nano",
 "input":[...],"output_content":"...",
 "usage":{"prompt_tokens":120,"completion_tokens":34},"attempt":1}
```

agent / evolution_agent / reasoning_bank_agent 都会**自动**在每集开始 `set_log_file` 到 `api_calls_epNNN.jsonl`，所以一般不用手动调。

---

## 6. 其他调用路径（什么时候用）

项目里还有两条调 LLM 的路径——大部分时候用 `LLM` 就够了，但如果你需要更细粒度的控制：

### 6.1 `EvolutionAgent._call_llm`（在 [agent/evolution_agent.py](../agent/evolution_agent.py)）
直接 HTTP，自带：
- `purpose=` 标签（"play" / "reflection" / "induce_memory" 等）
- 独立的 reflection 模型（`reflect_model` / `reflect_api_key` / `reflect_api_base`）
- 每条调用都打到当前 episode 的日志文件

写新的 evolution-style agent 时直接 inherit `EvolutionAgent` 然后调用 `self._call_llm()` 最省事。

### 6.2 `agent/reasoning_bank/induce.py::_direct_chat`
最小化 HTTP 调用，**没有重试、没有日志**。只在 `induce_memory_items()` 不带 `llm_call` 参数时用作 fallback。

```python
from agent.reasoning_bank.induce import _direct_chat
text = _direct_chat(
    messages=[{"role":"system","content":"..."},{"role":"user","content":"..."}],
    model="gpt-5.4-nano", api_key="sk-...", api_base=None,
    temperature=0.7, max_tokens=2048,
)
```

适合一次性脚本、不需要日志的场景。

---

## 7. 多模态（把棋盘当图片传）

`LLM` 走 multimodal 是通过 message content 数组：

```python
import base64

with open("board.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

messages = [{
    "role": "user",
    "content": [
        {"type": "text", "text": "What's the best move?"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ],
}]
text = llm.call(messages=messages)
```

EvoPlay 里 `VanillaReasoning(multimodal=True)` 自动调用 game backend 的 `render()` 方法，拿到 PNG 路径再 base64 编码。直接看 [agent/reasoning/vanilla_reasoning.py](../agent/reasoning/vanilla_reasoning.py) 里 `_build_multimodal_prompt`。

---

## 8. Streaming

目前**没有**封装 streaming 调用。如果需要流式输出，自己直接用 litellm：

```python
import litellm
for chunk in litellm.completion(model="gpt-5.4-nano", messages=[...], stream=True):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

或者用 OpenAI SDK 的 `stream=True`。

---

## 9. 速查清单

| 想做的事 | 怎么做 |
|---|---|
| 一次性调 OpenAI | `LLM(model="gpt-4o-mini", api_key="...")` 然后 `.call()` |
| 调 SiliconFlow 上的 Qwen | `LLM(model="openai/Qwen/Qwen3-8B", api_key="...", api_base="https://api.siliconflow.cn/v1", no_thinking=True)` |
| 调 GPT-5.x | 同 OpenAI，代码会自动处理 `max_completion_tokens` |
| 拿 reasoning 内容 | `.last_reasoning` |
| 拿 token 用量 | `.last_usage` |
| 临时改 temperature | `.call(messages, temperature=0.0)` |
| 写日志 | `api_logger.set_log_file("...jsonl")` |
| 多模态 | message content 用数组，加 `image_url` |
| 重试 / 超时 | 改 [agent/llm.py](../agent/llm.py) 顶部 `MAX_RETRIES` / `TIMEOUT` |

---

## 10. 一个完整能跑的例子

```python
"""one_shot_llm.py"""
import os, sys
sys.path.insert(0, "/Users/shaoshao/Desktop/EvoPlay")  # 或者 cd 到项目根

from agent.llm import LLM, api_logger

api_logger.set_log_file("/tmp/my_calls.jsonl")

llm = LLM(
    model="gpt-5.4-nano",
    api_key=os.environ["OPENAI_API_KEY"],
    temperature=0.0,
    max_tokens=512,
)

text = llm.call(
    messages=[{"role": "user", "content": "Explain Connect-4 zugzwang in one sentence."}],
    system_message="You are an expert in board games.",
)
print("=== content ===")
print(text)
print(f"=== reasoning ({len(llm.last_reasoning)} chars) ===")
print(llm.last_reasoning[:200])
print(f"=== usage ===\n{llm.last_usage}")
```

跑：

```bash
OPENAI_API_KEY=$(grep OPENAI_API_KEY .env | cut -d= -f2) \
    conda run -n evoplay python one_shot_llm.py
```

看 `/tmp/my_calls.jsonl` 就有这次调用的完整记录。
