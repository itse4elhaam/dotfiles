# DOC_MAP acceptance fixtures

Run every applicable scenario against the generated `DOC_MAP.html`. Use temporary fixture documents beneath the invocation root; remove them after validation. Report skipped scenarios with the concrete missing capability.

## Inventory and health

| Scenario | Setup | Required assertions |
|---|---|---|
| Empty inventory | No eligible documents | Map renders `0%`, `0 / 0`, empty reading path, and no divide-by-zero/console error. |
| Branch states | One untracked, staged, unstaged, pushed-branch, and unpushed-branch document | Each appears exactly once with every applicable state label. |
| Supersession | Document B explicitly replaces A | A remains discoverable under Superseded; B remains active; aggregate population excludes A. |
| Context missing | Document requires a named absent prerequisite | `context-missing` includes the missing name and a corrective action. |
| Review due vs stale | One old evergreen document and one old time-sensitive document | Evergreen document is not stale from age alone; time-sensitive document is `review-due`; `stale` requires expired/conflicting evidence. |
| Duplicate evidence | Two documents share a reader job, questions, and substantial evidence | Both receive linked duplicate evidence; similarly named but semantically different control document does not. |
| Orphan evidence | One standalone reference and one unrelated document without relationships | Standalone reference is exempt; unrelated document is `orphaned`. |

## Reading order

| Scenario | Setup | Required assertions |
|---|---|---|
| Linear prerequisites | A → B → C | Suggested order is A, B, C with a reason for each edge. |
| Tie break | Two available documents without an edge | Prior-context rank, reading time, then relative path determine order. |
| Multiple cycles | A ↔ B and C ↔ D, plus independent E | Two cycle groups render deterministically; members use relative-path order; E appears once. |
| Cycle dependent | F depends on A in cycle A ↔ B | F appears once after the cycle component and is marked blocked by that cycle. |
| No relationships | Three independent documents | Path is labeled “Suggested by context and reading time,” not dependency order. |

## Progress and resume

| Scenario | Setup | Required assertions |
|---|---|---|
| Malformed storage | Invalid JSON and out-of-range percentages | Map ignores invalid values, uses defaults, remains interactive, and does not overwrite personal state until a valid user action. |
| Monotonic progress | Send 35%, 20%, 70% for one child | Stored/displayed progress is 70%; `isRead` is false. |
| Completion | Send 100% | `isRead` derives true; aggregate and completed fraction update. |
| Invalid sender | Message from unknown window, wrong document ID, invalid percentage, or unknown heading | Message is rejected without state mutation. |
| Manual-to-automatic precedence | Store 40% manual fallback, then report 60% automatic | State becomes 60% automatic; a later 50% automatic report leaves it unchanged. |
| Heading-only advance | Store 60% at heading A, then report 60% at valid heading B | Percentage remains 60%; resume target advances to heading B. A lower percentage with valid heading C may update the heading without lowering percentage. |
| Resume heading | Report 45% at a valid heading | Entry links to encoded `#heading`, labels the section title, and retains 45%. |
| Removed heading | Regenerate without the saved heading | Percentage remains; heading is cleared; resume falls back to document root. |
| Refreshed resume link | Render a row, update its progress/heading so the row rerenders, then click Resume | Delegated opener tracks the new child and progress messages remain accepted. |
| Short document | Entire dossier fits viewport | 100% is sent only after three visible seconds. |
| Blocked popup | `window.open` returns null | Ordinary navigation remains available and entry exposes manual fallback progress. |

## UI state and queues

| Scenario | Setup | Required assertions |
|---|---|---|
| Full UI restore | Change query, every filter, sort, grouping, view, theme, queue, and collapsed sections | Reload restores controls and results before first visible render. |
| Filter URL synchronization | Activate multiple filters, copy the resulting URL, then open it after storing different filters locally | The URL contains repeated validated filter parameters; its non-empty valid filter set wins on initial load, updates visible controls/results and local storage together, and malformed values are ignored. |
| Reset view | Activate non-default controls, then reset | Defaults render and persist; queues and progress remain unchanged. |
| Storage unavailable | Make `localStorage` throw | Session remains functional with in-memory state and a neutral persistence warning. |
| Default queues | No queue key exists | Today, Required, and Reference are created once; reload does not duplicate them. |
| Queue mutation | Rename, reorder, and add one document to two queues | Order and memberships persist; duplicate IDs within one queue are rejected. |
| Missing queued document | Remove a queued fixture document | Queue retains an unresolved item until explicit removal or document return. |

## Presentation and accessibility

| Scenario | Setup | Required assertions |
|---|---|---|
| User zoom | Apply 200% browser zoom | Content and controls reflow without page-level horizontal scrolling. |
| Keyboard-only | Traverse filters, queues, progress fallback, and document links | Focus is visible, order is logical, every action works, and progress is not color-only. |
| Reduced motion | Enable reduced-motion preference | Progress and view changes use no nonessential animation. |

## Failing and regression scenarios

These scenarios document past baseline failures. Each must pass after the corresponding fix is applied. Run them alongside the acceptance fixtures above.

| Scenario | Setup | Required assertions |
|---|---|---|
| Queue inline controls | Create, rename, delete, and assign through every queue trigger | No `alert`, `prompt`, or `confirm` dialog opens. Every interaction uses a keyboard-operable inline form or panel and restores focus to its trigger. |
| Hierarchy order | Render three documents: one at 40% progress (started), one unfinished with complete prerequisites, one available but not started | **Continue Reading** appears first (unfinished doc with complete prerequisites), then **In Progress** (40% doc), then **Up Next** (available not started). Sections follow this normative order. |
| Feature checklist excluded from reader UI | Inspect rendered map for implementation checklists, fixture tables, or engineer-facing metadata | These items do not appear in Continue Reading, In Progress, Up Next, or Library sections. They may exist behind Diagnostics/Settings. |
| Minimum text sizes | Render the map at browser 100% and measure computed text style | Body text minimum effective 18px; secondary and label text minimum 14px. |
| No unsupported health signal | Register a document modified 95 days ago with no time-sensitive claims and no changed external dependencies | Document does not receive `review-due` or `stale`. Health section shows no signal or explicitly lists the document as healthy. |
| Native dialog guardrail | Source-inspect all queue interaction handlers | No call to `alert()`, `prompt()`, or `confirm()` exists in the generated HTML for queue interactions. |
| Progressive disclosure card | Render a card with health evidence, section index, and relationship metadata | Summary content (title, about, progress, reading time) is always visible. Deeper metadata is hidden behind expand/hover toggle that does not persist across page loads. |

## Completion record

For each run, record fixture name, pass/fail/skip, evidence, browser, generated-map path, and timestamp. Completion requires every applicable scenario to pass and every skip to name the unavailable capability.
