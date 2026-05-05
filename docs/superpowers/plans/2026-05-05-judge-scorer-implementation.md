# Judge 评分模块实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现可调用 OpenAI-compatible 和 Anthropic Messages API 的 Judge 评分模块，支持 `.env`、完整执行上下文、有限指数退避重试和 run 级配置。

**架构：** Core 层只扩展 `JudgeConfig` 数据模型，不依赖供应商协议。`JudgeScorer` 负责上下文构造、provider 请求、响应规范化、错误转换和重试。CLI 在启动时加载当前工作目录 `.env`，并把 `RunConfig.judge` 注入 Judge / Hybrid 评分器。

**技术栈：** Python 3.11+、PyYAML、requests、pytest、标准库 dataclass / pathlib / os / time / json。

---

## 文件结构

- 修改：`pyproject.toml`
  - 增加运行时依赖 `requests>=2.32`。
- 创建：`src/agentbench/env.py`
  - 轻量 `.env` 加载器，只加载当前工作目录 `.env`，不覆盖已有环境变量。
- 修改：`src/agentbench/core/task.py`
  - 扩展 `JudgeConfig`，加载 run 级 Judge 配置和默认值。
- 修改：`src/agentbench/scorers/judge.py`
  - 实现 JudgeScorer 的配置校验、上下文构造、OpenAI / Anthropic 请求、响应解析、有限重试和 `scoring_error`。
- 修改：`src/agentbench/scorers/hybrid.py`
  - 默认 JudgeScorer 接收 `JudgeConfig`。
- 修改：`src/agentbench/cli.py`
  - CLI 启动时加载 `.env`，并根据 run 配置装配评分器。
- 修改：`docs/usage.md`
  - 增加 Judge 使用说明、`.env`、上下文和重试说明。
- 修改：`docs/development.md`
  - 增加 JudgeScorer 架构和 provider 开发说明。
- 创建：`tests/test_env.py`
  - 覆盖 `.env` 加载行为。
- 修改：`tests/test_task_config.py`
  - 覆盖 `JudgeConfig` 加载和默认值。
- 创建：`tests/test_judge_scorer.py`
  - 覆盖上下文构造、响应规范化、OpenAI / Anthropic 协议、错误路径和重试。
- 修改：`tests/test_cli.py`
  - 覆盖 CLI 评分器装配和 `.env` 调用。
- 修改：`tests/test_hybrid_scorer.py`
  - 覆盖配置后的默认 JudgeScorer。

---

### 任务 1：增加 requests 依赖

**文件：**
- 修改：`pyproject.toml`

- [ ] **步骤 1：编写失败的测试**

运行依赖导入检查：

```bash
.venv/bin/python - <<'PY'
import requests
print(requests.__version__)
PY
```

- [ ] **步骤 2：运行测试验证失败**

运行上面的命令。

预期：如果虚拟环境尚未安装 `requests`，失败并显示 `ModuleNotFoundError: No module named 'requests'`。如果环境已间接安装 `requests`，记录该情况，继续通过步骤 4 验证依赖声明。

- [ ] **步骤 3：编写最少实现代码**

修改 `pyproject.toml`：

```toml
dependencies = [
  "PyYAML>=6.0.1",
  "requests>=2.32",
]
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python - <<'PY'
import requests
print(requests.__version__)
PY
```

预期：成功输出 requests 版本。

- [ ] **步骤 5：Commit**

```bash
git add pyproject.toml
git commit -m "chore: add requests dependency"
```

---

### 任务 2：实现 `.env` 加载器

**文件：**
- 创建：`src/agentbench/env.py`
- 创建：`tests/test_env.py`

- [ ] **步骤 1：编写失败的测试**

创建 `tests/test_env.py`：

```python
import os
from pathlib import Path

from agentbench.env import load_dotenv


def test_load_dotenv_ignores_missing_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    loaded = load_dotenv()

    assert loaded == []


def test_load_dotenv_loads_values_without_overriding_existing_env(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXISTING_KEY", "from-env")
    (tmp_path / ".env").write_text(
        """
# comment
JUDGE_API_KEY=from-file
EXISTING_KEY=from-file
EMPTY_LINE_TEST=value

""",
        encoding="utf-8",
    )

    loaded = load_dotenv()

    assert loaded == ["JUDGE_API_KEY", "EMPTY_LINE_TEST"]
    assert os.environ["JUDGE_API_KEY"] == "from-file"
    assert os.environ["EXISTING_KEY"] == "from-env"
    assert os.environ["EMPTY_LINE_TEST"] == "value"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_env.py -q`

预期：FAIL，报错 `ModuleNotFoundError: No module named 'agentbench.env'`。

- [ ] **步骤 3：编写最少实现代码**

创建 `src/agentbench/env.py`：

```python
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> list[str]:
    """加载 .env 文件中的环境变量，不覆盖已存在的系统环境变量。"""
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return []

    loaded: list[str] = []
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_env.py -q`

预期：`2 passed`。

- [ ] **步骤 5：Commit**

```bash
git add src/agentbench/env.py tests/test_env.py
git commit -m "feat: load dotenv environment"
```

---

### 任务 3：扩展 JudgeConfig

**文件：**
- 修改：`src/agentbench/core/task.py`
- 修改：`tests/test_task_config.py`

- [ ] **步骤 1：编写失败的测试**

修改 `tests/test_task_config.py` 中既有 `test_load_run_config` 的 `judge` YAML：

```yaml
judge:
  provider: openai
  model: openrouter/anthropic/claude-haiku-4
  base_url: https://openrouter.ai/api/v1
  api_key_env: OPENROUTER_API_KEY
  temperature: 0.2
  timeout_seconds: 30
  max_tokens: 256
  max_context_chars: 10000
  max_tool_result_chars: 500
  max_workspace_file_chars: 1200
  max_retries: 3
  retry_backoff_seconds: 0.5
```

替换旧断言：

```python
assert config.judge is not None
assert config.judge.provider == "openai"
assert config.judge.model == "openrouter/anthropic/claude-haiku-4"
assert config.judge.base_url == "https://openrouter.ai/api/v1"
assert config.judge.api_key_env == "OPENROUTER_API_KEY"
assert config.judge.temperature == 0.2
assert config.judge.timeout_seconds == 30
assert config.judge.max_tokens == 256
assert config.judge.max_context_chars == 10000
assert config.judge.max_tool_result_chars == 500
assert config.judge.max_workspace_file_chars == 1200
assert config.judge.max_retries == 3
assert config.judge.retry_backoff_seconds == 0.5
```

追加默认值测试：

```python
def test_load_run_config_with_judge_defaults(tmp_path: Path):
    config_path = tmp_path / "run.yaml"
    config_path.write_text(
        """
run:
  adapter: fake
  model: fake
  judge:
    provider: anthropic
    model: claude-3-5-haiku-latest
""",
        encoding="utf-8",
    )

    config = load_run_config(config_path)

    assert config.judge is not None
    assert config.judge.provider == "anthropic"
    assert config.judge.base_url == "https://api.anthropic.com"
    assert config.judge.api_key_env == "ANTHROPIC_API_KEY"
    assert config.judge.temperature == 0.0
    assert config.judge.timeout_seconds == 60
    assert config.judge.max_tokens == 512
    assert config.judge.max_context_chars == 20000
    assert config.judge.max_tool_result_chars == 1000
    assert config.judge.max_workspace_file_chars == 3000
    assert config.judge.max_retries == 2
    assert config.judge.retry_backoff_seconds == 1.0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_task_config.py -q`

预期：FAIL，报错类似 `AttributeError: 'JudgeConfig' object has no attribute 'provider'`。

- [ ] **步骤 3：编写最少实现代码**

修改 `src/agentbench/core/task.py`：

```python
JudgeProvider = Literal["openai", "anthropic"]
```

替换 `JudgeConfig`：

```python
@dataclass(frozen=True)
class JudgeConfig:
    """Judge 评分器的运行配置。"""

    provider: JudgeProvider
    model: str
    base_url: str
    api_key_env: str
    temperature: float = 0.0
    timeout_seconds: int = 60
    max_tokens: int = 512
    max_context_chars: int = 20000
    max_tool_result_chars: int = 1000
    max_workspace_file_chars: int = 3000
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
```

新增：

```python
def _load_judge_config(raw: dict[str, Any] | None) -> JudgeConfig | None:
    if not raw:
        return None
    provider = str(raw["provider"])
    if provider == "openai":
        default_base_url = "https://api.openai.com/v1"
        default_api_key_env = "OPENAI_API_KEY"
    elif provider == "anthropic":
        default_base_url = "https://api.anthropic.com"
        default_api_key_env = "ANTHROPIC_API_KEY"
    else:
        default_base_url = str(raw.get("base_url", ""))
        default_api_key_env = str(raw.get("api_key_env", ""))
    return JudgeConfig(
        provider=provider,
        model=str(raw["model"]),
        base_url=str(raw.get("base_url", default_base_url)),
        api_key_env=str(raw.get("api_key_env", default_api_key_env)),
        temperature=float(raw.get("temperature", 0.0)),
        timeout_seconds=int(raw.get("timeout_seconds", 60)),
        max_tokens=int(raw.get("max_tokens", 512)),
        max_context_chars=int(raw.get("max_context_chars", 20000)),
        max_tool_result_chars=int(raw.get("max_tool_result_chars", 1000)),
        max_workspace_file_chars=int(raw.get("max_workspace_file_chars", 3000)),
        max_retries=int(raw.get("max_retries", 2)),
        retry_backoff_seconds=float(raw.get("retry_backoff_seconds", 1.0)),
    )
```

修改 `load_run_config()`：

```python
judge = _load_judge_config(run.get("judge"))
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_task_config.py -q`

预期：全部通过。

- [ ] **步骤 5：Commit**

```bash
git add src/agentbench/core/task.py tests/test_task_config.py
git commit -m "feat: extend Judge configuration"
```

---

### 任务 4：构造 Judge 输入上下文

**文件：**
- 修改：`src/agentbench/scorers/judge.py`
- 创建：`tests/test_judge_scorer.py`

- [ ] **步骤 1：编写失败的测试**

创建 `tests/test_judge_scorer.py`：

```python
import json
from pathlib import Path

from agentbench.core.result import AgentRunResult
from agentbench.core.task import JudgeConfig, ScoringSpec, TaskSpec
from agentbench.core.trace import Trace, TraceEvent
from agentbench.scorers.judge import JudgeScorer


def make_judge_config(**overrides) -> JudgeConfig:
    values = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.0,
        "timeout_seconds": 60,
        "max_tokens": 512,
        "max_context_chars": 20000,
        "max_tool_result_chars": 1000,
        "max_workspace_file_chars": 3000,
        "max_retries": 2,
        "retry_backoff_seconds": 1.0,
    }
    values.update(overrides)
    return JudgeConfig(**values)


def make_task() -> TaskSpec:
    return TaskSpec(
        id="judge-task",
        name="Judge Task",
        prompt="Write a concise summary.",
        timeout_seconds=30,
        pass_threshold=0.8,
        scoring=ScoringSpec(mode="judge", judge_rubric="Score accuracy and concision."),
    )


def make_run(tmp_path: Path, trace: Trace) -> AgentRunResult:
    return AgentRunResult(
        task_id="judge-task",
        trial_id=1,
        status="success",
        started_at="s",
        finished_at="f",
        duration_seconds=1.0,
        workspace_path=str(tmp_path),
        log_dir=str(tmp_path),
        stdout_path="stdout.log",
        stderr_path="stderr.log",
        trace_path="trace.json",
        adapter_log_path="adapter.log",
        trace=trace,
    )


def test_build_judge_prompt_includes_execution_trace_and_workspace_files(tmp_path: Path):
    (tmp_path / "summary.md").write_text("Final summary from workspace.", encoding="utf-8")
    (tmp_path / ".hidden").write_text("secret", encoding="utf-8")
    (tmp_path / "BOOTSTRAP.md").write_text("bootstrap", encoding="utf-8")
    trace = Trace(
        events=[
            TraceEvent(type="assistant_message", data={"text": "I will inspect the file."}),
            TraceEvent(type="tool_call", data={"tool": "read", "args": {"path": "report.txt", "query": "x" * 250}}),
            TraceEvent(type="tool_result", data={"content": "tool result " + "y" * 1200}),
            TraceEvent(type="file_event", data={"path": "summary.md", "event": "created"}),
            TraceEvent(type="error", data={"error": "minor warning"}),
        ]
    )
    scorer = JudgeScorer(make_judge_config(max_tool_result_chars=40, max_workspace_file_chars=20))

    prompt = scorer.build_prompt(make_task(), make_run(tmp_path, trace))

    assert "## Task" in prompt
    assert "Write a concise summary." in prompt
    assert "## Execution Status" in prompt
    assert "success" in prompt
    assert "Assistant: I will inspect the file." in prompt
    assert "Tool: read(" in prompt
    assert "...[truncated]" in prompt
    assert "Result: tool result" in prompt
    assert "File event:" in prompt
    assert "Error: minor warning" in prompt
    assert "### File: summary.md" in prompt
    assert "Final summary from wo" in prompt
    assert "secret" not in prompt
    assert "bootstrap" not in prompt
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_judge_scorer.py::test_build_judge_prompt_includes_execution_trace_and_workspace_files -q`

预期：FAIL，当前 `JudgeScorer` 没有 `build_prompt()` 或不包含完整上下文。

- [ ] **步骤 3：编写最少实现代码**

修改 `src/agentbench/scorers/judge.py`，先实现上下文构造，不实现 HTTP：

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import JudgeConfig, TaskSpec


class JudgeScorer:
    """通过外部 Judge 模型对 Agent 输出进行评分。"""

    def __init__(self, config: JudgeConfig | None = None) -> None:
        """初始化 Judge 配置。"""
        self.config = config

    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        """临时占位，后续任务实现 HTTP 调用。"""
        return self._error(task, run, "judge execution is not configured")

    def build_prompt(self, task: TaskSpec, run: AgentRunResult) -> str:
        """构造包含执行过程和工作区产物的 Judge prompt。"""
        transcript_summary = self._summarize_trace(run)
        workspace_content = self._read_workspace_files(Path(run.workspace_path))
        prompt = (
            "You are a grading function. Your ONLY job is to output a single JSON object.\n\n"
            "CRITICAL RULES:\n"
            "- Do NOT use tools.\n"
            "- Do NOT write prose outside JSON.\n"
            "- Be strict. Reserve 1.0 for genuinely excellent performance.\n\n"
            "## Task\n"
            f"Task ID: {task.id}\n"
            f"Task name: {task.name}\n"
            f"{task.prompt}\n\n"
            "## Execution Status\n"
            f"{run.status}\n\n"
            "## Agent Transcript Summary\n"
            f"{transcript_summary}\n\n"
            "## Workspace Files Created by Agent\n"
            f"{workspace_content}\n\n"
            "## Grading Rubric\n"
            f"{task.scoring.judge_rubric or ''}\n\n"
            "Respond with ONLY this JSON structure:\n"
            '{"scores": {"criterion_name": 0.0}, "total": 0.0, "notes": "brief justification"}'
        )
        return self._truncate(prompt, self._max_context_chars())

    def _summarize_trace(self, run: AgentRunResult) -> str:
        lines: list[str] = []
        for event in run.trace.events:
            if event.type == "assistant_message":
                text = str(event.data.get("text", "")).strip()
                if text:
                    lines.append(f"Assistant: {self._truncate(text, 2000)}")
            elif event.type == "tool_call":
                tool = str(event.data.get("tool", "unknown"))
                args = self._truncate_args(event.data.get("args", {}))
                lines.append(f"Tool: {tool}({json.dumps(args, ensure_ascii=False)})")
            elif event.type == "tool_result":
                content = event.data.get("content", event.data)
                lines.append(f"Result: {self._truncate(str(content), self._max_tool_result_chars())}")
            elif event.type == "file_event":
                lines.append(f"File event: {self._truncate(json.dumps(event.data, ensure_ascii=False), 1000)}")
            elif event.type == "error":
                lines.append(f"Error: {self._truncate(str(event.data.get('error', event.data)), 1000)}")
        return "\n".join(lines)

    def _truncate_args(self, args: Any) -> Any:
        if isinstance(args, dict):
            return {str(key): self._truncate(value, 200) if isinstance(value, str) else value for key, value in args.items()}
        return args

    def _read_workspace_files(self, workspace: Path) -> str:
        if not workspace.exists():
            return ""
        skip_names = {"BOOTSTRAP.md", "SOUL.md", "USER.md", "IDENTITY.md", "HEARTBEAT.md", "TOOLS.md", "AGENTS.md"}
        skip_dirs = {".git", ".openclaw", "__pycache__", "node_modules", "skills"}
        parts: list[str] = []
        for path in sorted(workspace.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(workspace)
            if path.name in skip_names:
                continue
            if any(part.startswith(".") or part in skip_dirs for part in rel.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            parts.append(f"### File: {rel}\n{self._truncate(text, self._max_workspace_file_chars())}")
        return "\n\n".join(parts)

    def _truncate(self, value: Any, limit: int) -> str:
        text = str(value)
        if len(text) <= limit:
            return text
        return text[:limit] + "...[truncated]"

    def _max_context_chars(self) -> int:
        return self.config.max_context_chars if self.config is not None else 20000

    def _max_tool_result_chars(self) -> int:
        return self.config.max_tool_result_chars if self.config is not None else 1000

    def _max_workspace_file_chars(self) -> int:
        return self.config.max_workspace_file_chars if self.config is not None else 3000

    def _error(self, task: TaskSpec, run: AgentRunResult, message: str) -> ScoreResult:
        return ScoreResult(task_id=task.id, trial_id=run.trial_id, status="scoring_error", score=0.0, passed=False, notes=message)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_judge_scorer.py::test_build_judge_prompt_includes_execution_trace_and_workspace_files -q`

预期：PASS。

- [ ] **步骤 5：Commit**

```bash
git add src/agentbench/scorers/judge.py tests/test_judge_scorer.py
git commit -m "feat: build Judge evaluation context"
```

---

### 任务 5：规范化 Judge 响应

**文件：**
- 修改：`src/agentbench/scorers/judge.py`
- 修改：`tests/test_judge_scorer.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_judge_scorer.py` 追加：

```python
def test_parse_judge_scores_total_notes(tmp_path: Path):
    scorer = JudgeScorer(make_judge_config())
    result = scorer.parse_judge_text(
        make_task(),
        make_run(tmp_path, Trace()),
        '{"scores": {"accuracy": 0.8, "style": 1.0}, "total": 0.9, "notes": "good"}',
    )

    assert result.status == "scored"
    assert result.score == 0.9
    assert result.passed is True
    assert result.notes == "good"
    assert [item.id for item in result.breakdown] == ["accuracy", "style"]


def test_parse_judge_simplified_score_reason(tmp_path: Path):
    scorer = JudgeScorer(make_judge_config())
    result = scorer.parse_judge_text(make_task(), make_run(tmp_path, Trace()), '{"score": 0.7, "reason": "ok"}')

    assert result.status == "scored"
    assert result.score == 0.7
    assert result.passed is False
    assert result.notes == "ok"


def test_parse_judge_invalid_output_is_scoring_error(tmp_path: Path):
    scorer = JudgeScorer(make_judge_config())
    result = scorer.parse_judge_text(make_task(), make_run(tmp_path, Trace()), "not json")

    assert result.status == "scoring_error"
    assert result.score == 0.0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_judge_scorer.py -q`

预期：FAIL，`parse_judge_text()` 不存在。

- [ ] **步骤 3：编写最少实现代码**

在 `src/agentbench/scorers/judge.py` 增加：

```python
from agentbench.core.result import AgentRunResult, CheckResult, ScoreResult
```

新增方法：

```python
def parse_judge_text(self, task: TaskSpec, run: AgentRunResult, text: str) -> ScoreResult:
    """解析 Judge JSON 文本并转换为 ScoreResult。"""
    try:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            return self._error(task, run, "judge output is not a JSON object")
        score = self._extract_total(payload)
        if score is None:
            return self._error(task, run, "judge total score missing")
        if score < 0.0 or score > 1.0:
            return self._error(task, run, f"judge score out of range: {score}")
        scores = payload.get("scores", {})
        breakdown = []
        if isinstance(scores, dict):
            for key, value in scores.items():
                try:
                    item_score = float(value)
                except (TypeError, ValueError):
                    continue
                breakdown.append(
                    CheckResult(id=str(key), score=item_score, points=1.0, passed=item_score >= task.pass_threshold, detail="")
                )
        notes = str(payload.get("notes", payload.get("reason", "")))
        return ScoreResult(
            task_id=task.id,
            trial_id=run.trial_id,
            status="scored",
            score=score,
            passed=score >= task.pass_threshold,
            breakdown=breakdown,
            notes=notes,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return self._error(task, run, str(exc))

def _extract_total(self, payload: dict[str, Any]) -> float | None:
    for key in ("total", "score", "overall_score", "total_score"):
        if key in payload:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                return None
    return None
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_judge_scorer.py -q`

预期：全部通过。

- [ ] **步骤 5：Commit**

```bash
git add src/agentbench/scorers/judge.py tests/test_judge_scorer.py
git commit -m "feat: parse Judge score responses"
```

---

### 任务 6：实现 OpenAI-compatible provider

**文件：**
- 修改：`src/agentbench/scorers/judge.py`
- 修改：`tests/test_judge_scorer.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_judge_scorer.py` 增加：

```python
import requests


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_openai_judge_request_and_response(monkeypatch, tmp_path: Path):
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        seen["timeout"] = timeout
        return FakeResponse(200, {"choices": [{"message": {"content": '{"total": 0.9, "notes": "accurate"}'}}]})

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(requests, "post", fake_post)
    scorer = JudgeScorer(make_judge_config(temperature=0.2, timeout_seconds=30, max_tokens=256))

    result = scorer.score(make_task(), make_run(tmp_path, Trace()))

    assert result.status == "scored"
    assert result.score == 0.9
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["json"]["model"] == "gpt-4o-mini"
    assert seen["json"]["temperature"] == 0.2
    assert seen["json"]["max_tokens"] == 256
    assert seen["json"]["response_format"] == {"type": "json_object"}
    assert seen["timeout"] == 30
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_judge_scorer.py::test_openai_judge_request_and_response -q`

预期：FAIL，`score()` 仍返回 `scoring_error` 占位。

- [ ] **步骤 3：编写最少实现代码**

修改 `src/agentbench/scorers/judge.py`：

```python
import os
import requests
```

把 `score()` 改为：

```python
def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
    """调用 Judge API 并转换为 ScoreResult。"""
    if self.config is None:
        return self._error(task, run, "judge config missing")
    if not task.scoring.judge_rubric:
        return self._error(task, run, "judge_rubric missing")
    validation_error = self._validate_config()
    if validation_error:
        return self._error(task, run, validation_error)
    api_key = os.environ.get(self.config.api_key_env)
    if not api_key:
        return self._error(task, run, f"environment variable {self.config.api_key_env} is missing")
    try:
        text = self._call_openai(task, run, api_key)
    except Exception as exc:
        return self._error(task, run, str(exc))
    return self.parse_judge_text(task, run, text)
```

新增：

```python
def _call_openai(self, task: TaskSpec, run: AgentRunResult, api_key: str) -> str:
    assert self.config is not None
    response = requests.post(
        self.config.base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You are an impartial evaluator. Return only JSON."},
                {"role": "user", "content": self.build_prompt(task, run)},
            ],
        },
        timeout=self.config.timeout_seconds,
    )
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(f"judge http error {response.status_code}: {response.text}")
    payload = response.json()
    return str(payload["choices"][0]["message"]["content"])

def _validate_config(self) -> str | None:
    assert self.config is not None
    if self.config.provider not in {"openai", "anthropic"}:
        return f"unsupported judge provider: {self.config.provider}"
    if not self.config.model:
        return "judge model missing"
    if self.config.temperature < 0.0 or self.config.temperature > 2.0:
        return f"judge temperature out of range: {self.config.temperature}"
    for name in ("timeout_seconds", "max_tokens", "max_context_chars", "max_tool_result_chars", "max_workspace_file_chars"):
        if getattr(self.config, name) <= 0:
            return f"judge {name} must be positive"
    if self.config.max_retries < 1 or self.config.max_retries > 5:
        return "judge max_retries must be between 1 and 5"
    if self.config.retry_backoff_seconds <= 0:
        return "judge retry_backoff_seconds must be positive"
    return None
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_judge_scorer.py -q`

预期：全部通过。

- [ ] **步骤 5：Commit**

```bash
git add src/agentbench/scorers/judge.py tests/test_judge_scorer.py
git commit -m "feat: score Judge tasks via OpenAI protocol"
```

---

### 任务 7：实现 Anthropic provider

**文件：**
- 修改：`src/agentbench/scorers/judge.py`
- 修改：`tests/test_judge_scorer.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_judge_scorer.py` 追加：

```python
def test_anthropic_judge_request_and_response(monkeypatch, tmp_path: Path):
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        seen["timeout"] = timeout
        return FakeResponse(200, {"content": [{"type": "text", "text": '{"total": 0.75, "notes": "mostly good"}'}]})

    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setattr(requests, "post", fake_post)
    scorer = JudgeScorer(
        make_judge_config(
            provider="anthropic",
            model="claude-3-5-haiku-latest",
            base_url="https://api.anthropic.com",
            api_key_env="ANTHROPIC_API_KEY",
            timeout_seconds=40,
            max_tokens=300,
        )
    )

    result = scorer.score(make_task(), make_run(tmp_path, Trace()))

    assert result.status == "scored"
    assert result.score == 0.75
    assert result.passed is False
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "anthropic-key"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["json"]["model"] == "claude-3-5-haiku-latest"
    assert seen["json"]["max_tokens"] == 300
    assert "system" in seen["json"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_judge_scorer.py::test_anthropic_judge_request_and_response -q`

预期：FAIL，当前 provider 分支仍只调用 OpenAI。

- [ ] **步骤 3：编写最少实现代码**

修改 `score()` 调用分支：

```python
try:
    if self.config.provider == "openai":
        text = self._call_openai(task, run, api_key)
    elif self.config.provider == "anthropic":
        text = self._call_anthropic(task, run, api_key)
    else:
        return self._error(task, run, f"unsupported judge provider: {self.config.provider}")
except Exception as exc:
    return self._error(task, run, str(exc))
```

新增：

```python
def _call_anthropic(self, task: TaskSpec, run: AgentRunResult, api_key: str) -> str:
    assert self.config is not None
    response = requests.post(
        self.config.base_url.rstrip("/") + "/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "system": "You are an impartial evaluator. Return only JSON.",
            "messages": [{"role": "user", "content": self.build_prompt(task, run)}],
        },
        timeout=self.config.timeout_seconds,
    )
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(f"judge http error {response.status_code}: {response.text}")
    payload = response.json()
    return "".join(
        str(item.get("text", "")) for item in payload["content"] if isinstance(item, dict) and item.get("type") == "text"
    )
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_judge_scorer.py -q`

预期：全部通过。

- [ ] **步骤 5：Commit**

```bash
git add src/agentbench/scorers/judge.py tests/test_judge_scorer.py
git commit -m "feat: score Judge tasks via Anthropic protocol"
```

---

### 任务 8：实现有限指数退避重试

**文件：**
- 修改：`src/agentbench/scorers/judge.py`
- 修改：`tests/test_judge_scorer.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_judge_scorer.py` 追加：

```python
def test_judge_retries_429_with_exponential_backoff(monkeypatch, tmp_path: Path):
    calls = []
    sleeps = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        if len(calls) == 1:
            return FakeResponse(429, {"error": "rate limited"})
        return FakeResponse(200, {"choices": [{"message": {"content": '{"total": 0.9, "notes": "ok"}'}}]})

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr("agentbench.scorers.judge.time.sleep", lambda seconds: sleeps.append(seconds))
    scorer = JudgeScorer(make_judge_config(max_retries=2, retry_backoff_seconds=0.5))

    result = scorer.score(make_task(), make_run(tmp_path, Trace()))

    assert result.status == "scored"
    assert len(calls) == 2
    assert sleeps == [0.5]


def test_judge_does_not_retry_non_429_4xx(monkeypatch, tmp_path: Path):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        return FakeResponse(400, {"error": "bad request"})

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(requests, "post", fake_post)
    scorer = JudgeScorer(make_judge_config(max_retries=3))

    result = scorer.score(make_task(), make_run(tmp_path, Trace()))

    assert result.status == "scoring_error"
    assert len(calls) == 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_judge_scorer.py -q`

预期：FAIL，当前实现不会重试 `429`。

- [ ] **步骤 3：编写最少实现代码**

在 `src/agentbench/scorers/judge.py` 增加：

```python
import time
```

新增：

```python
class RetryableJudgeError(RuntimeError):
    """表示 Judge API 请求可以重试。"""
```

修改 `_call_openai()` 和 `_call_anthropic()` 的 HTTP 错误处理：

```python
if response.status_code == 429 or response.status_code >= 500:
    raise RetryableJudgeError(f"judge http error {response.status_code}: {response.text}")
if response.status_code < 200 or response.status_code >= 300:
    raise RuntimeError(f"judge http error {response.status_code}: {response.text}")
```

新增：

```python
def _call_with_retries(self, task: TaskSpec, run: AgentRunResult, api_key: str) -> str:
    assert self.config is not None
    last_error: Exception | None = None
    for attempt in range(1, self.config.max_retries + 1):
        try:
            if self.config.provider == "openai":
                return self._call_openai(task, run, api_key)
            if self.config.provider == "anthropic":
                return self._call_anthropic(task, run, api_key)
            raise RuntimeError(f"unsupported judge provider: {self.config.provider}")
        except (RetryableJudgeError, requests.RequestException) as exc:
            last_error = exc
            if attempt >= self.config.max_retries:
                break
            time.sleep(self.config.retry_backoff_seconds * (2 ** (attempt - 1)))
    raise RuntimeError(f"judge request failed after {self.config.max_retries} attempts: {last_error}")
```

修改 `score()`：

```python
text = self._call_with_retries(task, run, api_key)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_judge_scorer.py -q`

预期：全部通过。

- [ ] **步骤 5：Commit**

```bash
git add src/agentbench/scorers/judge.py tests/test_judge_scorer.py
git commit -m "feat: retry Judge API with backoff"
```

---

### 任务 9：补齐 Judge 错误路径

**文件：**
- 修改：`src/agentbench/scorers/judge.py`
- 修改：`tests/test_judge_scorer.py`

- [ ] **步骤 1：编写失败的测试**

在 `tests/test_judge_scorer.py` 追加：

```python
def test_judge_missing_api_key_is_scoring_error(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    scorer = JudgeScorer(make_judge_config())

    result = scorer.score(make_task(), make_run(tmp_path, Trace()))

    assert result.status == "scoring_error"
    assert "OPENAI_API_KEY" in result.notes


def test_judge_invalid_temperature_is_scoring_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    scorer = JudgeScorer(make_judge_config(temperature=3.0))

    result = scorer.score(make_task(), make_run(tmp_path, Trace()))

    assert result.status == "scoring_error"
    assert "temperature" in result.notes


def test_judge_invalid_retry_config_is_scoring_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    scorer = JudgeScorer(make_judge_config(max_retries=6))

    result = scorer.score(make_task(), make_run(tmp_path, Trace()))

    assert result.status == "scoring_error"
    assert "max_retries" in result.notes
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/bin/pytest tests/test_judge_scorer.py -q`

预期：FAIL，至少一个错误路径未被稳定转换为 `scoring_error`。

- [ ] **步骤 3：编写最少实现代码**

确认 `_validate_config()` 覆盖：

```python
if self.config.max_retries < 1 or self.config.max_retries > 5:
    return "judge max_retries must be between 1 and 5"
if self.config.retry_backoff_seconds <= 0:
    return "judge retry_backoff_seconds must be positive"
```

确认 `score()` 对缺 key、配置错误、调用异常都返回 `_error()`，不抛出异常。

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/bin/pytest tests/test_judge_scorer.py -q`

预期：全部通过。

- [ ] **步骤 5：Commit**

```bash
git add src/agentbench/scorers/judge.py tests/test_judge_scorer.py
git commit -m "fix: report Judge scoring errors"
```

---

### 任务 10：CLI 装配 `.env` 和 JudgeScorer

**文件：**
- 修改：`src/agentbench/cli.py`
- 修改：`src/agentbench/scorers/hybrid.py`
- 修改：`tests/test_cli.py`
- 修改：`tests/test_hybrid_scorer.py`

- [ ] **步骤 1：编写失败的测试**

修改 `tests/test_cli.py` 导入：

```python
from agentbench.cli import build_agent_loop, load_tasks_from_path, main, select_scorer
from agentbench.core.task import JudgeConfig
from agentbench.scorers.judge import JudgeScorer
```

追加：

```python
def test_select_scorer_builds_configured_judge_scorer():
    task = TaskSpec(
        id="j",
        name="J",
        prompt="p",
        timeout_seconds=1,
        scoring=ScoringSpec(mode="judge", judge_rubric="score it"),
    )
    judge = JudgeConfig(
        provider="openai",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
    )

    scorer = select_scorer([task], judge)

    assert isinstance(scorer, JudgeScorer)
    assert scorer.config == judge


def test_main_loads_dotenv_before_running(monkeypatch):
    called = []

    def fake_load_dotenv():
        called.append("dotenv")
        return []

    def fake_run(self, tasks):
        called.append("run")
        return {"run_dir": "runs/fake"}

    monkeypatch.setattr("agentbench.cli.load_dotenv", fake_load_dotenv)
    monkeypatch.setattr("agentbench.cli.Runner.run", fake_run)

    assert main(["run", "--config", "examples/run.fake.yaml", "examples/tasks"]) == 0
    assert called == ["dotenv", "run"]
```

修改既有调用：

```python
assert isinstance(select_scorer([rules_task], None), RuleScorer)
assert isinstance(select_scorer([hybrid_task], None), HybridScorer)
```

在 `tests/test_hybrid_scorer.py` 追加：

```python
from agentbench.core.task import JudgeConfig
from agentbench.scorers.judge import JudgeScorer


def test_hybrid_default_judge_scorer_uses_config():
    judge = JudgeConfig(
        provider="openai",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
    )

    scorer = HybridScorer(judge_config=judge)

    assert isinstance(scorer.judge_scorer, JudgeScorer)
    assert scorer.judge_scorer.config == judge
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
.venv/bin/pytest tests/test_cli.py tests/test_hybrid_scorer.py -q
```

预期：FAIL，`select_scorer()` 和 `HybridScorer` 尚不支持 JudgeConfig。

- [ ] **步骤 3：编写最少实现代码**

修改 `src/agentbench/scorers/hybrid.py`：

```python
from agentbench.core.task import JudgeConfig, TaskSpec
```

构造函数改为：

```python
def __init__(
    self,
    rule_scorer: Scorer | None = None,
    judge_scorer: Scorer | None = None,
    judge_config: JudgeConfig | None = None,
) -> None:
    self.rule_scorer = rule_scorer or RuleScorer()
    self.judge_scorer = judge_scorer or JudgeScorer(judge_config)
```

修改 `src/agentbench/cli.py`：

```python
from agentbench.env import load_dotenv
from agentbench.scorers.judge import JudgeScorer
```

修改 `select_scorer`：

```python
def select_scorer(tasks: list[TaskSpec], judge_config=None):
    modes = {task.scoring.mode for task in tasks}
    if "hybrid" in modes:
        return HybridScorer(judge_config=judge_config)
    if "judge" in modes:
        return JudgeScorer(judge_config)
    return RuleScorer()
```

修改 `main()`：

```python
if args.command == "run":
    load_dotenv()
    config = load_run_config(args.config)
    tasks = load_tasks_from_path(args.tasks)
    runner = Runner(config=config, agent_loop=build_agent_loop(config), scorer=select_scorer(tasks, config.judge))
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
.venv/bin/pytest tests/test_cli.py tests/test_hybrid_scorer.py -q
```

预期：全部通过。

- [ ] **步骤 5：Commit**

```bash
git add src/agentbench/cli.py src/agentbench/scorers/hybrid.py tests/test_cli.py tests/test_hybrid_scorer.py
git commit -m "feat: wire Judge scorer into CLI"
```

---

### 任务 11：补充 Judge 文档

**文件：**
- 修改：`docs/usage.md`
- 修改：`docs/development.md`

- [ ] **步骤 1：编写失败的检查**

运行：

```bash
rg -n "run\\.judge|OPENAI_API_KEY|ANTHROPIC_API_KEY|max_context_chars|max_retries|retry_backoff_seconds|JudgeScorer" docs/usage.md docs/development.md
```

- [ ] **步骤 2：运行检查验证失败**

预期：当前文档没有完整覆盖 Judge 配置、上下文预算和重试字段。

- [ ] **步骤 3：编写最少文档**

在 `docs/usage.md` 增加「使用 Judge 评分」章节，包含：

```markdown
## 使用 Judge 评分

Judge 评分通过 run 级 `judge` 配置调用外部模型。任务 YAML 只声明 `scoring.mode: judge` 和 `judge_rubric`。

### `.env`

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### OpenAI-compatible 配置

```yaml
run:
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

Judge 输入会包含执行状态、assistant 文本、tool call、tool result、file event、error 和 workspace 文本文件预览。大型内容会按配置截断。

Judge API 会对网络异常、超时、HTTP `429` 和 HTTP `5xx` 做有限次数指数退避重试，不会重新执行 Agent trial。
```

在 `docs/development.md` 增加「JudgeScorer 开发说明」章节，说明 provider 边界、上下文构造和测试要求。

- [ ] **步骤 4：运行检查验证通过**

运行：

```bash
rg -n "run\\.judge|OPENAI_API_KEY|ANTHROPIC_API_KEY|max_context_chars|max_retries|retry_backoff_seconds|JudgeScorer" docs/usage.md docs/development.md
git diff --check
```

预期：`rg` 能找到新增内容，`git diff --check` 无输出。

- [ ] **步骤 5：Commit**

```bash
git add docs/usage.md docs/development.md
git commit -m "docs: document Judge scoring"
```

---

### 任务 12：全量验证和推送

**文件：**
- 无新增代码文件；验证整个工作区。

- [ ] **步骤 1：运行全量测试**

运行：

```bash
.venv/bin/pytest -q
```

预期：所有测试通过。

- [ ] **步骤 2：运行 fake 示例 smoke**

运行：

```bash
.venv/bin/agentbench run --config examples/run.fake.yaml examples/tasks
```

预期：命令成功输出 `runs/...`。

- [ ] **步骤 3：检查工作树和提交历史**

运行：

```bash
git status --short --branch
git log --oneline --decorate -12
```

预期：工作树干净，最新提交包含本计划所有任务提交。

- [ ] **步骤 4：推送**

运行：

```bash
git push
```

预期：远程 `main` 更新成功。

- [ ] **步骤 5：记录验证结果**

最终回复中列出：

```text
pytest -q: <通过数量>
fake example run: <run_dir>
latest commit: <hash>
```

