from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentbench.core.result import AgentRunResult, CheckResult, ScoreResult
from agentbench.core.task import RuleSpec, TaskSpec


class RuleScorer:
    """基于任务 YAML 中 rules 配置的确定性评分器。"""

    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        """执行所有规则，并把规则异常汇总为 scoring_error。"""
        checks = [self._score_rule(rule, run) for rule in task.scoring.rules]
        errors = [check.detail for check in checks if check.detail.startswith("scoring_error: ")]
        if errors:
            return ScoreResult(
                task_id=task.id,
                trial_id=run.trial_id,
                status="scoring_error",
                score=0.0,
                passed=False,
                breakdown=checks,
                notes="; ".join(errors),
            )
        total_points = sum(check.points for check in checks)
        earned = sum(check.points * check.score for check in checks)
        score = round(earned / total_points, 4) if total_points else 0.0
        return ScoreResult(
            task_id=task.id,
            trial_id=run.trial_id,
            status="scored",
            score=score,
            passed=score >= task.pass_threshold,
            breakdown=checks,
        )

    def _score_rule(self, rule: RuleSpec, run: AgentRunResult) -> CheckResult:
        """执行单条规则，捕获异常并转成 CheckResult。"""
        try:
            matched, detail = self._evaluate(rule, run)
            return CheckResult(
                id=rule.id,
                score=1.0 if matched else 0.0,
                points=rule.points,
                passed=matched,
                detail=detail,
            )
        except Exception as exc:
            return CheckResult(id=rule.id, score=0.0, points=rule.points, passed=False, detail=f"scoring_error: {exc}")

    def _evaluate(self, rule: RuleSpec, run: AgentRunResult) -> tuple[bool, str]:
        """根据规则类型执行实际匹配逻辑。"""
        params = rule.params
        workspace = Path(run.workspace_path)
        if rule.type == "file_exists":
            path = workspace / params["path"]
            return path.exists(), f"path={path}"
        if rule.type in {"file_contains", "file_not_contains"}:
            path = workspace / params["path"]
            text = path.read_text(encoding="utf-8")
            patterns = _patterns(params)
            contains = all(pattern.lower() in text.lower() for pattern in patterns)
            matched = contains if rule.type == "file_contains" else not contains
            return matched, f"path={path} patterns={patterns}"
        if rule.type in {"response_contains", "response_not_contains"}:
            text = "\n".join(
                str(event.data.get("text", "")) for event in run.trace.events if event.type == "assistant_message"
            )
            patterns = _patterns(params)
            contains = all(pattern.lower() in text.lower() for pattern in patterns)
            matched = contains if rule.type == "response_contains" else not contains
            return matched, f"patterns={patterns}"
        if rule.type in {"tool_called", "tool_not_called"}:
            tool = str(params["tool"])
            count = sum(1 for event in run.trace.events if event.type == "tool_call" and event.data.get("tool") == tool)
            matched = count > 0 if rule.type == "tool_called" else count == 0
            return matched, f"tool={tool} count={count}"
        if rule.type == "tool_arg_contains":
            tool = str(params["tool"])
            pattern = str(params["pattern"]).lower()
            for event in run.trace.events:
                if event.type == "tool_call" and event.data.get("tool") == tool:
                    args_text = json.dumps(event.data.get("args", {}), ensure_ascii=False).lower()
                    if pattern in args_text:
                        return True, f"tool={tool} pattern={pattern}"
            return False, f"tool={tool} pattern={pattern}"
        raise ValueError(f"unsupported rule type: {rule.type}")


def _patterns(params: dict[str, Any]) -> list[str]:
    """兼容 pattern 和 patterns 两种规则参数写法。"""
    if "patterns" in params:
        return [str(item) for item in params["patterns"]]
    return [str(params["pattern"])]
