# AgentBench 开发文档

本文面向希望阅读源码、贡献代码或二次开发 AgentBench 的开发者。

## 设计目标

AgentBench 的核心目标是提供一个小而稳定的本地评测框架：

- Core 层不依赖 OpenClaw 等具体 Agent 产品概念。
- Agent 执行后端通过 `AgentLoop` 协议接入。
- 评分逻辑通过 `Scorer` 协议接入。
- 每个 trial 的运行结果、评分结果和 trace 都落盘，便于复现和排查。
- 单个 trial 失败不能中断整次 run。

当前版本不追求平台化能力，因此不包含数据库、Web UI、leaderboard、分布式调度、自动重试和插件系统。

## 本地开发环境

```bash
git clone git@github.com:Crush12999/agent-bench.git
cd agent-bench

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## 代码结构

```text
src/agentbench/
├── adapters/
│   ├── base.py        # AgentLoop 协议和预检结果
│   ├── fake.py        # 测试用假适配器
│   └── openclaw.py    # OpenClaw CLI 适配器
├── core/
│   ├── aggregate.py   # run 汇总指标
│   ├── result.py      # AgentRunResult、ScoreResult 等结果模型
│   ├── runner.py      # 运行编排
│   ├── task.py        # YAML 配置模型和加载函数
│   ├── trace.py       # 标准 trace 事件模型
│   └── workspace.py   # trial 工作区和日志路径管理
├── reporters/
│   └── json.py        # JSON / JSONL 写入工具
├── scorers/
│   ├── base.py        # Scorer 协议
│   ├── hybrid.py      # 混合评分器
│   ├── judge.py       # Judge 占位评分器
│   └── rules.py       # 确定性规则评分器
└── cli.py             # CLI 入口和装配逻辑
```

## 核心数据流

一次 `agentbench run` 的主要流程如下：

```text
CLI
  ├── load_run_config()
  ├── load_tasks_from_path()
  ├── build_agent_loop()
  └── select_scorer()
        ↓
Runner.run()
  ├── agent_loop.preflight()
  ├── WorkspaceManager.prepare_trial()
  ├── agent_loop.run()
  ├── scorer.score()
  ├── write trace.json / result.json
  ├── append trials.jsonl
  ├── WorkspaceManager.cleanup_trial()
  └── aggregate_scores() → run.json
```

错误处理原则：

- `preflight` 失败会阻止整次 run 开始。
- 单个 trial 的 Agent 执行异常会被记录为 `AgentRunResult(status="error")`。
- 单个 trial 的评分异常会被记录为 `ScoreResult(status="scoring_error")`。
- 上述 trial 级异常不会中断其他 trial。

## 适配器开发

新增 Agent 后端时，实现 `agentbench.adapters.base.AgentLoop` 协议即可。

```python
from pathlib import Path

from agentbench.adapters.base import PreflightResult
from agentbench.core.result import AgentRunResult
from agentbench.core.task import RunConfig, TaskSpec


class MyAgentLoop:
    def preflight(self, config: RunConfig) -> PreflightResult:
        return PreflightResult(ok=True)

    def run(
        self,
        task: TaskSpec,
        trial_id: int,
        workspace: Path,
        log_dir: Path,
        timeout_seconds: int,
    ) -> AgentRunResult:
        ...
```

适配器需要负责：

- 在 `workspace` 中执行任务。
- 写入 `stdout.log`、`stderr.log` 和 `adapter.log`。
- 返回标准 `AgentRunResult`。
- 尽量把外部系统异常转换为 `status="error"` 或 `status="timeout"`。
- 如果有执行轨迹，应转换为标准 `Trace`。

### OpenClaw 适配器边界

OpenClaw 专有逻辑只能放在：

```text
src/agentbench/adapters/openclaw.py
```

Core 层不得依赖以下概念：

- OpenClaw agent store。
- OpenClaw `models.json`。
- OpenClaw `sessions.json`。
- OpenClaw CLI 参数。
- OpenClaw transcript 文件布局。

如果要修改 OpenClaw 行为，请优先补充或更新 `tests/test_openclaw_adapter.py`。

## 评分器开发

新增评分器时，实现 `agentbench.scorers.base.Scorer` 协议。

```python
from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import TaskSpec


class MyScorer:
    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        ...
```

评分器应遵循以下约定：

- 正常评分返回 `status="scored"`。
- 评分配置或评分过程异常返回 `status="scoring_error"`。
- 不应把评分器错误伪装成 Agent 执行失败。
- `score` 使用 `0.0` 到 `1.0` 之间的浮点数。
- `passed` 应根据任务的 `pass_threshold` 或评分器自身规则给出。

### 规则评分器

`RuleScorer` 适合可确定性检查的任务。新增规则类型时，需要修改：

- `src/agentbench/scorers/rules.py`
- `tests/test_rules_scorer.py`
- `docs/usage.md` 中的规则表

新增规则应保持输入参数简单，错误信息清晰。

## 结果模型约定

### AgentRunResult

`AgentRunResult` 表示 Agent 执行结果，重点字段包括：

| 字段 | 说明 |
| --- | --- |
| `status` | `success`、`timeout`、`error` 或 `preflight_failed`。 |
| `workspace_path` | trial 工作区路径。 |
| `log_dir` | trial 日志目录。 |
| `trace` | 标准化执行轨迹。 |
| `error` | 执行异常信息。 |

### ScoreResult

`ScoreResult` 表示评分结果，重点字段包括：

| 字段 | 说明 |
| --- | --- |
| `status` | `scored`、`scoring_error` 或 `skipped`。 |
| `score` | `0.0` 到 `1.0` 之间的分数。 |
| `passed` | 当前 trial 是否通过。 |
| `breakdown` | 单条检查项明细。 |
| `notes` | 评分补充说明或错误信息。 |

## 测试策略

项目使用 `pytest`。

```bash
pytest -q
```

测试分层：

| 测试文件 | 覆盖内容 |
| --- | --- |
| `tests/test_project_scaffold.py` | 项目骨架和包导入。 |
| `tests/test_task_config.py` | run / task YAML 加载。 |
| `tests/test_workspace.py` | trial 工作区创建和清理策略。 |
| `tests/test_result_models.py` | 结果模型序列化。 |
| `tests/test_rules_scorer.py` | 规则评分和 scoring error。 |
| `tests/test_hybrid_scorer.py` | 混合评分权重计算。 |
| `tests/test_runner_fake_adapter.py` | Runner 编排、trial 级异常隔离和输出文件。 |
| `tests/test_openclaw_adapter.py` | OpenClaw 命令构造、状态目录隔离和 transcript 解析。 |
| `tests/test_cli.py` | CLI 装配和 fake 示例运行。 |
| `tests/test_aggregate.py` | 汇总指标计算。 |

开发新功能时建议遵循 TDD：

1. 先写一个失败测试描述目标行为。
2. 运行测试，确认失败原因符合预期。
3. 写最小实现。
4. 再次运行测试，确认通过。
5. 视情况更新使用文档或开发文档。

## 代码风格

- 代码命名使用英文。
- 面向项目维护者的注释和 docstring 使用中文。
- 中英文之间保留空格，例如「OpenClaw 适配器」「JSON 报告」。
- 不为显而易见的赋值添加注释。
- 注释重点解释边界、外部系统行为、异常语义和不容易从代码看出的约束。

## 贡献流程

建议贡献流程：

1. Fork 或创建开发分支。
2. 安装开发依赖。
3. 为修改补充测试。
4. 运行 `pytest -q`。
5. 更新相关文档。
6. 提交 Pull Request。

提交前请确认：

- 没有引入规格外平台能力。
- Core 层没有依赖 OpenClaw 专有概念。
- 新增配置项已在文档中说明。
- 新增行为有对应测试。

## 发布前检查清单

- [ ] `pytest -q` 通过。
- [ ] README、使用文档和开发文档与当前行为一致。
- [ ] 示例命令可以直接运行。
- [ ] 没有把本地 run 产物、虚拟环境或缓存文件提交进仓库。
- [ ] OpenClaw 相关改动只出现在 `src/agentbench/adapters/openclaw.py` 和对应测试中。
