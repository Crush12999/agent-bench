# Judge 评分模块设计

## 背景

AgentBench 当前已经支持规则评分（`rules`）和混合评分（`hybrid`），但 `JudgeScorer` 仍是占位实现。为了支持更接近真实评测场景的主观质量判断，需要实现一个可调用大模型 API 的 Judge 评分模块。

本设计只覆盖标准 OpenAI 协议和 Anthropic Messages API 两类主流协议。实现应保持轻量、可测试，并继续遵守 AgentBench 的现有边界：Core 层不依赖具体供应商协议，供应商相关逻辑集中在 scorer 层。

## 目标

- 支持 `scoring.mode: judge` 的任务通过外部 Judge 模型评分。
- 支持 `scoring.mode: hybrid` 继续组合规则评分和 Judge 评分。
- 支持 OpenAI-compatible Chat Completions 协议。
- 支持 Anthropic Messages API 协议。
- 支持 run 级 Judge 配置，包括 provider、model、base_url、api_key_env、temperature、timeout_seconds、max_tokens 和有限重试参数。
- 自动加载执行 `agentbench run` 时当前工作目录下的 `.env`，让开源用户可以通过 `.env` 提供 API key。
- Judge 输入包含 Agent 执行过程摘要、工具调用、工具结果预览和工作区文本产物，而不是只依赖最终 assistant 文本。
- Judge 输出解析为标准 `ScoreResult`，错误统一标记为 `scoring_error`。
- 使用 `requests` 发起 HTTP 请求，不使用 `urllib.request`。

## 非目标

- 不支持在 YAML 中写明文 `api_key`。
- 不支持任务级覆盖 Judge 配置。
- 不支持流式响应。
- 不支持 Agent trial 自动重试。Judge API 调用支持有限次数的指数退避重试。
- 不支持多 Judge 投票或 pairwise 比较。
- 不支持数据库、leaderboard、Web UI 或远程任务队列。
- 不实现 OpenClaw adapter 之外的新 Agent 运行后端。

## 配置设计

Judge 配置只放在 `run.judge` 下。任务 YAML 只负责声明 `scoring.mode` 和 `judge_rubric`。

### OpenAI-compatible 示例

```yaml
run:
  adapter: openclaw
  model: minimax/MiniMax-M2.7
  trials: 1
  parallelism: 1
  output_dir: runs
  workspace_policy: failed
  judge:
    provider: openai
    model: gpt-4o-mini
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    temperature: 0
    timeout_seconds: 60
    max_tokens: 512
    max_retries: 2
    retry_backoff_seconds: 1
```

### Anthropic 示例

```yaml
run:
  adapter: openclaw
  model: minimax/MiniMax-M2.7
  trials: 1
  parallelism: 1
  output_dir: runs
  workspace_policy: failed
  judge:
    provider: anthropic
    model: claude-3-5-haiku-latest
    base_url: https://api.anthropic.com
    api_key_env: ANTHROPIC_API_KEY
    temperature: 0
    timeout_seconds: 60
    max_tokens: 512
    max_retries: 2
    retry_backoff_seconds: 1
```

### 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `provider` | string | 是 | 无 | 支持 `openai` 和 `anthropic`。 |
| `model` | string | 是 | 无 | Judge 模型名称。 |
| `base_url` | string | 否 | 按 provider 决定 | OpenAI 默认为 `https://api.openai.com/v1`，Anthropic 默认为 `https://api.anthropic.com`。 |
| `api_key_env` | string | 否 | 按 provider 决定 | OpenAI 默认为 `OPENAI_API_KEY`，Anthropic 默认为 `ANTHROPIC_API_KEY`。 |
| `temperature` | number | 否 | `0.0` | Judge 采样温度，建议评测场景保持 `0`。 |
| `timeout_seconds` | integer | 否 | `60` | HTTP 请求超时时间。 |
| `max_tokens` | integer | 否 | `512` | Judge 响应最大 token 数。 |
| `max_context_chars` | integer | 否 | `20000` | 传给 Judge 的评测上下文最大字符数。 |
| `max_tool_result_chars` | integer | 否 | `1000` | 单条工具结果预览最大字符数。 |
| `max_workspace_file_chars` | integer | 否 | `3000` | 单个工作区文本文件内容最大字符数。 |
| `max_retries` | integer | 否 | `2` | Judge API 调用最大尝试次数，包含首次请求。 |
| `retry_backoff_seconds` | number | 否 | `1.0` | 指数退避的初始等待秒数。 |

`temperature` 的合法范围为 `0.0` 到 `2.0`。`timeout_seconds`、`max_tokens`、`max_context_chars`、`max_tool_result_chars` 和 `max_workspace_file_chars` 必须为正数。`max_retries` 必须为 `1` 到 `5` 之间的整数，`retry_backoff_seconds` 必须大于 `0`。配置非法时，评分结果应返回 `scoring_error`。

## `.env` 加载规则

AgentBench 在 CLI 启动时自动加载当前工作目录下的 `.env` 文件。

规则：

- 只加载执行 `agentbench run` 时所在目录的 `.env`。
- `.env` 不存在时静默跳过。
- `.env` 中的变量只写入当前 Python 进程环境。
- 已存在的系统环境变量不被 `.env` 覆盖。
- 支持简单的 `KEY=value` 格式。
- 忽略空行和以 `#` 开头的注释行。
- 不负责创建 `.env`。
- 文档提醒用户不要提交 `.env`。

示例：

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## 任务配置

Judge 任务使用 `scoring.mode: judge`，并提供 `judge_rubric`。

```yaml
id: answer_quality
name: Answer quality
timeout_seconds: 120
pass_threshold: 0.8
prompt: |
  Read report.txt and write a concise summary.
seed_files:
  - source: fixtures/report.txt
    dest: report.txt
scoring:
  mode: judge
  judge_rubric: |
    Evaluate whether the answer is accurate, concise, and grounded in the report.
    Return a high score only if the summary captures the key facts without inventing details.
```

`hybrid` 模式继续使用现有 `weights`：

```yaml
scoring:
  mode: hybrid
  weights:
    rules: 0.7
    judge: 0.3
  rules:
    - id: summary_exists
      type: file_exists
      points: 1
      params:
        path: summary.md
  judge_rubric: |
    Score the quality of summary.md.
```

## Judge 输入内容

JudgeScorer 应参考 `skill/scripts/lib_grading.py` 中 `llm_judge` 的做法，构造一个能反映 Agent 执行全过程的评分 prompt。Judge 输入不应只包含最终 assistant 文本。

Prompt 至少包含：

- 任务 ID 和任务名称。
- 原始任务 prompt。
- `judge_rubric`。
- Agent 执行状态（例如 `success`、`timeout`、`error`）。
- Agent transcript 摘要。
- 工具调用名称和参数预览。
- 工具执行结果预览。
- assistant 文本消息摘要。
- trial 工作区中 Agent 产出的文本文件内容预览。

### Transcript 摘要

AgentBench 标准 `Trace` 当前包含 `assistant_message`、`tool_call`、`tool_result`、`file_event` 和 `error`。JudgeScorer 需要把这些事件转成可读摘要：

| Trace 事件 | Judge 摘要 |
| --- | --- |
| `assistant_message` | `Assistant: <text>` |
| `tool_call` | `Tool: <tool>(<args JSON preview>)` |
| `tool_result` | `Result: <result preview>` |
| `file_event` | `File event: <event JSON preview>` |
| `error` | `Error: <error preview>` |

截断规则：

- 单条 assistant 文本最多保留 `2000` 字符。
- 单个工具参数字符串最多保留 `200` 字符。
- 单条工具结果最多保留 `max_tool_result_chars` 字符。
- 单条 error / file event 最多保留 `1000` 字符。
- 所有摘要拼接后仍受 `max_context_chars` 总预算限制。

### 工作区文本产物

JudgeScorer 应读取 trial 工作区中的用户产出文本文件，作为补充评分证据。这样 Judge 可以直接检查 Agent 写出的报告、摘要、配置或代码片段，而不是依赖 Agent 自己声称完成了什么。

读取规则：

- 只读取 `run.workspace_path` 下的文件。
- 跳过隐藏目录和隐藏文件。
- 跳过 `.git`、`.openclaw`、`__pycache__`、`node_modules`、`skills` 等目录。
- 跳过 OpenClaw 启动文件：`BOOTSTRAP.md`、`SOUL.md`、`USER.md`、`IDENTITY.md`、`HEARTBEAT.md`、`TOOLS.md`、`AGENTS.md`。
- 只读取可用 UTF-8 解码的文本文件。
- 单个文件最多保留 `max_workspace_file_chars` 字符。
- 每个文件用 `### File: <relative path>` 标记。
- 工作区内容与 transcript 摘要合并后仍受 `max_context_chars` 总预算限制。

### 上下文预算

为了避免把大型工具结果或文件完整塞进 Judge 请求，第一版采用字符预算控制：

- 默认 `max_context_chars = 20000`。
- 先保留任务信息和 rubric。
- 再加入 transcript 摘要。
- 最后加入工作区文本产物。
- 如果超出预算，截断后追加 `...[truncated]` 标记。

这个策略保证 Judge 至少能看到任务和评分标准，同时尽量保留执行过程与产物证据。

### Prompt 结构

Prompt 应明确要求 Judge 不使用工具、不输出额外文本，并严格返回 JSON。建议结构：

```text
You are a grading function. Your ONLY job is to output a single JSON object.

CRITICAL RULES:
- Do NOT use tools.
- Do NOT write prose outside JSON.
- Be strict. Reserve 1.0 for genuinely excellent performance.

## Task
...

## Execution Status
...

## Agent Transcript Summary
...

## Workspace Files Created by Agent
...

## Grading Rubric
...

Respond with ONLY this JSON structure:
{"scores": {"criterion_name": 0.0}, "total": 0.0, "notes": "brief justification"}
```

## Judge 输出协议

Judge 模型必须返回 JSON 对象。推荐结构：

```json
{
  "scores": {"criterion_name": 0.0},
  "total": 0.0,
  "notes": "简短说明"
}
```

解析规则：

- `total` 必须是 `0.0` 到 `1.0` 的数字。
- `scores` 是可选明细，若存在则转换为 `CheckResult` 或写入 breakdown。
- `notes` 写入 `ScoreResult.notes`。
- 为兼容不同模型，可以额外接受简化结构：`{"score": 0.8, "reason": "..."}`，并规范化为 `total` / `notes`。
- 最终通过判定以 `total >= task.pass_threshold` 为准。
- JSON 解析失败、缺少可用总分、总分越界或 HTTP 请求失败，均返回 `status="scoring_error"`，分数为 `0.0`。

## HTTP 协议设计

### OpenAI-compatible

Endpoint：

```text
POST {base_url}/chat/completions
```

Headers：

```text
Authorization: Bearer ${api_key}
Content-Type: application/json
```

Payload：

```json
{
  "model": "gpt-4o-mini",
  "temperature": 0,
  "max_tokens": 512,
  "response_format": {"type": "json_object"},
  "messages": [
    {"role": "system", "content": "You are an impartial evaluator..."},
    {"role": "user", "content": "..."}
  ]
}
```

响应解析：

- 从 `choices[0].message.content` 读取 JSON 文本。

### Anthropic

Endpoint：

```text
POST {base_url}/v1/messages
```

Headers：

```text
x-api-key: ${api_key}
anthropic-version: 2023-06-01
Content-Type: application/json
```

Payload：

```json
{
  "model": "claude-3-5-haiku-latest",
  "temperature": 0,
  "max_tokens": 512,
  "system": "You are an impartial evaluator...",
  "messages": [
    {"role": "user", "content": "..."}
  ]
}
```

响应解析：

- 从 `content` 列表中提取 `type == "text"` 的文本片段并拼接。

## Judge API 重试

Judge API 调用需要支持有限重试，以降低临时网络抖动和供应商短暂不可用对评分的影响。这里的重试只作用于 Judge API 请求，不会重新执行 Agent trial，也不会重新运行任务。

默认策略：

- `max_retries = 2`，表示最多尝试 2 次请求。
- `retry_backoff_seconds = 1.0`，第 1 次失败后等待 `1.0` 秒，第 2 次失败后不再等待，直接返回错误。
- 第 `n` 次失败后的等待时间为 `retry_backoff_seconds * 2 ** (n - 1)`。
- `max_retries` 上限为 `5`，避免评测卡死或产生不可控成本。

可重试错误：

- `requests` 网络异常。
- 请求超时。
- HTTP `429`。
- HTTP `5xx`。

不可重试错误：

- 缺少 API key。
- provider / model / temperature 等配置非法。
- HTTP `4xx`（除 `429` 外）。
- 响应结构不符合协议。
- Judge 输出无法解析为合法评分 JSON。

所有尝试失败后，`ScoreResult.status` 为 `scoring_error`，`notes` 应包含最后一次错误，并说明已达到最大重试次数。

## 错误处理

JudgeScorer 不应抛出未捕获异常给 Runner。以下情况统一转为 `ScoreResult(status="scoring_error")`：

- `run.judge` 缺失。
- `judge_rubric` 缺失。
- `provider` 不支持。
- `model` 缺失。
- `api_key_env` 对应环境变量不存在。
- `temperature`、`timeout_seconds` 或 `max_tokens` 非法。
- `max_context_chars`、`max_tool_result_chars` 或 `max_workspace_file_chars` 非法。
- `max_retries` 或 `retry_backoff_seconds` 非法。
- HTTP 请求异常。
- HTTP 状态码不是 2xx。
- 响应 JSON 结构不符合预期。
- Judge 输出无法解析为合法评分 JSON。

Runner 已经能把评分器异常转换为 `scoring_error`，但 JudgeScorer 自身仍应尽量返回结构化错误，方便用户查看 `result.json`。

## 代码组织

预计新增或修改：

```text
src/agentbench/core/task.py          # 扩展 JudgeConfig
src/agentbench/env.py                # 加载 .env
src/agentbench/cli.py                # CLI 启动时加载 .env，并把 RunConfig.judge 注入评分器
src/agentbench/scorers/judge.py      # 实现 JudgeScorer
src/agentbench/scorers/hybrid.py     # 默认 JudgeScorer 接收配置
pyproject.toml                       # 增加 requests 依赖
docs/usage.md                        # 增加 Judge 使用说明
docs/development.md                  # 增加 Judge 开发说明
tests/test_env.py                    # .env 加载测试
tests/test_judge_scorer.py           # OpenAI / Anthropic 协议与错误测试
tests/test_cli.py                    # CLI 装配测试
```

## 测试策略

必须使用 TDD。核心测试包括：

- `.env` 文件不存在时不报错。
- `.env` 能加载 key-value，且不覆盖已有环境变量。
- `load_run_config()` 能加载完整 Judge 配置和默认值。
- Judge prompt 包含 assistant message、tool call、tool result、file event、error 和 workspace 文本产物。
- Judge prompt 对工具参数、工具结果和工作区文件内容执行截断。
- Judge API 对网络异常、超时、HTTP `429` 和 HTTP `5xx` 执行有限指数退避重试。
- Judge API 不重试配置错误、HTTP `4xx`（除 `429` 外）和 JSON 解析错误。
- OpenAI provider 构造正确 endpoint、headers 和 payload。
- Anthropic provider 构造正确 endpoint、headers 和 payload。
- `temperature` 传入请求体。
- OpenAI 响应中的 `scores` / `total` 能解析为 `ScoreResult(status="scored")`。
- Anthropic 响应中的 `scores` / `total` 能解析为 `ScoreResult(status="scored")`。
- 简化响应 `score` / `reason` 能被规范化。
- Judge score 低于 `pass_threshold` 时 `passed=False`。
- 缺少 API key、HTTP 非 2xx、输出非 JSON、score 越界时返回 `scoring_error`。
- `HybridScorer` 使用配置后的 JudgeScorer。

测试不发真实网络请求，使用 mock 的 `requests.post`。

## 文档更新

使用文档需要补充：

- `.env` 示例。
- `run.judge` 配置字段表。
- OpenAI-compatible 配置示例。
- Anthropic 配置示例。
- Judge 任务 YAML 示例。
- Judge 输入上下文包含 transcript 摘要、工具调用、工具结果和工作区文本文件。
- 上下文长度控制字段说明。
- Judge API 重试字段和指数退避策略说明。
- 常见错误说明。

开发文档需要补充：

- JudgeScorer 架构说明。
- Provider 协议边界。
- 新增 provider 的测试要求。

## 验收标准

- `pytest -q` 通过。
- `agentbench run` 在 `scoring.mode: judge` 任务中能使用 mock 测试覆盖 Judge 评分路径。
- OpenAI-compatible 请求符合 Chat Completions 基本协议。
- Anthropic 请求符合 Messages API 基本协议。
- Judge 输入包含 Agent 执行过程和工作区产物，并有明确截断策略。
- Judge API 有有限次数指数退避重试，且不会重试不可恢复错误。
- 当前工作目录下的 `.env` 自动加载生效。
- 文档覆盖用户运行和二次开发所需信息。
- 不引入明文 `api_key` 配置。
- 不引入 Agent trial 自动重试、流式响应或任务级 Judge 配置。
