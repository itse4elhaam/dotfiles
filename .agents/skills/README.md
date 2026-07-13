# Dotfiles Skills

AI agent skills for code review, Git workflows, documentation, and structured data access. These skills are designed for [OpenCode](https://opencode.ai) and other AI coding agents that support the skills specification.

> **Installed automatically** by [`dev-setup/runs/skills.sh`](../dev-setup/runs/skills.sh) — skills are symlinked from the dotfiles repo to `~/.agents/skills/`.

## Skills

| Skill | Description |
|---|---|
| **elhaam-review** | Personal code review with seven lenses: codebase boundary, simplicity, test confidence, security/server boundaries, scalability, maintainability, and automation feedback. Defaults to an HTML findings report. |
| **pr-review-dossier** | Read-only investigation of GitHub PR review feedback. Fetches review threads via GraphQL and produces an evidence-backed HTML dossier with a recommended decision or way ahead. |
| **local-change-review** | Review uncommitted local changes by grouping related hunks into small, intentional commits. |
| **conflict-rebase-resolution** | Merge or rebase by gathering a holistic view of conflicts, then resolving them safely. |
| **readable-html-dossier** | Create standalone, reading-first HTML reports for research, reviews, and investigations. |
| **doc-map** | Maintain a branch-aware DOC_MAP.html registry with document summaries, reading metadata, and persistent read status. |
| **github-graphql-first** | Fetch structured GitHub data — PRs, reviews, review threads, comments, project items, timelines — using `gh api graphql`. |
| **linear-issue-recon** | Pull full context from a Linear issue (description, comments, linked issues and PRs), explore the codebase, and produce an HTML dossier with a way-ahead recommendation. |

## Installing from this repo

Install individual skills via `npx skills`:

```bash
npx skills add itse4elhaam/dotfiles@elhaam-review --global --all --yes
npx skills add itse4elhaam/dotfiles@local-change-review --global --all --yes
```

Or install all skills at once:

```bash
npx skills add itse4elhaam/dotfiles --global --all --yes
```

## Adding a new skill

1. Create a new directory: `mkdir -p .agents/skills/<skill-name>`
2. Add `SKILL.md` with [frontmatter](https://github.com/mattpocock/skills). Model-invoked skills keep a trigger-oriented `description`. On runtimes that support user-only invocation, user-invoked skills set `disable-model-invocation: true`; OpenCode ignores that extension, so use its skill permissions when the distinction must be enforced there.
3. Symlink it globally: `ln -sfn "$PWD/.agents/skills/<skill-name>" ~/.agents/skills/<skill-name>`
