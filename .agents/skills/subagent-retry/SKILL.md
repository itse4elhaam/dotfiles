---
name: subagent-retry
description: Recover stuck or incomplete subagent work in OhMyOpenAgent. Use when a subagent times out, returns empty output, produces a partial result, or errors out before completing its task — get its output, assess what's done, then either finish the remainder yourself or launch a follow-up subagent for the unfinished portion.
allowed-tools: Bash, Read, Grep, Glob, Edit, Task
disable-model-invocation: true
---

# Subagent Retry

Recover gracefully when an OhMyOpenAgent subagent stalls, errors, or produces incomplete work. The core loop: **extract → assess → continue-or-fire**.

This skill is for recovering work from a *previous* subagent that failed. Use it when a subagent session produced no output, partial output, or errored before completion.

## Workflow

### 1. Capture the subagent output

Use `background_output(task_id="...", full_session=true)` to pull the full agent transcript. Set `include_tool_results=true` to see every file it wrote, read, or modified. Set `include_thinking=true` to see its reasoning.

If the subagent wrote intermediate files or partial results, record their paths and contents.

Completion criterion: you know exactly what the stuck agent produced (files, stdout, stderr) and where it stopped.

### 2. Assess completeness

Map what was asked against what was delivered:

- **All done** — the task is fully complete despite the status. Commit/output the results directly.
- **Partially done** — some files written, some steps completed. Identify the last completed step and the next undone step.
- **Nothing done** — agent crashed or returned nothing useful. Treat the task as fresh.
- **Confused direction** — agent went off-course but produced usable intermediate work. Decide whether to salvage or discard.

State the assessment explicitly before proceeding.

Completion criterion: you have a clear verdict — full, partial, none, or misdirected.

### 3. Continue or re-fire

**If all done:** deliver the results. No further action needed.

**If partially done:** continue from the last completed step. Preserve the agent's output files and complete the remainder yourself using direct tools.

**If nothing done or confused:** fire a new subagent with the same original task. Add a note in the prompt about what the previous attempt produced (or failed to produce) so the new agent doesn't repeat the same mistakes:

```text
[PREVIOUS ATTEMPT]: A previous subagent attempted this task but [describe failure].
Produced: [files/outputs].
Stopped at: [step].
Do not repeat the same approach for [what failed].
```

**If the remaining work is independent:** fire multiple subagents concurrently using `run_in_background=true`.

Completion criterion: the original task is complete, or you have a clear reason to escalate to the user.

### 4. If still stuck

If the follow-up agent also fails or the error is architectural:

1. Document both attempts and their output paths.
2. Escalate to the user with a summary of what was tried, what was produced, and what remains uncertain.
3. Ask for guidance before trying a third time.

## Reference

### Causes of stuck subagents

| Symptom | Likely cause | Mitigation |
|---|---|---|
| Timeout | Task too large for one session | Split into smaller sub-tasks before firing |
| Empty output | Agent crashed or was denied a tool | Review tool permissions; re-fire with same prompt |
| Partial output | Agent hit context limit mid-task | Resume from last completed step |
| Wrong output | Agent misunderstood the prompt | Tighten prompt scope and add constraints |
| Duplicate work | Agent repeated a step | Give explicit "do not repeat" instructions |

### Leading word

*Tracer bullet* — each retry is a small, fast probe that either completes the task or reveals exactly where the next bullet should aim.
