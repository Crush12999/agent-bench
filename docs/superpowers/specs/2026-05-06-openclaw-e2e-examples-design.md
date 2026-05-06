# AgentBench OpenClaw E2E 示例设计

## 背景

`agentbench` 当前已经具备以下基础能力：

- `openclaw` adapter，可通过 OpenClaw CLI 执行端到端任务。
- `rules`、`judge`、`hybrid` 三种评分模式。
- 一个现有的 OpenClaw smoke 示例：`examples/run.openclaw.yaml` + `examples/tasks/openclaw_smoke.yaml`。

当前缺口不是评分器或 adapter 能力不足，而是缺少一组清楚展示 OpenClaw 端到端评测方式的示例，尤其是：

- 如何编写 `judge` 任务。
- 如何编写 `hybrid` 任务。
- 如何一次运行多个 OpenClaw 任务，体现 AgentBench 的多任务能力。

本设计只覆盖示例资产和相关轻量文档调整，不扩展运行时能力。

## 目标

- 新增一个基于 OpenClaw `skills` surface 的 `judge` 端到端示例。
- 新增一个基于 OpenClaw `skills` surface 的 `hybrid` 端到端示例。
- 保留并复用现有 `rules` smoke 示例，作为 OpenClaw 三种评分模式中的规则示例。
- 新增一个可一次运行 `rules`、`judge`、`hybrid` 三个 OpenClaw 任务的 run 配置。
- 让用户通过示例直接理解：
  - run 级 Judge 配置放在哪里；
  - task 级 scoring 配置放在哪里；
  - 单任务运行和多任务目录运行分别怎么用。

## 非目标

- 不修改 `JudgeScorer`、`HybridScorer` 或 `RuleScorer` 的实现。
- 不扩展 task schema。
- 不新增 custom scorer、custom check 或新的 CLI 参数。
- 不引入新的 fixture 数据集，除非示例实现被现有结构阻塞。
- 不把 OpenClaw `skills list --json` 的完整输出 schema 固化为严格 contract。
- 不新增 leaderboard、报告 UI 或批量调度能力。

## 设计原则

- **示例先可运行。** 优先让用户复制命令即可跑通，而不是追求任务复杂度。
- **OpenClaw 味道要明确。** 任务需显式依赖 OpenClaw 原生 surface，而不是纯通用文件题。
- **差异要易懂。** `judge` 和 `hybrid` 两个示例应体现不同评分模式的长处。
- **避免过度设计。** 示例只展示最小必要配置，不为未来可能需求预埋抽象。

## 文件结构

为了把 OpenClaw 专用任务与其他示例隔离，新增一个独立任务目录：

```text
agentbench/examples/
├── run.openclaw.yaml
├── run.openclaw.judge.yaml
├── run.openclaw.hybrid.yaml
├── run.openclaw.all.yaml
└── tasks/
    ├── openclaw_smoke.yaml
    └── openclaw/
        ├── openclaw_smoke.yaml
        ├── openclaw_skills_judge.yaml
        └── openclaw_skills_hybrid.yaml
```

说明：

- 现有 `examples/tasks/openclaw_smoke.yaml` 保留不动，避免破坏已有引用。
- 新增 `examples/tasks/openclaw/` 目录，用于承载 OpenClaw 专用任务 bundle。
- `examples/tasks/openclaw/openclaw_smoke.yaml` 复用现有 smoke 任务内容，作为多任务目录运行中的 `rules` 示例。
- 新增三份 run 配置：
  - `run.openclaw.judge.yaml`
  - `run.openclaw.hybrid.yaml`
  - `run.openclaw.all.yaml`

## 任务设计

### 1. Rules 任务

任务文件：

- `examples/tasks/openclaw/openclaw_smoke.yaml`

设计：

- 直接复用现有 smoke case 的任务语义。
- 保持它作为最简单、最稳定的 OpenClaw 规则评分示例。
- 任务要求 Agent 在工作区创建 `summary.md`，并写入固定句子。

原因：

- 这是最容易跑通的 OpenClaw E2E 示例。
- 作为 `all` 配置中的规则任务，它能与后续两个更开放的任务形成对比。

### 2. Judge 任务

任务文件：

- `examples/tasks/openclaw/openclaw_skills_judge.yaml`

任务目标：

- 使用 `openclaw skills list --json` 获取本机 skills 状态。
- 基于命令输出创建 `skills_assessment.md`。

任务要求：

- 将 `openclaw skills list --json` 作为主要事实来源。
- 产出一份简短分析文档，包含：
  - 概览；
  - 2-4 条观察；
  - 1-2 条对新用户的使用建议。
- 不要臆测未从命令输出中观察到的信息。

设计意图：

- 该任务主要依赖 Judge 对“是否忠于事实、总结是否清楚、建议是否合理”的判断。
- 不使用规则评分，避免把 `judge` 示例做成伪 `hybrid`。

### 3. Hybrid 任务

任务文件：

- `examples/tasks/openclaw/openclaw_skills_hybrid.yaml`

任务目标：

- 使用 `openclaw skills list --json` 获取本机 skills 状态。
- 创建两个产物：
  - `skills_inventory.json`
  - `skills_remediation.md`

任务要求：

- 从 `openclaw skills list --json` 中提取最小结构化 inventory，写入 JSON 文件。
- 在 Markdown 文档中说明：
  - 当前可直接使用的 skills 类型；
  - 可能存在的缺口或限制；
  - 给新用户的下一步建议。
- 遇到不明确状态时，明确写出不确定，而不是推断。

设计意图：

- `skills_inventory.json` 适合规则评分做最小硬约束校验。
- `skills_remediation.md` 适合 Judge 评估解释质量和建议质量。
- 该任务清楚展示 `hybrid = rules + judge` 的组合价值。

## 评分设计

### Judge 示例评分

配置：

- `scoring.mode: judge`
- 不配置 `rules`
- 通过 `judge_rubric` 约束评分标准

Judge rubric 应聚焦以下维度：

- 是否以 `openclaw skills list --json` 输出为事实基础。
- 是否避免编造 skills、状态或能力。
- 是否把关键信息总结清楚。
- 建议是否克制、具体且对新用户有帮助。

通过阈值建议：

- `pass_threshold: 0.75`

理由：

- 该任务完全依赖 Judge 判断，应让高分语义足够严格。

### Hybrid 示例评分

配置：

- `scoring.mode: hybrid`
- `weights.rules: 0.6`
- `weights.judge: 0.4`

规则评分建议使用最小必要集合：

1. `skills_inventory.json` 存在。
2. `skills_remediation.md` 存在。
3. `skills_inventory.json` 包含约定字段，例如 `generated_from` 或 `skills`。
4. `skills_remediation.md` 包含固定小节标题：
   - `## Available Skills`
   - `## Gaps Or Limits`
   - `## Next Steps`

Judge rubric 应聚焦以下维度：

- 结构化 inventory 是否与观察一致。
- remediation 文档是否忠于命令输出。
- 不确定信息是否被明确标注。
- 建议是否按先事实、后建议的顺序组织。

通过阈值建议：

- `pass_threshold: 0.7`

理由：

- 规则评分已经提供最基本兜底，整体阈值可略低于纯 Judge 示例。

## Run 配置设计

### 1. `run.openclaw.judge.yaml`

用途：

- 单独运行 `openclaw_skills_judge.yaml`

特点：

- 包含完整 `run.judge` 配置。
- 其他字段与现有 `run.openclaw.yaml` 保持一致或尽量接近。

### 2. `run.openclaw.hybrid.yaml`

用途：

- 单独运行 `openclaw_skills_hybrid.yaml`

特点：

- 同样包含完整 `run.judge` 配置。
- 说明 `hybrid` 任务也需要 run 级 Judge 配置。

### 3. `run.openclaw.all.yaml`

用途：

- 运行整个 `examples/tasks/openclaw/` 目录，体现多任务能力。

特点：

- 配置上与前两者保持同构，包含 Judge 配置。
- 通过目录输入一次执行三个任务：
  - `openclaw_smoke.yaml`
  - `openclaw_skills_judge.yaml`
  - `openclaw_skills_hybrid.yaml`

## 运行体验

目标命令应清晰直接：

```bash
agentbench run --config examples/run.openclaw.judge.yaml examples/tasks/openclaw/openclaw_skills_judge.yaml
```

```bash
agentbench run --config examples/run.openclaw.hybrid.yaml examples/tasks/openclaw/openclaw_skills_hybrid.yaml
```

```bash
agentbench run --config examples/run.openclaw.all.yaml examples/tasks/openclaw
```

用户应能通过这三条命令理解：

- 如何跑单任务 `judge` 示例；
- 如何跑单任务 `hybrid` 示例；
- 如何让 AgentBench 一次跑多个 OpenClaw 任务。

## 文档调整

本设计允许做最小必要的文档更新，但不要求重写文档体系。推荐更新范围：

- `README.md`
- `docs/usage.md`

更新内容只需覆盖：

- 新增 Judge / Hybrid OpenClaw 示例的位置；
- 单任务运行命令；
- 多任务目录运行命令；
- `run.judge` 与 task `scoring` 的分工。

## 验证标准

本设计完成后的成功标准：

1. 仓库中存在两个新的 OpenClaw E2E 任务示例和三个对应 run 配置。
2. `judge` 示例能清楚展示纯 rubric 评分。
3. `hybrid` 示例能清楚展示规则评分与 Judge 评分的结合。
4. `all` 配置能一次运行 `rules`、`judge`、`hybrid` 三个 OpenClaw 任务。
5. 示例不依赖新增运行时功能即可成立。

## 风险与取舍

- `openclaw skills list --json` 的本机输出可能因环境不同而不同，因此 Judge rubric 必须强调忠于观察，而不是追求固定结论。
- `hybrid` 示例的规则应保持最小集；如果规则过多，会削弱它作为教学示例的可读性。
- 为兼顾现有兼容性与新目录结构，保留原始 `examples/tasks/openclaw_smoke.yaml` 会形成一定重复，但这是可接受的示例层重复。

## 实施范围总结

本设计的实施范围仅包括：

- 示例 task YAML
- 示例 run YAML
- 必要的轻量文档更新

不包括任何评分器、adapter、Runner 或 CLI 行为更改。
