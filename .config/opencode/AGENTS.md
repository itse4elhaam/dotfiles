## NOTES

when asked to create a skill, create it in ~/workspace/coding/skills (github.com/itse4elhaam/skills) and then symlink it to ~/.agents/skills

## Agent skills

### Issue tracker

Issues live as local markdown files under a **global** tracker at `~/.scratch/` (shared across every repo; prefix feature slugs with the repo name to avoid collisions). See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles, each using its own name as the `Status:` string: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` + `docs/adr/` at the repo root (a `CONTEXT-MAP.md` switches to multi-context where present). See `docs/agents/domain.md`.

## Screen readers and accessibility settings

Never enable screen readers, Orca, speech-dispatcher, accessibility speech, or desktop accessibility settings. Never set `ScreenReaderEnabled`, `screen-reader-enabled`, or `toolkit-accessibility` to true, even temporarily for testing. Never unmask speech services or remove the speech safeguards. This applies to every task, including Neovim textbox integration. Only a new, explicit user request to enable speech can override this rule.

## Media on Google Drive

On Elhaam’s workstation, open archived media, captions and receipts under `~/GoogleDrive/` before downloading an SSD copy. The mount is read-only. For content projects, `content:` maps to `~/GoogleDrive/Content/`. Publish through the project’s authorized uploader and verify the Drive file and build receipt. Use writable scratch for an encode, and keep a large local copy only for a specific remaining step or retention request. Follow the project’s storage and cleanup rules.

## Compute permission

Remote compute is off by default. Never install or launch boxes.dev or wake any of its machines. Agent 37 requires Elhaam's explicit permission for each specific run, including submitting work to an existing instance, starting one, or resuming one. This applies to delegated work, retries that start another run, and scheduled jobs. Account setup and earlier approvals do not authorize a run.

For heavy local work, follow `~/.agents/skills/laptop-compute-caps/SKILL.md`. Keep whole-machine CPU at or below 50% and RAM at or below 70%.
