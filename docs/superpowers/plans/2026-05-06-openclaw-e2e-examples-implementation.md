# AgentBench OpenClaw E2E 示例实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为 `agentbench` 增加 OpenClaw `rules`、`judge`、`hybrid` 三类端到端示例，以及一个可一次运行三类任务的多任务 run 配置。

**架构：** 示例层只新增和重组 `examples/` 资产，不修改 scorer、adapter、Runner 或 task schema。OpenClaw 专用任务收拢到 `examples/tasks/openclaw/`，单任务 run 配置分别演示 `judge` 和 `hybrid`，目录级 run 配置演示多任务执行。测试重点验证真实示例 YAML 可加载、schema 兼容、CLI 可以接收 OpenClaw 任务目录。

**技术栈：** Python 3.11+、PyYAML、pytest、标准库 pathlib、现有 `agentbench` CLI 和 scorer 配置模型。

---

## 执行前提

所有命令都从 `agentbench/` 子项目根目录执行：

```bash
cd /Users/ming/Documents/Code/2026/openclaw_repos/claw_eval_repos/agentbench
```

本计划采用单次最终 commit。前面任务只修改文件并运行针对性测试，最后统一提交完整示例 bundle，避免中途提交和收尾提交互相冲突。

## 文件结构

- 创建：`examples/tasks/openclaw/openclaw_smoke.yaml`
  - 复用现有 smoke 内容，作为多任务目录中的 `rules` 示例。
- 创建：`examples/tasks/openclaw/openclaw_skills_judge.yaml`
  - OpenClaw `skills` surface 的 `judge` 任务示例。
- 创建：`examples/tasks/openclaw/openclaw_skills_hybrid.yaml`
  - OpenClaw `skills` surface 的 `hybrid` 任务示例。
- 创建：`examples/run.openclaw.judge.yaml`
  - 单任务运行 `judge` 示例。
- 创建：`examples/run.openclaw.hybrid.yaml`
  - 单任务运行 `hybrid` 示例。
- 创建：`examples/run.openclaw.all.yaml`
  - 目录级运行 `rules`、`judge`、`hybrid` 三个 OpenClaw 任务。
- 创建：`tests/test_openclaw_examples.py`
  - 验证新增示例文件真实存在、可加载、schema 兼容、CLI 可接收任务目录。
- 修改：`README.md`
  - 增加 OpenClaw `judge` / `hybrid` / 多任务运行命令。
- 修改：`docs/usage.md`
  - 增加 OpenClaw 示例目录说明、三类示例运行方式和 `run.judge` / task `scoring` 分工说明。

---

### 任务 1：增加 OpenClaw 示例目录与 smoke 复本

**文件：**
- 创建：`examples/tasks/openclaw/openclaw_smoke.yaml`
- 创建：`tests/test_openclaw_examples.py`

- [ ] **步骤 1：编写失败的测试**

创建 `tests/test_openclaw_examples.py`：

```python
from pathlib import Path

from agentbench.cli import load_tasks_from_path


def test_openclaw_smoke_bundle_reuses_existing_smoke_task():
    original = load_tasks_from_path(Path("examples/tasks/openclaw_smoke.yaml"))[0]
    bundled = load_tasks_from_path(Path("examples/tasks/openclaw/openclaw_smoke.yaml"))[0]

    assert bundled.id == original.id
    assert bundled.name == original.name
    assert bundled.prompt == original.prompt
    assert bundled.pass_threshold == original.pass_threshold
    assert bundled.scoring.mode == "rules"
    assert [rule.id for rule in bundled.scoring.rules] == [rule.id for rule in original.scoring.rules]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_openclaw_smoke_bundle_reuses_existing_smoke_task -q`

预期：FAIL，报错指向 `examples/tasks/openclaw/openclaw_smoke.yaml` 不存在或无法读取。

- [ ] **步骤 3：编写最少实现代码**

创建 `examples/tasks/openclaw/openclaw_smoke.yaml`，内容与现有 `examples/tasks/openclaw_smoke.yaml` 一致：

```yaml
id: openclaw_smoke
name: OpenClaw smoke
timeout_seconds: 90
pass_threshold: 1.0
prompt: |
  Create a file named summary.md in the current workspace.
  The file must contain exactly this sentence: AgentBench OpenClaw smoke passed.
scoring:
  mode: rules
  rules:
    - id: summary_exists
      type: file_exists
      points: 1
      params:
        path: summary.md
    - id: summary_contains
      type: file_contains
      points: 1
      params:
        path: summary.md
        patterns:
          - AgentBench OpenClaw smoke passed
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_openclaw_smoke_bundle_reuses_existing_smoke_task -q`

预期：`1 passed`。

---

### 任务 2：增加 OpenClaw judge 任务示例

**文件：**
- 创建：`examples/tasks/openclaw/openclaw_skills_judge.yaml`
- 修改：`tests/test_openclaw_examples.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_openclaw_examples.py` 追加：

```python
def test_openclaw_skills_judge_example_has_expected_scoring():
    task = load_tasks_from_path(Path("examples/tasks/openclaw/openclaw_skills_judge.yaml"))[0]

    assert task.id == "openclaw_skills_judge"
    assert task.scoring.mode == "judge"
    assert task.pass_threshold == 0.75
    assert task.scoring.judge_rubric is not None
    assert task.scoring.rules == []
    assert "openclaw skills list --json" in task.prompt
    assert "skills_assessment.md" in task.prompt
    assert "primary fact source" in task.scoring.judge_rubric
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_openclaw_skills_judge_example_has_expected_scoring -q`

预期：FAIL，报错指向 `examples/tasks/openclaw/openclaw_skills_judge.yaml` 不存在或无法读取。

- [ ] **步骤 3：编写最少实现代码**

创建 `examples/tasks/openclaw/openclaw_skills_judge.yaml`：

```yaml
id: openclaw_skills_judge
name: OpenClaw skills judge
timeout_seconds: 120
pass_threshold: 0.75
prompt: |
  Use `openclaw skills list --json` as your primary fact source.
  Create a file named `skills_assessment.md` in the current workspace.

  The file must include:
  - a short overview of the current local OpenClaw skills state
  - 2 to 4 concrete observations grounded in the command output
  - 1 to 2 practical suggestions for a new user

  Do not invent skills, statuses, or capabilities that are not supported by the command output.
scoring:
  mode: judge
  judge_rubric: |
    Score the submission strictly using the following criteria:
    - It uses `openclaw skills list --json` as the primary fact source.
    - It does not invent skills, statuses, or capabilities not supported by the observed output.
    - It clearly summarizes the most relevant facts from the local skills inventory.
    - Its suggestions are concrete, restrained, and helpful to a new user.

    Give high scores only when the report is fact-grounded, clear, and useful.
    If the report is generic, speculative, or weakly tied to the observed output, reduce the score.
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_openclaw_skills_judge_example_has_expected_scoring -q`

预期：`1 passed`。

---

### 任务 3：增加 OpenClaw hybrid 任务示例

**文件：**
- 创建：`examples/tasks/openclaw/openclaw_skills_hybrid.yaml`
- 修改：`tests/test_openclaw_examples.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_openclaw_examples.py` 追加：

```python
def test_openclaw_skills_hybrid_example_has_expected_scoring():
    task = load_tasks_from_path(Path("examples/tasks/openclaw/openclaw_skills_hybrid.yaml"))[0]

    assert task.id == "openclaw_skills_hybrid"
    assert task.scoring.mode == "hybrid"
    assert task.pass_threshold == 0.7
    assert task.scoring.weights == {"rules": 0.6, "judge": 0.4}
    assert task.scoring.judge_rubric is not None
    assert [rule.id for rule in task.scoring.rules] == [
        "inventory_exists",
        "remediation_exists",
        "inventory_has_skills_key",
        "remediation_has_sections",
    ]
    assert "openclaw skills list --json" in task.prompt
    assert "skills_inventory.json" in task.prompt
    assert "skills_remediation.md" in task.prompt
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_openclaw_skills_hybrid_example_has_expected_scoring -q`

预期：FAIL，报错指向 `examples/tasks/openclaw/openclaw_skills_hybrid.yaml` 不存在或无法读取。

- [ ] **步骤 3：编写最少实现代码**

创建 `examples/tasks/openclaw/openclaw_skills_hybrid.yaml`：

```yaml
id: openclaw_skills_hybrid
name: OpenClaw skills hybrid
timeout_seconds: 120
pass_threshold: 0.7
prompt: |
  Use `openclaw skills list --json` as your primary fact source.

  Create two files in the current workspace:
  - `skills_inventory.json`
  - `skills_remediation.md`

  Requirements:
  - `skills_inventory.json` should capture a minimal structured inventory of the observed skills state.
  - `skills_remediation.md` should explain available skills, likely gaps or limits, and practical next steps for a new user.
  - If a status is unclear from the command output, explicitly say it is uncertain instead of guessing.
scoring:
  mode: hybrid
  weights:
    rules: 0.6
    judge: 0.4
  rules:
    - id: inventory_exists
      type: file_exists
      points: 1
      params:
        path: skills_inventory.json
    - id: remediation_exists
      type: file_exists
      points: 1
      params:
        path: skills_remediation.md
    - id: inventory_has_skills_key
      type: file_contains
      points: 1
      params:
        path: skills_inventory.json
        patterns:
          - '"skills"'
    - id: remediation_has_sections
      type: file_contains
      points: 1
      params:
        path: skills_remediation.md
        patterns:
          - "## Available Skills"
          - "## Gaps Or Limits"
          - "## Next Steps"
  judge_rubric: |
    Score the submission strictly using the following criteria:
    - The structured inventory is consistent with the observed `openclaw skills list --json` output.
    - The remediation document stays grounded in observed facts.
    - Uncertain states are explicitly labeled as uncertain instead of guessed.
    - The document presents useful next steps in a clear, practical order.

    Reduce the score if the response is generic, speculative, or disconnected from the observed skills state.
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_openclaw_skills_hybrid_example_has_expected_scoring -q`

预期：`1 passed`。

---

### 任务 4：增加 OpenClaw judge 和 hybrid run 配置

**文件：**
- 创建：`examples/run.openclaw.judge.yaml`
- 创建：`examples/run.openclaw.hybrid.yaml`
- 修改：`tests/test_openclaw_examples.py`

- [ ] **步骤 1：编写失败的测试**

先在 `tests/test_openclaw_examples.py` import 中加入 `load_run_config`，让红灯来自目标配置文件缺失，而不是测试代码自身缺少导入：

```python
from agentbench.core.task import load_run_config
```

再追加：

```python
def test_load_openclaw_judge_and_hybrid_run_configs():
    judge_config = load_run_config(Path("examples/run.openclaw.judge.yaml"))
    hybrid_config = load_run_config(Path("examples/run.openclaw.hybrid.yaml"))

    assert judge_config.adapter == "openclaw"
    assert hybrid_config.adapter == "openclaw"
    assert judge_config.model == "minimax/MiniMax-M2.7"
    assert hybrid_config.model == "minimax/MiniMax-M2.7"
    assert judge_config.workspace_policy == "all"
    assert hybrid_config.workspace_policy == "all"
    assert judge_config.adapter_config["openclaw_binary"] == "openclaw"
    assert hybrid_config.adapter_config["openclaw_binary"] == "openclaw"
    assert judge_config.judge is not None
    assert hybrid_config.judge is not None
    assert judge_config.judge.provider == "openai"
    assert hybrid_config.judge.provider == "openai"
    assert judge_config.judge.api_key_env == "OPENAI_API_KEY"
    assert hybrid_config.judge.api_key_env == "OPENAI_API_KEY"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_load_openclaw_judge_and_hybrid_run_configs -q`

预期：FAIL，报错指向 `examples/run.openclaw.judge.yaml` 或 `examples/run.openclaw.hybrid.yaml` 不存在。

- [ ] **步骤 3：编写最少实现代码**

创建 `examples/run.openclaw.judge.yaml`：

```yaml
run:
  adapter: openclaw
  model: minimax/MiniMax-M2.7
  trials: 1
  parallelism: 1
  output_dir: runs
  workspace_policy: all
  adapter_config:
    openclaw_binary: openclaw
    session_artifact_timeout_seconds: 15
  judge:
    provider: openai
    model: gpt-4o-mini
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    temperature: 0
    timeout_seconds: 60
    max_tokens: 512
```

创建 `examples/run.openclaw.hybrid.yaml`：

```yaml
run:
  adapter: openclaw
  model: minimax/MiniMax-M2.7
  trials: 1
  parallelism: 1
  output_dir: runs
  workspace_policy: all
  adapter_config:
    openclaw_binary: openclaw
    session_artifact_timeout_seconds: 15
  judge:
    provider: openai
    model: gpt-4o-mini
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    temperature: 0
    timeout_seconds: 60
    max_tokens: 512
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_load_openclaw_judge_and_hybrid_run_configs -q`

预期：`1 passed`。

---

### 任务 5：增加 OpenClaw 多任务 run 配置与 CLI 目录路径测试

**文件：**
- 创建：`examples/run.openclaw.all.yaml`
- 修改：`tests/test_openclaw_examples.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_openclaw_examples.py` 追加：

```python
def test_openclaw_all_run_config_supports_expected_task_modes():
    config = load_run_config(Path("examples/run.openclaw.all.yaml"))
    tasks = load_tasks_from_path(Path("examples/tasks/openclaw"))

    tasks_by_id = {task.id: task for task in tasks}

    assert config.adapter == "openclaw"
    assert config.judge is not None
    assert set(tasks_by_id) == {
        "openclaw_smoke",
        "openclaw_skills_judge",
        "openclaw_skills_hybrid",
    }
    assert tasks_by_id["openclaw_smoke"].scoring.mode == "rules"
    assert tasks_by_id["openclaw_skills_judge"].scoring.mode == "judge"
    assert tasks_by_id["openclaw_skills_hybrid"].scoring.mode == "hybrid"


def test_cli_accepts_openclaw_all_directory(monkeypatch):
    from agentbench import cli

    seen: dict[str, object] = {}

    class RecordingRunner:
        def __init__(self, config, agent_loop, scorer):
            seen["adapter"] = config.adapter

        def run(self, tasks):
            seen["task_ids"] = {task.id for task in tasks}
            return {"run_dir": "runs/example"}

    monkeypatch.setattr(cli, "build_agent_loop", lambda config: object())
    monkeypatch.setattr(cli, "select_scorer", lambda config, tasks: object())
    monkeypatch.setattr(cli, "Runner", RecordingRunner)

    exit_code = cli.main(
        [
            "run",
            "--config",
            "examples/run.openclaw.all.yaml",
            "examples/tasks/openclaw",
        ]
    )

    assert exit_code == 0
    assert seen["adapter"] == "openclaw"
    assert seen["task_ids"] == {
        "openclaw_smoke",
        "openclaw_skills_judge",
        "openclaw_skills_hybrid",
    }
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_openclaw_all_run_config_supports_expected_task_modes tests/test_openclaw_examples.py::test_cli_accepts_openclaw_all_directory -q`

预期：FAIL，报错指向 `examples/run.openclaw.all.yaml` 不存在。

- [ ] **步骤 3：编写最少实现代码**

创建 `examples/run.openclaw.all.yaml`：

```yaml
run:
  adapter: openclaw
  model: minimax/MiniMax-M2.7
  trials: 1
  parallelism: 1
  output_dir: runs
  workspace_policy: all
  adapter_config:
    openclaw_binary: openclaw
    session_artifact_timeout_seconds: 15
  judge:
    provider: openai
    model: gpt-4o-mini
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    temperature: 0
    timeout_seconds: 60
    max_tokens: 512
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_openclaw_examples.py::test_openclaw_all_run_config_supports_expected_task_modes tests/test_openclaw_examples.py::test_cli_accepts_openclaw_all_directory -q`

预期：`2 passed`。

---

### 任务 6：更新 README 中的 OpenClaw 示例入口

**文件：**
- 修改：`README.md`

- [ ] **步骤 1：编写失败的检查**

运行：

```bash
.venv/bin/python - <<'PY'
from pathlib import Path

readme = Path("README.md").read_text(encoding="utf-8")
required = [
    "examples/run.openclaw.judge.yaml",
    "examples/run.openclaw.hybrid.yaml",
    "examples/run.openclaw.all.yaml",
    "examples/tasks/openclaw",
]
missing = [item for item in required if item not in readme]
assert not missing, missing
PY
```

预期：FAIL，输出缺失的示例路径。

- [ ] **步骤 2：编写最少文档更新**

修改 `README.md` 的 OpenClaw 示例段落，保留现有 smoke 命令，并追加：

```md
如需查看 Judge 与 Hybrid 配置示例，可以运行：

```bash
agentbench run --config examples/run.openclaw.judge.yaml examples/tasks/openclaw/openclaw_skills_judge.yaml
agentbench run --config examples/run.openclaw.hybrid.yaml examples/tasks/openclaw/openclaw_skills_hybrid.yaml
agentbench run --config examples/run.openclaw.all.yaml examples/tasks/openclaw
```
```

- [ ] **步骤 3：运行检查验证通过**

重新运行步骤 1 的 Python 检查。

预期：PASS，无输出。

---

### 任务 7：更新 usage 文档中的 OpenClaw 示例说明

**文件：**
- 修改：`docs/usage.md`

- [ ] **步骤 1：编写失败的检查**

运行：

```bash
.venv/bin/python - <<'PY'
from pathlib import Path

usage = Path("docs/usage.md").read_text(encoding="utf-8")
required = [
    "examples/tasks/openclaw/",
    "examples/run.openclaw.judge.yaml",
    "examples/run.openclaw.hybrid.yaml",
    "examples/run.openclaw.all.yaml",
    "run.judge",
    "scoring.mode",
]
missing = [item for item in required if item not in usage]
assert not missing, missing
PY
```

预期：FAIL，输出缺失的说明关键词。

- [ ] **步骤 2：编写最少文档更新**

修改 `docs/usage.md` 的 OpenClaw E2E 示例部分，增加：

```md
如果想查看三种 OpenClaw 评分模式的完整示例，可以使用 `examples/tasks/openclaw/` 目录中的任务：

- `openclaw_smoke.yaml`：`rules`
- `openclaw_skills_judge.yaml`：`judge`
- `openclaw_skills_hybrid.yaml`：`hybrid`

对应运行命令：

```bash
agentbench run --config examples/run.openclaw.judge.yaml examples/tasks/openclaw/openclaw_skills_judge.yaml
agentbench run --config examples/run.openclaw.hybrid.yaml examples/tasks/openclaw/openclaw_skills_hybrid.yaml
agentbench run --config examples/run.openclaw.all.yaml examples/tasks/openclaw
```

说明：

- `run.judge` 负责配置 Judge 模型和 API 信息。
- task 中的 `scoring.mode`、`rules` 和 `judge_rubric` 负责定义具体评分方式。
```

- [ ] **步骤 3：运行检查验证通过**

重新运行步骤 1 的 Python 检查。

预期：PASS，无输出。

---

### 任务 8：运行回归并提交

**文件：**
- 创建：前述新增示例和测试文件
- 修改：`README.md`
- 修改：`docs/usage.md`

- [ ] **步骤 1：运行新增测试文件**

运行：

```bash
.venv/bin/pytest tests/test_openclaw_examples.py -q
```

预期：新增 OpenClaw 示例测试全部通过。

- [ ] **步骤 2：运行现有 CLI 测试**

运行：

```bash
.venv/bin/pytest tests/test_cli.py -q
```

预期：现有 CLI 测试全部通过。

- [ ] **步骤 3：运行示例加载检查**

运行：

```bash
.venv/bin/python - <<'PY'
from agentbench.cli import load_tasks_from_path
from agentbench.core.task import load_run_config

tasks = load_tasks_from_path("examples/tasks/openclaw")
config = load_run_config("examples/run.openclaw.all.yaml")

print({task.id: task.scoring.mode for task in tasks})
print(config.adapter, config.judge.provider if config.judge else None)
PY
```

预期：

```text
{'openclaw_skills_hybrid': 'hybrid', 'openclaw_skills_judge': 'judge', 'openclaw_smoke': 'rules'}
openclaw openai
```

- [ ] **步骤 4：检查工作区状态**

运行：

```bash
git status --short
```

预期：只看到本计划涉及的示例、文档和测试文件变更。

- [ ] **步骤 5：Commit**

```bash
git add examples README.md docs/usage.md tests/test_openclaw_examples.py
git commit -m "feat: add openclaw e2e example bundle"
```

---

## 自检

- **规格覆盖度：**
  - OpenClaw `judge` 示例：任务 2。
  - OpenClaw `hybrid` 示例：任务 3。
  - 复用 `rules` smoke 示例并纳入目录：任务 1。
  - 单任务 judge / hybrid run 配置：任务 4。
  - 多任务 run 配置和 CLI 目录路径：任务 5。
  - README / usage 轻量文档更新：任务 6、7。
  - 回归和最终提交：任务 8。
- **审查反馈处理：**
  - 红灯测试改为验证真实目标文件缺失，不再以“测试函数不存在”作为失败原因。
  - `judge_rubric` 断言与英文 YAML 内容保持一致。
  - 计划明确所有命令从 `agentbench/` 子项目根目录执行。
  - `load_run_config` 导入在测试步骤中先补齐，失败原因来自缺失配置文件。
  - 多任务能力增加 CLI 目录路径的轻量测试。
  - 文档检查保留为脚本级 sanity check，不再放入长期 pytest 回归。
  - 提交策略统一为最后一次 commit。
- **类型一致性：**
  - 任务 ID、文件名、run config 路径、`weights` 字段名、规则 ID 和文档中的命令保持一致：
    - `openclaw_smoke`
    - `openclaw_skills_judge`
    - `openclaw_skills_hybrid`
    - `examples/run.openclaw.judge.yaml`
    - `examples/run.openclaw.hybrid.yaml`
    - `examples/run.openclaw.all.yaml`

