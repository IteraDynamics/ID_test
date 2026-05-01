# Itera Dynamics LLM Skill System

This folder contains reusable skill files for LLM-assisted development of Itera Dynamics.

The goal is to make AI-assisted work repeatable, auditable, and aligned with the fund architecture. These files are intended to be referenced directly in Claude Code, ChatGPT, Codex, or any other coding assistant session.

## How to use

Start future prompts with explicit references to the relevant skills, for example:

```text
Read and follow:
- docs/llm_skills/01_itera_architecture_context.md
- docs/llm_skills/02_research_protocol.md
- docs/llm_skills/03_code_change_protocol.md

Task:
Evaluate this candidate defensive overlay result and recommend proceed / iterate / abandon.
```

Use only the skill files required for the task. Do not attach every skill to every prompt.

## Core skills

- `01_itera_architecture_context.md` — current system state, fund structure, live validation rules, and known research outcomes.
- `02_research_protocol.md` — how to conduct strategy / sleeve / overlay / governor research without overfitting or contaminating Fund v1.
- `03_code_change_protocol.md` — rules for safe repo edits, branch hygiene, full-file replacements, tests, and reporting.
- `04_backtest_review_protocol.md` — standard method for reading backtest, blend, and overlay results.
- `05_governor_design_protocol.md` — how to design and evaluate Layer 3 governors.
- `06_runtime_safety_protocol.md` — runtime and paper-trading safety rules.

## Prime directive

Itera Dynamics is transitioning from a research project into an operated systematic fund architecture. LLMs may generate code, but they must operate under clear contracts:

1. Preserve experimental attribution.
2. Never silently change live/paper-trading behavior.
3. Prefer deterministic, closed-bar, no-lookahead logic.
4. Treat costs, slippage, turnover, and operational observability as first-class constraints.
5. Optimize for fund usefulness, not headline CAGR.

## Current branch context

These skill files were created from the `research/defensive-overlay` state, not from old `main`, because the defensive governor research and Fund v1 paper-trading discipline are now part of the current operating context.
