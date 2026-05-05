# Judge 评分模块设计

## 背景

AgentBench 当前已经支持规则评分（`rules`）和混合评分（`hybrid`），但 `JudgeScorer` 仍是占位实现。为了支持更接近真实评测场景的主观质量判断，需要实现一个可调用大模型 API 的 Judge 评分模块。

本设计只覆盖标准 OpenAI 协议和 Anthropic Messages API 两类主流协议。实现应保持轻量、可测试，并继续遵守 AgentBench 的现有边界：Core 层不依赖具体供应商协议，供应商相关逻辑集中在 scorer 层。

## 目标

- 支持 `scoring.mode: judge` 的任务通过外部 Judge 模型评分。
- 支持 `scoring.mode: hybrid` 继续组合规则评分和 Judge 评分。
- 支持 OpenAI-compatible Chat Completions 协议。
- 支持 Anthropic Messages API 协议。
- 支持 run 级 Judge 配置，包括 provider、model、base_url、api_key_env、temperature、timeout_seconds 和 max_tokens。
- 自动加载项目根目录下的 `.env`，让开源用户可以通过 `.env` 提供 API key。
- Judge 输出解析为标准 `ScoreResult`，错误统一标记为 `scoring_error`。
- 使用 `requests` 发起 HTTP 请求，不使用 `urllib.request`。

## 非目标

- 不支持在 YAML 中写明文 `api_key`。
- 不支持任务级覆盖 Judge 配置。
- 不支持流式响应。
- 不支持自动重试。
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

`temperature` 的合法范围为 `0.0` 到 `2.0`。`timeout_seconds` 和 `max_tokens` 必须为正数。配置非法时，评分结果应返回 `scoring_error`。

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

JudgeScorer 应构造一个评分 prompt，包含：

- 任务 ID 和任务名称。
- 原始任务 prompt。
- `judge_rubric`。
- Agent 的 assistant message 文本。
- 工作区内可用于评分的核心输出提示。

第一版不扫描整个工作区，不自动上传文件内容。Judge 主要基于标准 trace 中的 assistant message 评分。规则评分仍用于检查文件存在、文件内容和工具调用等确定性条件。

如果任务希望 Judge 评估文件内容，Agent 的最终响应应概述输出内容，或配合规则评分检查文件结果。后续版本可以单独设计「可显式声明待评审文件」能力。

## Judge 输出协议

Judge 模型必须返回 JSON 对象：

```json
{
  "score": 0.0,
  "passed": false,
  "reason": "简短说明"
}
```

解析规则：

- `score` 必须是 `0.0` 到 `1.0` 的数字。
- `passed` 可以存在，但最终通过判定以 `score >= task.pass_threshold` 为准。
- `reason` 写入 `ScoreResult.notes`。
- 允许响应外层是纯 JSON 字符串；不支持 Markdown 代码块作为第一版要求。
- JSON 解析失败、缺少 `score`、`score` 越界或 HTTP 请求失败，均返回 `status="scoring_error"`，分数为 `0.0`。

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

## 错误处理

JudgeScorer 不应抛出未捕获异常给 Runner。以下情况统一转为 `ScoreResult(status="scoring_error")`：

- `run.judge` 缺失。
- `judge_rubric` 缺失。
- `provider` 不支持。
- `model` 缺失。
- `api_key_env` 对应环境变量不存在。
- `temperature`、`timeout_seconds` 或 `max_tokens` 非法。
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
- OpenAI provider 构造正确 endpoint、headers 和 payload。
- Anthropic provider 构造正确 endpoint、headers 和 payload。
- `temperature` 传入请求体。
- OpenAI 响应能解析为 `ScoreResult(status="scored")`。
- Anthropic 响应能解析为 `ScoreResult(status="scored")`。
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
- `.env` 自动加载生效。
- 文档覆盖用户运行和二次开发所需信息。
- 不引入明文 `api_key` 配置。
- 不引入自动重试、流式响应或任务级 Judge 配置。
