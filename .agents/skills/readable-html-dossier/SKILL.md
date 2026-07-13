---
name: readable-html-dossier
description: Reading-first HTML dossier. Use when dense research, review, or investigation evidence must become a standalone report, or when another skill needs the dossier visual contract.
---

# Readable HTML Dossier

Create a self-contained HTML dossier that turns dense evidence into a clear reading journey. The dossier is the narrative; `DOC_MAP.html` is the registry that helps the reader find and track it.

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

4. **Write the standalone HTML.** Save where the caller asks, or in the invocation folder when no path is specified. Use semantic HTML, inline CSS, responsive reflow, dark-default theme variables, a print stylesheet, no build step, and the visual contract's default display scale. Add a visible theme toggle only when interactive switching serves the reader.
   Completion: one HTML file opens directly through `file://`, presents all screen content at the required design scale, contains its required styling, and needs no local server.

   Read [REFERENCES.md](REFERENCES.md#visual-contract) before writing; it is the single source of truth for typography, layout, scaffold, and interaction details.

5. **Install reading-progress tracking.** Obtain the dossier's document ID from `/doc-map`'s stable-identity contract. Add the percentage tracker defined in [REFERENCES.md](REFERENCES.md#reading-progress-tracker), using the opener bridge from `/doc-map`.
   Completion: a dossier opened from `DOC_MAP.html` reports monotonic 0–100% progress and reaches 100% only at the document end; direct opening and unavailable browser APIs leave it fully readable with manual map fallback.

6. **Verify from source.** Check semantic heading order, 45–75 character prose measure, WCAG AA contrast, non-color-only links, keyboard focus, print URL exposure, empty sections, required default scaling, and reflow when the user applies up to 200% browser zoom. Use source inspection by default; use headless `agent-browser` only when rendered behavior genuinely cannot be established statically.
   Completion: every fixable check passes; any remaining limitation is demonstrably outside the agent's control and is disclosed before delivery.

7. **Automatically register the dossier.** On every normal invocation, invoke `/doc-map` at the invocation root immediately after writing the local dossier. Pass the dossier path and let `/doc-map` create or reconcile `DOC_MAP.html` across all branch-relevant documents. The sole exception is when this skill is rendering `DOC_MAP.html` for `/doc-map`; complete that map without invoking `/doc-map` again.

   Completion: the dossier has exactly one current entry satisfying `/doc-map`'s complete registry contract.

8. **Open through the registry.** Open `DOC_MAP.html` as the browser entry point and direct the reader to its tracked dossier link. The map must create the dossier tab so it can validate the completion event; command-line opening of the dossier bypasses automatic tracking.
   Completion: the map is open, its dossier link creates a tracked child tab, and the user receives absolute paths for both files.

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

The run is complete only when the dossier is readable as a standalone file, passes the source audit, reports its path, and is registered in `DOC_MAP.html` unless it is itself the map.
