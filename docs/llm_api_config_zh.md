# GPT Researcher LLM API 配置中文说明

整理日期：2026-06-24

## 1. 先纠正一个概念

GPT Researcher 的 LLM API 不是配置在 `.venv` 里面。

`.venv` 的作用是：

- 存放 Python 解释器。
- 存放 pip 安装的依赖包。

真正的 API 配置应该写在项目根目录的 `.env` 文件里：

```text
C:\Users\liang\Desktop\agent学习\gpt-researcher\.env
```

项目启动时会通过 `python-dotenv` 自动读取 `.env`。

## 2. GPT Researcher 的三个 LLM 变量

GPT Researcher 会根据任务复杂度使用不同模型：

| 变量 | 含义 | 建议 |
| --- | --- | --- |
| `FAST_LLM` | 快速模型，用于简单任务、轻量处理 | 便宜、速度快 |
| `SMART_LLM` | 主力模型，用于大部分研究、写作、判断 | 质量较好 |
| `STRATEGIC_LLM` | 策略模型，用于规划、复杂推理 | 质量最好或推理能力强 |

格式统一是：

```text
供应商:模型名
```

例如：

```text
FAST_LLM=openai:gpt-5-mini
SMART_LLM=openai:gpt-5
STRATEGIC_LLM=openai:o4-mini
```

## 3. Embedding 变量

`EMBEDDING` 用于向量化、检索、上下文压缩等能力。

格式也是：

```text
供应商:embedding模型名
```

例如：

```text
EMBEDDING=openai:text-embedding-3-small
```

如果不配置，项目会走默认配置，但为了稳定，建议显式写出来。

## 4. 推荐方案一：OpenAI 官方 API

如果你有 OpenAI 官方 API key，`.env` 可以这样写：

```text
OPENAI_API_KEY=你的OpenAIKey
TAVILY_API_KEY=你的TavilyKey

FAST_LLM=openai:gpt-5-mini
SMART_LLM=openai:gpt-5
STRATEGIC_LLM=openai:o4-mini
EMBEDDING=openai:text-embedding-3-small

DOC_PATH=./my-docs
```

说明：

- `OPENAI_API_KEY` 用于调用 LLM 和 embedding。
- `TAVILY_API_KEY` 用于联网搜索。
- `FAST_LLM` 负责轻量任务。
- `SMART_LLM` 负责主要研究与写作。
- `STRATEGIC_LLM` 负责规划和复杂推理。
- `EMBEDDING` 负责检索和上下文压缩。

## 5. 推荐方案二：OpenAI 兼容 API

如果你使用的是第三方 OpenAI-compatible API，例如某些中转、私有部署、本地 llama.cpp server，需要配置 `OPENAI_BASE_URL`。

```text
OPENAI_BASE_URL=https://你的兼容API地址/v1
OPENAI_API_KEY=你的APIKey
TAVILY_API_KEY=你的TavilyKey

FAST_LLM=openai:你的快速模型名
SMART_LLM=openai:你的主力模型名
STRATEGIC_LLM=openai:你的策略模型名
EMBEDDING=custom:你的embedding模型名

DOC_PATH=./my-docs
```

如果对方的 embedding 也兼容 OpenAI，可尝试：

```text
EMBEDDING=openai:text-embedding-3-small
```

如果对方文档要求自定义 embedding，则用：

```text
EMBEDDING=custom:你的embedding模型名
```

## 6. 推荐方案三：DeepSeek

文档支持 DeepSeek：

```text
DEEPSEEK_API_KEY=你的DeepSeekKey
TAVILY_API_KEY=你的TavilyKey

FAST_LLM=deepseek:deepseek-chat
SMART_LLM=deepseek:deepseek-chat
STRATEGIC_LLM=deepseek:deepseek-chat

DOC_PATH=./my-docs
```

注意：

- 文档里的 DeepSeek 示例没有写 embedding。
- 如果使用 DeepSeek 做 LLM，仍然建议另外配置一个 embedding，例如 OpenAI、DashScope、Google Gemini 或本地 embedding。
- 否则涉及检索和上下文压缩时可能会报 embedding 相关错误。

## 7. 推荐方案四：DashScope / 通义千问

文档支持 DashScope：

```text
DASHSCOPE_API_KEY=你的DashScopeKey
TAVILY_API_KEY=你的TavilyKey

FAST_LLM=dashscope:qwen3-32b
SMART_LLM=dashscope:qwen-turbo-2025-04-28
STRATEGIC_LLM=dashscope:qwen-plus-latest
EMBEDDING=dashscope:text-embedding-v3

DOC_PATH=./my-docs
```

注意：

- `.env` 文件里不要写 `export`。
- 文档示例里有 `export FAST_LLM=...`，那是 Linux/macOS 终端写法。
- 在 `.env` 中只写 `FAST_LLM=...`。

## 8. 推荐方案五：MiniMax

文档支持 MiniMax：

```text
MINIMAX_API_KEY=你的MiniMaxKey
TAVILY_API_KEY=你的TavilyKey

FAST_LLM=minimax:MiniMax-M2.7-highspeed
SMART_LLM=minimax:MiniMax-M2.7
STRATEGIC_LLM=minimax:MiniMax-M2.7
EMBEDDING=minimax:embo-01

DOC_PATH=./my-docs
```

## 9. 推荐方案六：Ollama 本地模型

如果你本机运行 Ollama：

```text
OLLAMA_BASE_URL=http://localhost:11434
TAVILY_API_KEY=你的TavilyKey

FAST_LLM=ollama:llama3
SMART_LLM=ollama:llama3
STRATEGIC_LLM=ollama:llama3
EMBEDDING=ollama:nomic-embed-text

DOC_PATH=./my-docs
```

注意：

- 你需要先安装 Ollama。
- 你需要先拉取模型，例如 `ollama pull llama3`。
- 你需要先拉取 embedding 模型，例如 `ollama pull nomic-embed-text`。

## 10. Tavily 是什么

GPT Researcher 默认用 Tavily 做联网搜索。

所以除了 LLM key，你通常还需要：

```text
TAVILY_API_KEY=你的TavilyKey
```

没有 Tavily 时：

- Web research 可能无法正常搜索。
- 可以尝试改其他 retriever，但 Day 1 为了跑通，建议先用 Tavily。

## 11. 你的项目当前最小可运行配置

如果你用 OpenAI 官方 API，建议当前 `.env` 写成：

```text
OPENAI_API_KEY=你的OpenAIKey
TAVILY_API_KEY=你的TavilyKey

FAST_LLM=openai:gpt-5-mini
SMART_LLM=openai:gpt-5
STRATEGIC_LLM=openai:o4-mini
EMBEDDING=openai:text-embedding-3-small

DOC_PATH=./my-docs
```

如果你没有 GPT-5 权限，可以换成你账户可用的模型，例如：

```text
FAST_LLM=openai:gpt-4o-mini
SMART_LLM=openai:gpt-4o
STRATEGIC_LLM=openai:gpt-4o
EMBEDDING=openai:text-embedding-3-small
```

## 12. 配置后如何测试

进入项目目录：

```powershell
cd C:\Users\liang\Desktop\agent学习\gpt-researcher
```

用虚拟环境运行测试脚本：

```powershell
.\.venv\Scripts\python.exe scripts\run_day1_basic_query.py
```

成功后会生成：

```text
C:\Users\liang\Desktop\agent学习\gpt-researcher\outputs\day1_basic_query.md
```

## 13. 常见错误

### 13.1 `OPENAI_API_KEY` not found

说明 `.env` 没有写 key，或者启动命令不在项目根目录运行。

解决：

```powershell
cd C:\Users\liang\Desktop\agent学习\gpt-researcher
.\.venv\Scripts\python.exe scripts\run_day1_basic_query.py
```

### 13.2 模型不存在

说明 `FAST_LLM` / `SMART_LLM` / `STRATEGIC_LLM` 写了你账户不可用的模型。

解决：

- 换成你的 API 账户可用模型。
- 先用同一个稳定模型填三个变量。

### 13.3 embedding 报错

说明 `EMBEDDING` 没配置，或者 provider 不支持对应 embedding。

解决：

- OpenAI 用户用 `EMBEDDING=openai:text-embedding-3-small`。
- DashScope 用户用 `EMBEDDING=dashscope:text-embedding-v3`。
- Ollama 用户用 `EMBEDDING=ollama:nomic-embed-text`。

### 13.4 搜索报错

说明 `TAVILY_API_KEY` 没填或者无效。

解决：

- 注册 Tavily。
- 填入 `TAVILY_API_KEY`。
- 重新运行脚本。

## 14. 最重要的记忆点

不要把 key 写进 `.venv`。

应该写到：

```text
C:\Users\liang\Desktop\agent学习\gpt-researcher\.env
```

然后用：

```powershell
.\.venv\Scripts\python.exe scripts\run_day1_basic_query.py
```

来运行。
