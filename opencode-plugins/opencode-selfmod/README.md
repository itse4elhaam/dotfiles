# opencode-selfmod

**OpenCode self-modification, but reviewable and safe.**

`opencode-selfmod` is a public OpenCode plugin for Pi-style self-improvement:
you can ask OpenCode to improve its own configuration, agents, commands, tools,
and plugin config files. Instead of editing live files directly, it creates a
proposal, applies the candidate change in an isolated git worktree, runs your
validation commands, shows a diff, and only applies the change after explicit
confirmation.

The goal is to give OpenCode enough context to modify itself well, while keeping
every mutation auditable, reversible, and gated.

## What it does

- Builds an OpenCode-specific context pack from `.config/opencode`, `.opencode`,
  agents, commands, plugin config files, package metadata, and local guide files.
- Ships a dedicated `@self-modifier` agent template whose model is configured
  through plugin options.
- Registers self-modification tools for proposing, evaluating, sandboxing,
  validating, diffing, applying, and cleaning up changes.
- Classifies proposed file changes by risk before they reach a worktree.
- Blocks common validation-bypass markers such as `@ts-ignore`,
  `@ts-expect-error`, `eslint-disable`, and skipped tests.
- Keeps candidate edits out of the active checkout until validation passes and
  the caller provides the exact apply confirmation string.

## What it does not do

- It does **not** silently rewrite your OpenCode setup.
- It does **not** approve its own changes.
- It does **not** push, commit, or publish changes for you.
- It does **not** collect telemetry.
- It does **not** install postinstall scripts.

Autonomous background improvement is intentionally out of scope for v0.1.0. The
manual, validated loop comes first.

## Quick start

### 1. Install from GitHub

OpenCode loads package plugins listed in `opencode.json` and installs them with
Bun. Install this package in
the same directory as your OpenCode config package, usually
`~/.config/opencode`:

```bash
cd ~/.config/opencode
bun add github:itse4elhaam/opencode-selfmod
```

> GitHub install is supported by committed `dist/` output. The package also has
> a Bun-backed `prepare` script for local development rebuilds.

### 2. Add the plugin to `opencode.json`

```jsonc
{
  "plugin": [
    [
      "opencode-selfmod",
      {
        "model": "opencode-go/deepseek-v4-flash",
        "riskThreshold": "moderate",
        "validationCommands": ["bun run typecheck", "bun run build"],
        "maxContextChars": 24000,
        "maxFileChars": 4000
      }
    ]
  ]
}
```

### 3. Install the dedicated agent

Copy the packaged agent template into your OpenCode agent directory:

```bash
mkdir -p ~/.config/opencode/agent
cp node_modules/opencode-selfmod/agent/self-modifier.md \
  ~/.config/opencode/agent/self-modifier.md
```

Restart OpenCode so it reloads the plugin and agent.

### 4. Use the workflow

Ask the dedicated agent to improve OpenCode itself, for example:

```text
@self-modifier improve my OpenCode command docs and validate the change before applying it
```

The agent is instructed to use this tool sequence:

```text
selfmod_context
  → selfmod_propose
  → selfmod_evaluate
  → selfmod_worktree
  → selfmod_validate
  → selfmod_diff
  → selfmod_apply confirm="apply:<proposalId>"
  → selfmod_cleanup
```

## Candidate worktrees

`selfmod_worktree` creates an isolated git worktree and temporary branch from
the current `HEAD`, then applies the proposed file changes there. Your active
checkout is not touched during proposal, sandboxing, validation, or diff review.

Only `selfmod_apply` copies validated files back to the active checkout, and it
requires both:

1. a passed validation result, and
2. the exact confirmation string `apply:<proposalId>`.

This makes self-modification behave like a reviewable patch pipeline instead of
an invisible live edit.

## Tool reference

| Tool | Purpose |
| --- | --- |
| `selfmod_context` | Generate a redacted OpenCode context pack for self-modification. |
| `selfmod_propose` | Create an in-memory proposal from intended file changes. |
| `selfmod_evaluate` | Re-run policy checks and risk classification for a proposal. |
| `selfmod_worktree` | Create an isolated git worktree and apply candidate changes there. |
| `selfmod_validate` | Run validation commands inside the candidate worktree. |
| `selfmod_diff` | Return a structured diff report and raw diff preview. |
| `selfmod_apply` | Copy validated candidate files back to the active checkout after explicit confirmation. |
| `selfmod_cleanup` | Remove the candidate worktree and temporary branch. |

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `model` | `opencode-go/deepseek-v4-flash` | Preferred model for the dedicated self-modifier agent. The agent file references this policy instead of hardcoding a model. |
| `riskThreshold` | `moderate` | Highest risk level allowed to proceed into a worktree. One of `safe`, `moderate`, `dangerous`, `critical`, or `off`. |
| `validationCommands` | `[]` | Commands run by `selfmod_validate` when no command override is provided. |
| `workDir` | `.selfmod/worktrees` | Directory used for candidate worktrees. |
| `homeConfigDir` | unset | Optional home OpenCode config directory to include in context packs. Defaults to `$HOME`-based discovery when omitted. |
| `maxContextChars` | `24000` | Total context-pack character budget. |
| `maxFileChars` | `4000` | Per-file context character budget. |
| `protectedPathOverrides` | `[]` | Additional path/risk rules for local policy needs. |
| `autoApprovalPatterns` | `[]` | Reserved for future use. v0.1.0 still requires explicit apply confirmation. |
| `debug` | `false` | Emit extra plugin diagnostics. |

## Risk policy

The default policy is intentionally conservative:

| Risk | Examples |
| --- | --- |
| `critical` | `.git/`, `.env*`, secrets, `.pem`, `.key` files. |
| `dangerous` | Lock files, CI/CD workflows, Dockerfiles. |
| `moderate` | `.config/opencode/`, `.opencode/`, shell rc files, plugin source code. |
| `safe` | New Markdown files and low-risk documentation changes. |

Proposals above `riskThreshold` are rejected before worktree creation. Proposals
containing validation bypass markers are also blocked.

## Example config

See [`examples/opencode.json`](examples/opencode.json) for a copy-pasteable
plugin configuration.

## Development

```bash
bun install
bun run typecheck
bun run build
bun pm pack --dry-run
```

The package is ESM and targets Node.js 22+.

## Current status

This is a v0.1.0 base release. It includes the validated manual workflow,
context generation, policy checks, candidate worktrees, validation, diff reports,
and explicit apply gates.

Known limitations:

- Proposal and worktree state is in memory; restarting OpenCode loses pending
  proposals.
- There is no TUI review panel yet.
- There are no slash commands yet; use the registered tools or the packaged
  `@self-modifier` agent.
- Autonomous background improvement is planned only after the manual validation
  loop is proven.

## License

MIT
