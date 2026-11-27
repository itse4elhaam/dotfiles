
## Screen readers and accessibility settings

Never enable screen readers, Orca, speech-dispatcher, accessibility speech, or desktop accessibility settings. Never set `ScreenReaderEnabled`, `screen-reader-enabled`, or `toolkit-accessibility` to true, even temporarily for testing. Never unmask speech services or remove the speech safeguards. This applies to every task, including Neovim textbox integration. Only a new, explicit user request to enable speech can override this rule.

## Media on Google Drive

On Elhaam’s workstation, open archived media, captions and receipts under `~/GoogleDrive/` before downloading an SSD copy. The mount is read-only. For content projects, `content:` maps to `~/GoogleDrive/Content/`. Publish through the project’s authorized uploader and verify the Drive file and build receipt. Use writable scratch for an encode, and keep a large local copy only for a specific remaining step or retention request. Follow the project’s storage and cleanup rules.

## Compute permission

Remote compute is off by default. Never install or launch boxes.dev or wake any of its machines. Agent 37 requires Elhaam's explicit permission for each specific run, including submitting work to an existing instance, starting one, or resuming one. This applies to delegated work, retries that start another run, and scheduled jobs. Account setup and earlier approvals do not authorize a run.

For heavy local work, follow `~/.agents/skills/laptop-compute-caps/SKILL.md`. Keep whole-machine CPU at or below 50% and RAM at or below 70%.

## Claude usage

The user explicitly lifted the Claude ban on 2026-11-17. Claude is permitted. The user paused the Claude usage guard (`claude-usage-guard.timer`) on 2026-11-18. Leave it disabled until they ask to turn it back on.

## Finish one-shot tickets and side-ships

By default, read and follow `~/.agents/skills/conclude-thread/SKILL.md` for independently actionable one-shot implementation tickets and when working a `side-ship` brief. A one-shot ticket asks for a concrete change with a clear outcome and enough context to carry it through without a separate scoping decision. Apply the workflow even when the user omits the skill name.

Use the authorization already in force for each step. A side-ship brief carries its existing authorization to open a PR, merge after required checks and reviews, and sync the live copy. Honor explicit holds, named finalizers, review or release gates, and the requested stopping point. For analysis, plans, or drafts, deliver the requested artifact and stop there. If a landing step needs authorization or a decision, finish the independent work and report what's pending.
