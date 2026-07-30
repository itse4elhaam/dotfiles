# ADR 1: Remove Redundant Superpowers Skills

**Date:** 2026-07-21

## Status

Accepted

## Context

The `.agents/skills/` directory contained 14 skills from the [obra/superpowers](https://github.com/obra/superpowers) repository. These skills form a complete SDLC methodology (brainstorm → plan → subagent-execute → review → finish).

However, the Sisyphus system persona already contains comprehensive orchestration instructions that cover the same ground — Phase 0 Intent Gate, Phase 2B decomposition/delegation, Phase 2C failure recovery, Phase 3 verification, etc. The superpowers bootstrap skill (`using-superpowers`) was being loaded at session start, consuming ~50k tokens per agent session with instructions that duplicate Sisyphus's existing behavior.

## Decision

Remove 13 superpowers skills that are redundant with the Sisyphus persona:

| Removed Skill | Sisyphus Equivalent |
|---|---|
| `using-superpowers` | Bootstrap / skill selection — covered by Category+Skill Protocol |
| `brainstorming` | Phase 0 Intent Gate |
| `writing-plans` | Phase 2B decompose+delegate |
| `executing-plans` | Phase 2B delegation |
| `subagent-driven-development` | Phase 2B subagent dispatch |
| `dispatching-parallel-agents` | Phase 2A parallel default |
| `systematic-debugging` | Phase 2C failure recovery |
| `verification-before-completion` | Evidence Requirements section |
| `receiving-code-review` | Delegation protocols |
| `requesting-code-review` | Pre-merge gates |
| `test-driven-development` | TDD mentioned in persona |
| `finishing-a-development-branch` | Phase 3 completion |
| `writing-skills` | Only useful for skill authors |

## Retained

- `using-git-worktrees` — no Sisyphus equivalent; useful for branch isolation

## Consequences

- Reduced token overhead per session (~50k tokens saved on agent start)
- No loss of workflow discipline — Sisyphus covers all removed functionality
- If Sisyphus persona is ever removed/replaced, some of these skills may need to be restored
