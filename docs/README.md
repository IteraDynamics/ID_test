# Itera Documentation

This directory contains documentation for Itera Dynamics architecture, research process, runtime discipline, and LLM-assisted development workflow.

## Current documentation map

```text
docs/
  llm_skills/        Reusable LLM operating protocols
```

## LLM skills

The `docs/llm_skills/` folder is the primary documentation system for AI-assisted development.

Use these files at the start of Claude Code, ChatGPT, Codex, or other LLM-assisted sessions to constrain behavior and preserve architectural consistency.

Core files:

- `00_readme.md` — overview and usage
- `01_itera_architecture_context.md` — current system context
- `02_research_protocol.md` — research process and failure modes
- `03_code_change_protocol.md` — safe repo-editing rules
- `04_backtest_review_protocol.md` — result interpretation framework
- `05_governor_design_protocol.md` — Layer 3 governor rules
- `06_runtime_safety_protocol.md` — live/paper-trading safety rules
- `07_prompt_execution_template.md` — standard prompt structure

## Documentation principles

Itera documentation should be:

- accurate to the current branch state
- explicit about research vs runtime
- clear about what is active, rejected, archived, or candidate-stage
- conservative about live/paper-trading behavior

Do not document research artifacts as production features unless they are actually integrated into runtime.
