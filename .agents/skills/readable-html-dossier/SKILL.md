---
name: readable-html-dossier
description: Use when dense research, review, investigation, onboarding, or audit evidence must become a standalone HTML report, or when a document needs a reading-first visual contract.
---

# Readable HTML Dossier

Create a self-contained HTML dossier that turns dense evidence into a clear reading journey. The dossier is the narrative; a standalone HTML report that tells the full reading journey.

## Steps

1. **Name the reader job.** Choose one primary job: decide, review, onboard, debug, or audit. State the intended reader, the decision or understanding available after reading, and the dossier's freshness boundary.
   Completion: the title and opening paragraph identify the reader, purpose, and outcome without requiring the rest of the report.

2. **Build the evidence spine.** Gather the background, findings, uncertainty, actions, source links, domain documents, and external resources needed for the reader job. Use relevant research skills when external material would deepen the reader's mental model.
   Completion: every conclusion can be traced to evidence, every uncertainty is visible, and every recommended action has a reason.

3. **Shape the reading journey.** Prefer this order when the evidence supports it:
   - executive summary;
   - background and vocabulary;
   - findings or evidence cards;
   - recommended actions;
   - open questions and stale items;
   - source links, domain documents, and curated external resources.

   Remove sections that have no reader job. Give every resumable heading a stable, unique ID derived from meaning rather than position.
   For the language, load the `wait-what` skill from `~/.agents/skills/wait-what` and follow it — it enforces ASD-STE100 Simplified Technical English and the ubiquitous language from `CONTEXT.md`. It is the single source of truth for the writing; keep no separate language rules in this skill.
   Completion: each section advances the reader from orientation to evidence to action, with no empty or orphaned section, and every resumable heading has a stable ID.

4. **Write the standalone HTML.** Save where the caller asks, or in `/tmp` when no path is specified. Use semantic HTML, inline CSS, responsive reflow, dark-default theme variables, a print stylesheet, and no build step. Add a visible theme toggle only when interactive switching serves the reader. When a diagram is deemed required, use the `architecture-diagram` skill from `~/.agents/skills/architecture-diagram`.
   Completion: one HTML file opens directly through `file://`, contains its required styling, and needs no local server.

   Read [REFERENCES.md](REFERENCES.md#visual-contract) before writing; it is the single source of truth for typography, layout, scaffold, and interaction details.

5. **Install reading-progress tracking.** Add the percentage tracker defined in [REFERENCES.md](REFERENCES.md#reading-progress-tracker).
   Completion: a dossier opened from a trusted opener reports monotonic 0–100% progress and reaches 100% only at the document end; direct opening and unavailable browser APIs leave it fully readable.

6. **Verify once from source.** Run a single pass checking only: (1) the HTML opens as `file://` without manifest errors, (2) no empty sections remain, (3) prose width respects `min(65ch, 100% - 2rem)`, (4) when narration is included, the reading controller works from the directly opened `file://` file: it renders, Play reads the first block, and the active block highlights and scrolls. That is the entire check. Do not do type checks, linting, or any codebase-level validation — this is an HTML report, not application code. Do not launch browser automation, Playwright, screenshots, or browser tests of any kind. Do not re-read or re-verify after this single pass.
   Completion: the checks pass; the dossier file exists and is ready for delivery.

7. **Open the dossier.** Open the HTML file directly with the user's browser. Provide the absolute path.

   Read [REFERENCES.md](REFERENCES.md#browser-opening) for the exact direct-file browser procedure and its hard guardrails.

## Narration (optional)

When the reader may prefer listening, add the self-contained read-aloud controller. Load the `html-read-aloud` skill from `~/.agents/skills/html-read-aloud` and embed its standalone controller: the CSS into `<head>`, the markup and script before `</body>`. Mark the main content as the predictable reading root:

```html
<article data-readable-root>
```

Narration must work from a `file://` URL with no server, framework, or build step. Use `data-readable` to force-read a block and `data-reader-ignore` to exclude one; the defaults handle the rest. Read `~/.agents/skills/html-read-aloud/REFERENCES.md` for the exact embedding contract.
Completion: when narration is included, the dossier opens from `file://` with a working reading controller.

## Evidence card

Each finding answers:

- What happened?
- Why does it matter?
- What evidence supports it?
- What should a human or agent do next?
- What could make it stale?

Use tables for genuine comparisons, cards for findings, and callouts for uncertainty. Keep actions visible.

## Completion contract

The run is complete only when the dossier is readable as a standalone file and reports its path.
