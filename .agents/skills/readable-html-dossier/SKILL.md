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

   Remove sections that have no reader job. Introduce each term before later sections depend on it. Give every resumable heading a stable, unique ID derived from meaning rather than position.
   Completion: each section advances the reader from orientation to evidence to action, with no empty or orphaned section, and every resumable heading has a stable ID.

4. **Write the standalone HTML.** Save where the caller asks, or in the invocation folder when no path is specified. Use semantic HTML, inline CSS, responsive reflow, dark-default theme variables, a print stylesheet, and no build step. Add a visible theme toggle only when interactive switching serves the reader.
   Completion: one HTML file opens directly through `file://`, contains its required styling, and needs no local server.

   Read [REFERENCES.md](REFERENCES.md#visual-contract) before writing; it is the single source of truth for typography, layout, scaffold, and interaction details.

5. **Install reading-progress tracking.** Add the percentage tracker defined in [REFERENCES.md](REFERENCES.md#reading-progress-tracker).
   Completion: a dossier opened from a trusted opener reports monotonic 0–100% progress and reaches 100% only at the document end; direct opening and unavailable browser APIs leave it fully readable.

6. **Verify briefly from source.** Check as many of the following from static HTML/CSS analysis as possible: semantic heading order, prose measure, WCAG AA contrast (resolve variables and calculate), non-color-only links, keyboard focus for native controls, print URL exposure, empty sections, minimum text sizes, and 200% zoom reflow from layout properties. Do not launch browser automation for checks the source can settle. If exactly one rendered fact remains genuinely uncertain after source audit, invoke `/agent-browser` once for a minimal headless smoke check of that fact only. Do not use Playwright, take screenshots, run multiple browsers, or perform exhaustive interaction testing.
   Completion: every fixable check passes; any remaining limitation is demonstrably outside the agent's control and is disclosed before delivery.

7. **Open the dossier.** Open the HTML file directly with the user's browser. Provide the absolute path.

   Read [REFERENCES.md](REFERENCES.md#browser-opening) for the exact direct-file browser procedure and its hard guardrails.

## Evidence card

Each finding answers:

- What happened?
- Why does it matter?
- What evidence supports it?
- What should a human or agent do next?
- What could make it stale?

Use tables for genuine comparisons, cards for findings, and callouts for uncertainty. Keep actions visible rather than burying them in prose.

## Completion contract

The run is complete only when the dossier is readable as a standalone file, passes the source audit, and reports its path.
