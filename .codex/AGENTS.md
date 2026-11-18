
## Screen readers and accessibility settings

Never enable screen readers, Orca, speech-dispatcher, accessibility speech, or desktop accessibility settings. Never set `ScreenReaderEnabled`, `screen-reader-enabled`, or `toolkit-accessibility` to true, even temporarily for testing. Never unmask speech services or remove the speech safeguards. This applies to every task, including Neovim textbox integration. Only a new, explicit user request to enable speech can override this rule.

## Codex fast mode

Keep Codex fast mode disabled. Do not enable fast mode, set `service_tier` to `fast`, or select a priority/fast service tier in T3 Code, including for delegated tasks. Use the default service tier. Only a new, explicit user request to re-enable fast mode overrides this rule.

**Heavy compute on this laptop:** prefer boxes.dev; before running anything CPU- or RAM-heavy locally, follow `~/.agents/skills/laptop-compute-caps/SKILL.md` (whole machine at or under 50% CPU and 70% RAM).

## Claude usage

The user explicitly lifted the Claude ban on 2026-11-17. Claude is permitted. The user paused the Claude usage guard (`claude-usage-guard.timer`) on 2026-11-18. Leave it disabled until they ask to turn it back on.

## Finish one-shot tickets and side-ships

By default, read and follow `~/.agents/skills/conclude-thread/SKILL.md` for independently actionable one-shot implementation tickets and when working a `side-ship` brief. A one-shot ticket asks for a concrete change with a clear outcome and enough context to carry it through without a separate scoping decision. Apply the workflow even when the user omits the skill name.

Use the authorization already in force for each step. A side-ship brief carries its existing authorization to open a PR, merge after required checks and reviews, and sync the live copy. Honor explicit holds, named finalizers, review or release gates, and the requested stopping point. For analysis, plans, or drafts, deliver the requested artifact and stop there. If a landing step needs authorization or a decision, finish the independent work and report what's pending.
