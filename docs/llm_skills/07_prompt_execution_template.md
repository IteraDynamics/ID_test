# Itera Prompt Execution Template (Meta Skill)

## Purpose

Provide a standard way to invoke Itera LLM skills in Claude Code, ChatGPT, Codex, or any other coding assistant.

This file is a meta skill. It does not define a single task domain. It defines how to compose the other skills into a controlled prompt.

---

## Core idea

Do not write giant one-off prompts when a reusable skill exists.

Instead, every meaningful task should include:

1. Skill references
2. Task role
3. Goal
4. Scope
5. Inputs
6. Constraints
7. Deliverables
8. Output format

---

## Standard invocation format

Use this structure:

```text
Read and follow:
- docs/llm_skills/01_itera_architecture_context.md
- docs/llm_skills/<relevant_skill>.md
- docs/llm_skills/03_code_change_protocol.md

Task role:
<research / code change / backtest review / governor design / runtime safety review>

Goal:
<one clear goal>

Scope:
<files, modules, or branch involved>

Inputs:
<commands, result blocks, artifact paths, branch names, or files>

Constraints:
<what must not change, safety rules, cost assumptions, runtime restrictions>

Deliverables:
<what to produce>

Output format:
Goal / What I Changed / Files Changed / Commands To Run / Verdict / Next Step
```

---

## Skill selection guide

Use these combinations by task type.

### Strategy or sleeve research

```text
Read and follow:
- docs/llm_skills/01_itera_architecture_context.md
- docs/llm_skills/02_research_protocol.md
- docs/llm_skills/04_backtest_review_protocol.md
- docs/llm_skills/03_code_change_protocol.md
```

### Backtest result review

```text
Read and follow:
- docs/llm_skills/01_itera_architecture_context.md
- docs/llm_skills/04_backtest_review_protocol.md

Task:
Review these results and classify proceed / iterate / abandon.
```

### Governor design or review

```text
Read and follow:
- docs/llm_skills/01_itera_architecture_context.md
- docs/llm_skills/05_governor_design_protocol.md
- docs/llm_skills/04_backtest_review_protocol.md
```

### Runtime or paper-trading changes

```text
Read and follow:
- docs/llm_skills/01_itera_architecture_context.md
- docs/llm_skills/06_runtime_safety_protocol.md
- docs/llm_skills/03_code_change_protocol.md
```

### Repo editing task

```text
Read and follow:
- docs/llm_skills/03_code_change_protocol.md

Task:
Make the requested change on branch <branch>.
```

---

## Mandatory pre-flight questions for the LLM

Before coding, the assistant must answer internally and, when useful, explicitly:

```text
1. What layer does this affect?
2. Could this change Fund v1 paper-trading behavior?
3. Is this research-only or runtime-active?
4. What is the correct baseline?
5. What is the pass/fail criterion?
```

If the answer to question 2 is yes, the change must be feature-gated or deferred unless the user explicitly instructs otherwise.

---

## Standard output format

For code changes:

```text
Goal:
What I changed:
Files changed:
Safety notes:
Commands to run:
Expected output:
Next step:
```

For research review:

```text
Test type:
Correct baseline:
Key metrics:
Interpretation:
Verdict:
Next step:
Do not do:
```

For runtime review:

```text
Runtime path affected:
Feature flag / isolation status:
State persistence impact:
Observability impact:
Paper-trading risk:
Verdict:
```

---

## Anti-patterns

Do not allow prompts that say only:

```text
Build a strategy that improves Sharpe.
```

or:

```text
Try more orthogonal ideas.
```

or:

```text
Make this production-ready.
```

These are underspecified and likely to produce unsafe or irrelevant work.

Rewrite them into structured task prompts using this template.

---

## Example: research task

```text
Read and follow:
- docs/llm_skills/01_itera_architecture_context.md
- docs/llm_skills/02_research_protocol.md
- docs/llm_skills/04_backtest_review_protocol.md

Task role:
Backtest review

Goal:
Evaluate whether candidate X should proceed as a Fund v2 component.

Inputs:
<paste result block>

Constraints:
Do not recommend changing Fund v1 live paper trading.
Use Fund v1 calibrated equal-weight as the reference baseline unless the script output states otherwise.

Deliverables:
Proceed / iterate / abandon verdict with rationale.
```

---

## Example: code task

```text
Read and follow:
- docs/llm_skills/01_itera_architecture_context.md
- docs/llm_skills/03_code_change_protocol.md
- docs/llm_skills/06_runtime_safety_protocol.md

Task role:
Code change

Goal:
Add a disabled-by-default integration hook for DefensiveExposureGovernor.

Scope:
runtime/argus/...

Constraints:
Must not change Fund v1 behavior when DEFENSIVE_OVERLAY_ENABLED=0.
Must include tests or a clear manual validation command.

Deliverables:
Files changed, commands to run, and safety notes.
```

---

## Final rule

Skills are not decoration. If a skill is referenced, the assistant must follow it. If a requested action conflicts with a skill, the assistant must call out the conflict and propose the safest path.