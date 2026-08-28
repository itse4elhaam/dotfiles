## NOTES

when asked to create a skill, create in this repo and then and then symlink to ~/.agents/skills

## Agent skills

### Issue tracker

Issues live as local markdown files under a **global** tracker at `~/.scratch/` (shared across every repo; prefix feature slugs with the repo name to avoid collisions). See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles, each using its own name as the `Status:` string: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` + `docs/adr/` at the repo root (a `CONTEXT-MAP.md` switches to multi-context where present). See `docs/agents/domain.md`.
