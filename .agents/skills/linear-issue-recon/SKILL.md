---
name: linear-issue-recon
description: Reconnaissance on a Linear issue: pull full context (description, comments, linked issues and PRs), explore the codebase, and produce an HTML dossier with a way-ahead recommendation.
---

# Linear Issue Recon

Thorough investigation of a Linear issue: gather the complete issue document, its conversation, linked artifacts, and codebase evidence, then produce a way-ahead dossier.

**Leading word:** _recon_ — treat this as reconnaissance before action. Leave no artifact unread, no linked thread collapsed, no assumption unchecked.

## Scope boundary

This skill performs read-only investigation and dossier production. It does not implement changes, create branches, or open PRs. For execution after the dossier, use implementation skills.

## Prerequisites

- Linear API access via the configured MCP server (`linear`). All Linear data access goes through `linear` MCP tools.
- GitHub access via `gh` CLI for linked PR data.
- Codebase access via standard file tools.
- `/readable-html-dossier` skill for the final deliverable.

## Workflow

### 1. Identify the target issue

Determine the Linear issue ID from the user's input or by inspecting the current git branch name for a Linear-style ticket reference (e.g. `ENG-123`, `PROJ-456`).

Search patterns for branch names: `([A-Z]+-\d+)` at the end of the branch name or after a `/` separator.

Completion: you have exactly one issue identifier, or you report that none could be found and ask the user.

### 2. Recon the issue document

Use `linear` MCP tools to fetch the full issue: description, status, priority, assignee, labels, project, and all metadata fields available.

Do not truncate or summarise the description — the full body is needed for codebase exploration. If the MCP tool returns a truncated body, use the `linear` MCP tool that returns full markdown content.

Completion: the complete issue body and all metadata fields are in hand.

### 3. Recon comment threads

Fetch ALL comments on the issue. Continue paginating until every comment is collected. Read each comment in full — do not stop at the first page.

Distinguish comment author types (human vs bot) and note any resolution decisions made in the thread.

Completion: every comment on the issue is accounted for and categorised by author type.

### 4. Trace linked issues

For every issue linked to this one, repeat steps 2–3 recursively.

Depth-limit to **one level of indirection** unless the user requests deeper. This means: linked issues of the target issue get full recon (steps 2–3), but their linked issues are noted but not reconned.

At each linked issue, record the link type (blocks, blocked by, relates to, duplicates, etc.) so the final dossier can represent the relationship graph.

Completion: every directly linked issue has been reconned and its link type recorded.

### 5. Trace linked PRs

For every PR linked to the original or linked issues, fetch:
- PR description and title
- Review threads with all comments
- Conversation comments
- Status (open/merged/closed/draft)
- CI check status

Use `gh` CLI with GraphQL for structured PR data — follow `/github-graphql-first` patterns.

Completion: every linked PR has been fetched with its review material.

### 6. Explore the codebase

Based on the gathered issue context, search the codebase for relevant files, patterns, types, and existing implementations.

Launch parallel explore agents for each distinct code area referenced in the issue. Direct the agents with specific paths, file patterns, or search terms derived from the issue body.

Concepts to search for: feature names, error messages, UI labels, API endpoints, type names, database models, or any code identifier mentioned in the issue.

Completion: each code area referenced in the issue has been examined and findings recorded.

### 7. Synthesise the dossier

Using all gathered context and codebase findings, delegate to `/readable-html-dossier` to produce a standalone HTML file.

The dossier must include:
- Issue summary and metadata
- Complete comment thread synopsis
- Linked issues inventory with relationship map
- Linked PRs status and review highlights
- Codebase findings with file paths and evidence
- Key decisions or open questions
- **Way-ahead recommendation** — a concrete set of next steps with confidence level and risk areas

The dossier should be self-contained: a human should understand the full picture without opening Linear or GitHub.

Completion: a standalone HTML file exists and the file path is reported to the user.

## Recon disciplines

- **Exhaustive reading:** read the complete thread before synthesising. Sampling the first comment misses shifts in direction.
- **Linked issues are first-class evidence:** each linked issue may narrow the scope or reveal blockers. Do not treat them as footnotes.
- **Trace the relationship graph:** note link types between issues — blocks, blocked by, relates to — so the dossier shows constraint flow.
- **Verify MCP output:** treat tool output as a starting point. If a description feels incomplete or a thread truncated, paginate or use an alternative tool to confirm completeness.
- **Distinguish stated from inferred:** in the dossier, label requirements that appear in the issue body as **stated** and those derived from code exploration as **inferred**.
