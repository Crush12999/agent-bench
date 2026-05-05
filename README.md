# AgentBench

AgentBench 是一个轻量级 Agent 评测框架，面向需要在本地批量运行任务、隔离 trial 工作区、收集执行轨迹并生成 JSON 报告的开发者。

当前版本以 OpenClaw 适配器为主要运行目标，同时提供 `fake` 适配器用于本地示例和测试。项目刻意保持小而清晰：不包含 leaderboard、数据库、Web UI、分布式调度、checkpoint / resume、自动重试或插件系统。

## 特性

- **本地 CLI 运行：** 通过 `agentbench run` 执行一个任务文件或一个任务目录。
- **适配器边界清晰：** Core 层只依赖 `AgentLoop` 协议，OpenClaw 专有逻辑集中在 `adapters/openclaw.py`。
- **trial 工作区隔离：** 每个任务和 trial 都有独立 workspace、stdout、stderr、adapter log、trace 和 result。
- **规则评分：** 支持文件、响应文本和工具调用相关的确定性规则。
- **基础统计：** 输出平均分、`pass_at_1`、`pass_at_k`、`pass_k` 和按任务拆分的指标。
- **可二次开发：** 适配器、评分器、任务模型和运行编排分层明确，便于扩展新 Agent 运行后端或评分方式。

## 快速开始

### 环境要求

- Python >= 3.11
- `pip`
- 如需运行 OpenClaw 评测，需要本机可执行的 `openclaw` CLI

### 安装

```bash
git clone git@github.com:Crush12999/agent-bench.git
cd agent-bench

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 运行本地 fake 示例

```bash
agentbench run --config examples/run.fake.yaml examples/tasks
```

命令会输出本次 run 的目录，例如：

```text
runs/20260505T145542Z-65147549
```

该目录中会包含：

- `run.json`：整次运行的汇总报告。
- `trials.jsonl`：每个 trial 的一行摘要。
- `logs/{task_id}/trial-{n}/result.json`：单个 trial 的运行结果和评分结果。
- `logs/{task_id}/trial-{n}/trace.json`：标准化后的执行轨迹。
- `workspaces/{task_id}/trial-{n}/`：按 `workspace_policy` 保留的工作区。

### 运行 OpenClaw E2E 示例

如果本机已经配置好 OpenClaw CLI，可以运行：

```bash
agentbench run --config examples/run.openclaw.yaml examples/tasks/openclaw_smoke.yaml
```

该示例使用 `minimax/MiniMax-M2.7`，会要求 OpenClaw 在 trial 工作区创建 `summary.md`，并用规则评分验证文件内容。

## 基本概念

| 概念 | 说明 |
| --- | --- |
| Task | 一个待评测任务，由 YAML 描述 prompt、超时时间、种子文件和评分规则。 |
| Trial | 同一个任务的一次独立运行，用于支持多次采样和 pass@k 指标。 |
| Adapter | Agent 运行后端，负责把任务交给具体 Agent CLI 或服务执行。 |
| Scorer | 评分器，负责把 Agent 输出转换为 `ScoreResult`。 |
| Trace | 标准化执行轨迹，用于记录 assistant message、tool call、tool result 等事件。 |
| Run | 一次完整评测，包含多个任务和多个 trial。 |

## 文档

- [使用文档](./docs/usage.md)：安装、配置、任务编写、评分规则和 OpenClaw 运行说明。
- [开发文档](./docs/development.md)：项目架构、二次开发入口、测试策略和贡献流程。

## 项目结构

```text
agentbench/
├── docs/                      # 使用文档和开发文档
├── examples/                  # 可直接运行的示例配置和任务
├── src/agentbench/
│   ├── adapters/              # Agent 运行适配器
│   ├── core/                  # 任务模型、Runner、结果模型和工作区管理
│   ├── reporters/             # JSON / JSONL 写入
│   ├── scorers/               # 规则评分、Judge 占位评分和混合评分
│   └── cli.py                 # 命令行入口
├── tests/                     # 单元测试和回归测试
├── pyproject.toml
└── README.md
```

## 开发与测试

```bash
pytest -q
```

当前测试覆盖项目骨架、配置加载、工作区管理、Runner 编排、规则评分、OpenClaw 适配器和 CLI 示例。

## 许可证

本项目使用 [MIT](./LICENSE) 许可证。
