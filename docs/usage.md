# AgentBench 使用文档

本文面向 AgentBench 使用者，介绍如何安装项目、编写评测任务、运行评测，并理解输出结果。

## 适用场景

AgentBench 适合以下场景：

- 在本地批量运行一组 Agent 任务。
- 为每次 trial 创建隔离工作区。
- 使用确定性规则检查 Agent 是否完成任务。
- 生成可被脚本或后续分析系统消费的 JSON / JSONL 报告。
- 对 OpenClaw Agent 做端到端 smoke test 或小规模评测。

当前版本不提供 leaderboard、数据库、Web UI、分布式执行、checkpoint / resume、自动重试和插件系统。

## 安装

### 从源码安装

```bash
git clone git@github.com:Crush12999/agent-bench.git
cd agent-bench

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 验证安装

```bash
agentbench run --config examples/run.fake.yaml examples/tasks
pytest -q
```

如果命令输出 `runs/...`，说明 CLI 可以正常运行。

## 快速运行示例

项目内置了一个 `fake` 适配器示例：

```bash
agentbench run --config examples/run.fake.yaml examples/tasks
```

`examples/run.fake.yaml`：

```yaml
run:
  adapter: fake
  model: fake
  trials: 2
  parallelism: 2
  output_dir: runs
  workspace_policy: failed
```

`fake` 适配器会模拟一次成功执行，并在 trial 工作区写入 `summary.md`。

### OpenClaw E2E 示例

如果本机已经配置好 OpenClaw CLI，可以运行内置 smoke case：

```bash
agentbench run --config examples/run.openclaw.yaml examples/tasks/openclaw_smoke.yaml
```

该示例使用 `minimax/MiniMax-M2.7`，会要求 OpenClaw 在当前 trial 工作区创建 `summary.md`，并用 `file_exists` 和 `file_contains` 规则验证结果。

## 运行配置

运行配置文件描述一次评测的全局参数。

```yaml
run:
  adapter: openclaw
  model: minimax/MiniMax-M2.7
  trials: 1
  parallelism: 1
  output_dir: runs
  workspace_policy: failed
  adapter_config:
    openclaw_binary: openclaw
    state_dir: .agentbench/openclaw-state
    session_artifact_timeout_seconds: 15
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `adapter` | string | 是 | Agent 适配器名称。当前支持 `fake` 和 `openclaw`。 |
| `model` | string | 是 | 传给适配器的模型名。OpenClaw 适配器会把它传给 agent 创建和执行命令。 |
| `trials` | integer | 否 | 每个任务运行多少次，默认值为 `1`。 |
| `parallelism` | integer | 否 | 最大并行 trial 数，默认值为 `1`。 |
| `output_dir` | string | 否 | run 目录输出位置，默认值为 `runs`。 |
| `workspace_policy` | string | 否 | 工作区保留策略，支持 `all`、`failed`、`none`，默认值为 `failed`。 |
| `adapter_config` | object | 否 | 适配器专用配置。 |

### 工作区保留策略

| 策略 | 行为 |
| --- | --- |
| `all` | 保留所有 trial 工作区。 |
| `failed` | 只保留执行失败或评分未通过的 trial 工作区。 |
| `none` | 运行结束后清理所有 trial 工作区。 |

## 编写任务

任务文件是 YAML 格式。可以传入单个任务文件，也可以传入一个目录；传入目录时，AgentBench 会加载该目录下的 `*.yaml` 文件。

示例：

```yaml
id: summary
name: Summary
timeout_seconds: 30
pass_threshold: 0.6
prompt: |
  Read report.txt and write summary.md.
seed_files:
  - source: fixtures/report.txt
    dest: report.txt
scoring:
  mode: rules
  rules:
    - id: summary_exists
      type: file_exists
      points: 1
      params:
        path: summary.md
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 任务唯一标识。会用于 run 输出路径。 |
| `name` | string | 否 | 任务显示名称。未设置时使用 `id`。 |
| `prompt` | string | 否 | 传给 Agent 的任务提示词。 |
| `timeout_seconds` | integer | 否 | 单个 trial 超时时间，默认值为 `180`。 |
| `pass_threshold` | number | 否 | 判定通过的最低分，默认值为 `0.6`。 |
| `seed_files` | list | 否 | 运行前复制进 trial 工作区的文件列表。 |
| `scoring` | object | 否 | 评分配置，默认使用 `rules`。 |
| `metadata` | object | 否 | 任务元数据，当前只做加载和保留。 |

### 种子文件

`seed_files` 用于把任务所需输入复制到 trial 工作区。

```yaml
seed_files:
  - source: fixtures/report.txt
    dest: inputs/report.txt
```

如果 `source` 是相对路径，会按任务 YAML 所在目录解析。`dest` 是 trial 工作区内的目标路径。

## 评分规则

当前内置规则评分器支持以下规则类型。

| 规则类型 | 说明 | 关键参数 |
| --- | --- | --- |
| `file_exists` | 检查工作区内文件是否存在。 | `path` |
| `file_contains` | 检查文件是否包含全部文本模式。 | `path`、`pattern` 或 `patterns` |
| `file_not_contains` | 检查文件是否不包含全部文本模式。 | `path`、`pattern` 或 `patterns` |
| `response_contains` | 检查 assistant 响应是否包含全部文本模式。 | `pattern` 或 `patterns` |
| `response_not_contains` | 检查 assistant 响应是否不包含全部文本模式。 | `pattern` 或 `patterns` |
| `tool_called` | 检查指定工具是否被调用。 | `tool` |
| `tool_not_called` | 检查指定工具是否未被调用。 | `tool` |
| `tool_arg_contains` | 检查指定工具调用参数中是否包含文本。 | `tool`、`pattern` |

示例：

```yaml
scoring:
  mode: rules
  rules:
    - id: output_exists
      type: file_exists
      points: 1
      params:
        path: summary.md
    - id: output_mentions_safe
      type: file_contains
      points: 1
      params:
        path: summary.md
        patterns:
          - safe
    - id: response_done
      type: response_contains
      points: 1
      params:
        pattern: done
```

计分方式：

- 每条规则有自己的 `points`。
- 单条规则通过得 `1.0`，未通过得 `0.0`。
- 最终分数为加权平均：`sum(points * rule_score) / sum(points)`。
- 若规则参数非法或规则类型不支持，评分结果会标记为 `scoring_error`，分数为 `0.0`。

## 使用 OpenClaw 适配器

OpenClaw 适配器通过本机 `openclaw` CLI 执行任务。运行前请确保：

- `openclaw` 命令在 `PATH` 中可用，或通过 `adapter_config.openclaw_binary` 指定路径。
- OpenClaw 已配置可用模型和鉴权信息。
- 目标模型名与 OpenClaw 支持的格式一致。

示例配置：

```yaml
run:
  adapter: openclaw
  model: minimax/MiniMax-M2.7
  trials: 1
  parallelism: 1
  output_dir: runs
  workspace_policy: failed
  adapter_config:
    openclaw_binary: openclaw
    state_dir: .agentbench/openclaw-state
    session_artifact_timeout_seconds: 15
```

OpenClaw 适配器会做以下事情：

- 运行 `openclaw agents list --json` 做预检。
- 为每个 task / trial 生成独立的 OpenClaw agent id。
- 创建或复用绑定到当前 trial 工作区的 agent。
- 如果同名 agent 指向旧工作区，会先删除再创建。
- 把 `model` 传给 `openclaw agents add` 和 `openclaw agent`。
- 通过 `OPENCLAW_HOME`、`OPENCLAW_STATE_DIR` 和 `OPENCLAW_CONFIG_PATH` 隔离指定 `state_dir`。
- 等待 OpenClaw 写出 transcript，并转换为 AgentBench 标准 `trace.json`。

### OpenClaw 运行产物

每个 trial 的日志目录包含：

```text
stdout.log
stderr.log
adapter.log
trace.json
result.json
```

如果 OpenClaw 创建 agent 失败、执行超时或 transcript 缺失，相关信息会写入 `adapter.log` 和 `result.json`。

## 使用 Judge 评分

Judge 评分通过 run 级 `judge` 配置调用外部模型。任务 YAML 只声明 `scoring.mode: judge` 和 `judge_rubric`；模型供应商、鉴权环境变量、上下文预算和重试策略都放在 run 配置中，便于同一组任务切换不同 Judge。

### 配置 `.env`

`agentbench run` 会自动加载当前工作目录下的 `.env`，并且不会覆盖已经存在的系统环境变量。`.env` 不应提交到 Git。

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

如果使用 OpenAI-compatible 服务，只需要把 `api_key_env` 指向对应环境变量，不要把明文密钥写进 YAML。

### OpenAI-compatible 配置

```yaml
run:
  adapter: fake
  model: fake
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
    max_context_chars: 20000
    max_tool_result_chars: 1000
    max_workspace_file_chars: 3000
    max_retries: 2
    retry_backoff_seconds: 1
```

### Anthropic 配置

```yaml
run:
  adapter: fake
  model: fake
  judge:
    provider: anthropic
    model: claude-3-5-sonnet-latest
    base_url: https://api.anthropic.com
    api_key_env: ANTHROPIC_API_KEY
    temperature: 0
    timeout_seconds: 60
    max_tokens: 512
    max_context_chars: 20000
    max_tool_result_chars: 1000
    max_workspace_file_chars: 3000
    max_retries: 2
    retry_backoff_seconds: 1
```

### Judge 任务示例

```yaml
id: judge-summary
name: Judge Summary
timeout_seconds: 30
pass_threshold: 0.7
prompt: |
  Read report.txt and write a concise summary.md.
seed_files:
  - source: fixtures/report.txt
    dest: report.txt
scoring:
  mode: judge
  judge_rubric: |
    Score whether summary.md captures the main findings, avoids unsupported claims,
    and is concise. Return JSON only.
```

Judge 输入会包含：

- 任务提示词和 `judge_rubric`。
- Agent 执行状态、耗时和错误信息。
- 标准 trace 摘要，包括 assistant 文本、tool call、tool result、file event 和 error。
- trial 工作区中的文本文件预览。

大型内容会按 `max_context_chars`、`max_tool_result_chars` 和 `max_workspace_file_chars` 截断。隐藏目录、`.git`、`.openclaw`、`node_modules`、`skills` 和 OpenClaw bootstrap 文件不会进入 Judge 上下文。

### Judge 输出格式

推荐输出：

```json
{"scores": {"accuracy": 0.9, "conciseness": 0.8}, "total": 0.85, "notes": "summary is accurate and concise"}
```

也支持简化输出：

```json
{"score": 0.85, "reason": "summary is accurate and concise"}
```

`total` 或 `score` 必须是 `0.0` 到 `1.0` 之间的数字。解析失败、配置非法、缺少 API key 或供应商响应结构异常都会返回 `ScoreResult(status="scoring_error")`。

### Judge API 重试

Judge API 会对 `requests` 网络异常、超时、HTTP `429` 和 HTTP `5xx` 做有限次数指数退避重试，不会重新执行 Agent trial。

- `max_retries` 表示失败后最多重试次数，合法范围是 `1` 到 `5`。
- 总尝试次数为 `1 + max_retries`。
- `retry_backoff_seconds` 是第一次失败后的等待秒数，之后按 `base * 2`、`base * 4` 递增。
- HTTP `4xx`（除 `429` 外）、缺少 API key、配置非法和 Judge 输出 JSON 非法不会重试。

## 输出结果

一次运行完成后，AgentBench 会输出 run 目录。

```text
runs/20260505T145542Z-65147549
```

目录结构示例：

```text
runs/{run_id}/
├── run.json
├── trials.jsonl
├── logs/
│   └── summary/
│       └── trial-1/
│           ├── adapter.log
│           ├── result.json
│           ├── stderr.log
│           ├── stdout.log
│           └── trace.json
└── workspaces/
    └── summary/
        └── trial-1/
```

`run.json` 中的核心指标：

| 字段 | 说明 |
| --- | --- |
| `average_score` | 所有 trial 的平均分。 |
| `pass_at_1` | 所有 trial 中通过的比例。 |
| `pass_at_k` | 至少有一个 trial 通过的任务比例。 |
| `pass_k` | 所有 trial 都通过的任务比例。 |
| `avg_score_stddev` | 各任务分数标准差的平均值。 |
| `tasks` | 按任务拆分的统计信息。 |

`trials.jsonl` 每行是一条 trial 摘要，适合后续用脚本逐行读取。

## 常见问题

### OpenClaw 预检失败怎么办？

先确认 `openclaw` 命令可执行：

```bash
openclaw agents list --json
```

如果使用了 `state_dir`，请确认该目录下的 OpenClaw 配置可用。

### 为什么任务成功了但没有保留 workspace？

检查 `workspace_policy`。默认值为 `failed`，成功且评分通过的 trial 会清理 workspace。如需调试，请设为：

```yaml
workspace_policy: all
```

### 为什么评分结果是 `scoring_error`？

这通常表示评分规则配置有问题，例如：

- 使用了不支持的 `type`。
- 缺少必需的 `params` 字段。
- `file_contains` 指向的文件不存在。

请查看对应 trial 的 `result.json`，其中 `score.notes` 会记录错误信息。

### Judge 评分一直是 `scoring_error` 怎么办？

请先查看对应 trial 的 `result.json` 中的 `score.notes`。常见原因包括：

- 当前工作目录没有 `.env`，或 `api_key_env` 指向的环境变量不存在。
- `provider` 不是 `openai` 或 `anthropic`。
- `temperature`、`max_retries`、`retry_backoff_seconds` 或上下文预算字段非法。
- Judge 返回的内容不是合法 JSON，或分数不在 `0.0` 到 `1.0` 范围内。
