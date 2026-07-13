# DOC_MAP reference

Load the section named by `SKILL.md` only when that step is active.

## Branch-aware discovery

### Git worktrees

Build one deduplicated inventory from these sources:

1. Untracked, non-ignored files: `git ls-files --others --exclude-standard`
2. Unstaged changes: `git diff --name-only --diff-filter=ACMR`
3. Staged changes: `git diff --cached --name-only --diff-filter=ACMR`
4. Current-branch commits: `git diff --name-only --diff-filter=ACMR "$base"...HEAD`

Resolve `base` in this order:

1. an explicit caller, issue, or pull-request base;
2. the current branch's upstream only when it names a different branch, such as a stacked-branch parent;
3. `origin/HEAD`'s symbolic target;
4. an existing `origin/main`, then `origin/master`;
5. the root commit of `HEAD`.

Use the merge-base/triple-dot comparison so changes added to the base after the branch diverged do not enter the map. If `HEAD` has no commits, use only working-tree sources. Keep paths beneath the invocation root and exclude deleted paths after forming the union.

Do not include stashes: they are not part of the visible branch or working tree. Do not override ignore rules. Exclude at least `.git/`, dependency/vendor trees, caches, build output, and `DOC_MAP.html` unless the caller explicitly narrows the boundary to one of those locations.

### Non-Git folders

Recursively scan beneath the invocation root for readable document formats. Apply the same exclusions and label branch state as `local`.

### Branch-state labels

Use the most informative applicable label:

- `untracked`
- `staged`
- `modified`
- `branch commit`
- `local` for non-Git discovery

If more than one applies, show all applicable labels without duplicating the entry.

## Registry contract

### Stable identity

The document ID is its normalized path relative to the invocation root, using `/` separators. The map ID is the first 12 hexadecimal characters of SHA-256 over the canonical absolute invocation-root path. HTML-escape visible text and build relative `href` values by percent-encoding each path segment while preserving `/`.

```text
doc-map:v2:<map-id>:document:<relative-path>
doc-map:v2:<map-id>:ui
doc-map:v2:<map-id>:queues
doc-map:v2:<map-id>:annotations
```

Changing the key prefix, map-ID algorithm, or path normalization requires an explicit migration because regeneration must preserve reader state.

### Required entry fields

Each entry contains:

| Field | Rule |
|---|---|
| Title | Prefer the document's own title; fall back to filename. |
| About | One or two concrete sentences. |
| Questions answered | A short list phrased as questions. |
| Prior context | `None`, `Helpful`, or `Required`, followed by the named context. |
| Context richness | `Lean`, `Balanced`, or `Rich`, plus a neutral reason based on evidence, examples, links, and background. |
| Reading time | `N min` at 200 prose words/minute, rounded up; mark non-prose estimates approximate. |
| Path and format | Relative path and normalized format label. |
| Branch state | One or more discovery labels. |
| Last modified | Filesystem modification date, labeled as local metadata rather than authorship time. |
| Relationships | Prerequisites, follow-ups, or superseded documents when supported by evidence. |
| Section index | Stable heading IDs and titles for compatible HTML documents. |
| Health | Zero or more evidence-backed signals, each with reason and corrective action. |
| Suggested order | 1-based active-path position and a concise “why next” explanation. |
| Reading progress | Integer `0–100`, tracking method, last heading ID, and update timestamp. `isRead` is derived as `progress === 100`. |

Context richness is descriptive, not a quality score. Do not convert it into good/bad language or rank documents by it.

### Reader progress

Persist JSON shaped as:

```json
{"progress":65,"method":"automatic","lastHeadingId":"findings","updatedAt":"2026-07-12T00:00:00.000Z"}
```

Progress follows these rules:

1. Clamp progress to an integer from 0 through 100.
2. Automatic progress is monotonic: persist `max(stored, received)` so scrolling upward never makes a document less read.
3. Derive `isRead`; never persist a separate boolean that can drift from progress.
4. Compatible dossiers use `method: "automatic"`. Direct-open or non-trackable formats expose a manual percentage control labeled `method: "manual-fallback"`.
5. A later automatic event may replace manual fallback only when its percentage is greater; automatic tracking remains the preferred source.
6. Accept `lastHeadingId` only when it appears in that document's section index. Update it independently from percentage so lateral section navigation can improve the resume target without reducing progress.

The aggregate population is every discovered document not placed in the “Superseded” section. Use this same population for both the percentage and completed fraction. Overall progress is reading-time weighted:

```text
round(sum(document progress × estimated minutes) / sum(estimated minutes))
```

Also display completed documents as a fraction (`3 / 8`) so the weighting stays transparent. If no reading-time estimate is available, use one minute for that document and label the aggregate approximate.

When the aggregate population is empty, render `0%` and `0 / 0`; skip division entirely.

Wrap every storage operation in `try/catch`. Keep an in-memory state map when `localStorage` is unavailable. Regeneration leaves active keys untouched; stale keys may remain because the generated file cannot safely infer whether another map in the same browser origin still owns them.

### UI state synchronization

Persist all interactive controls together under `doc-map:v2:<map-id>:ui`:

```json
{
  "query":"",
  "filters":{"format":[],"branchState":[],"readState":[],"contextRichness":[],"health":[]},
  "sort":{"field":"lastModified","direction":"desc"},
  "groupBy":"none",
  "viewMode":"cards",
  "theme":"dark",
  "selectedQueueId":null,
  "collapsedSectionIds":[]
}
```

The generated map must:

1. parse and validate stored values before first render;
2. merge only recognized fields with defaults, ignoring malformed or obsolete values;
3. initialize every visible control from the resulting state;
4. update state, UI, results, and `localStorage` as one action for every control change;
5. preserve search, every filter, sort, grouping/view mode, theme, selected queue, and collapsed sections across reloads;
6. provide “Reset view” to restore and persist defaults;
7. respond to a same-key `storage` event when the browser supplies one, while treating same-tab state as authoritative because cross-file events are unreliable under `file://`.

Debounce text-query persistence, but update its results immediately. Regeneration must preserve the UI key. The default list sort is `lastModified` descending; user state may select suggested order, progress, title, reading time, context richness, format, or branch state.

Use one state application path for initial load and interactions so controls cannot drift from storage:

```javascript
const UI_DEFAULTS = {
  query: "",
  filters: { format: [], branchState: [], readState: [], contextRichness: [], health: [] },
  sort: { field: "lastModified", direction: "desc" },
  groupBy: "none",
  viewMode: "cards",
  theme: "dark",
  selectedQueueId: null,
  collapsedSectionIds: []
};

let uiState = loadAndValidateUiState(UI_DEFAULTS);

function applyUiState(nextState, { persist = true } = {}) {
  uiState = validateUiState(nextState, UI_DEFAULTS);
  syncControlsFromState(uiState);
  renderFilteredDocuments(uiState);
  if (persist) safeSetItem(uiStateKey, JSON.stringify(uiState));
}

applyUiState(uiState, { persist: false });
```

Every control handler calls `applyUiState` with a new state object. A `storage` event for `uiStateKey` parses its `newValue` and calls the same function with `{ persist: false }`.

### Automatic progress

`DOC_MAP.html` cannot observe scrolling in a separate document, and separate `file://` pages cannot reliably share `localStorage`. Automatic tracking therefore uses an opener bridge:

1. The map delegates clicks from every compatible document, resume, annotation, and bookmark link; validates its document/heading IDs; opens the encoded URL with `window.open`; and records the returned `Window` reference with the expected document ID.
2. The dossier sends `{ type: "doc-map:progress", documentId, progress, lastHeadingId }` to `window.opener` with `postMessage`. Use `/readable-html-dossier`'s reading-progress tracker as the sender implementation.
3. The map accepts the event only when `event.source` is a recorded child window and `documentId` exactly matches the ID paired with that window.
4. The map validates an integer percentage, applies monotonic precedence, persists accepted progress in its own storage, and refreshes the row and aggregate immediately.

The receiver validates both source window and document ID before accepting progress. A directly opened dossier has no trusted map opener and therefore cannot update the map automatically. A blocked popup falls back to the ordinary link and manual state.

The generated map implements the receiving side with this shape; `setProgress` applies the state contract above and refreshes the affected row and overall progress:

```javascript
const openedDocuments = new Map();

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const link = event.target.closest("a[data-document-id][data-auto-track='true']");
  if (!link) return;

  const documentId = link.dataset.documentId;
  const headingId = link.dataset.headingId || null;
  const documentRecord = documentsById.get(documentId);
  if (!documentRecord) return;
  if (headingId !== null && !isKnownHeading(documentId, headingId)) return;

  event.preventDefault();
  const url = new URL(documentRecord.href, window.location.href);
  url.hash = headingId || "";
  const child = window.open(url.href, "_blank");
  if (child) openedDocuments.set(child, documentId);
  else window.location.href = url.href;
});

window.addEventListener("message", (event) => {
  const expectedId = openedDocuments.get(event.source);
  const message = event.data;
  if (!expectedId || message?.type !== "doc-map:progress") return;
  if (message.documentId !== expectedId) return;
  if (!Number.isInteger(message.progress) || message.progress < 0 || message.progress > 100) return;
  const headingId = message.lastHeadingId ?? null;
  if (headingId !== null && !isKnownHeading(expectedId, headingId)) return;
  setProgress(expectedId, message.progress, "automatic", headingId);
});
```

Remove a child-window entry when it reports 100% and periodically discard references whose `closed` property is true. `setProgress` preserves the greatest percentage and updates `isRead` from that value.

Markdown, PDF, office, image, and externally generated HTML documents without the tracker use manual fallback progress. Show this limitation as neutral metadata, not an error.

### Suggested reading order

Build a separate active reading path; list sorting does not redefine it.

1. Exclude documents explicitly superseded by another active document, but keep them in a “Superseded” section.
2. Treat prerequisite relationships as directed edges. Collapse strongly connected components into a component DAG, then topologically sort that DAG.
3. When multiple components are available at the same graph level, compare their first member using: `Prior context: None`, then `Helpful`, then `Required`; shorter reading time; relative path.
4. Sort members of an acyclic component normally. Sort members of a cyclic component by relative path, label the component “Ordering cycle,” and show every conflicting edge.
5. Give each acyclic ordered item a 1-based sequence number and “why next” text grounded in its prerequisite or tie-break evidence. Cyclic members receive a shared unresolved position rather than a fabricated internal sequence.
6. Keep nodes downstream of a cyclic component in the component-DAG order, mark them “Blocked by ordering cycle,” and list each document exactly once.
7. If there is no relationship evidence, label the sequence “Suggested by context and reading time” rather than presenting it as a dependency order.

The map presents “Continue reading” as the first unfinished document whose prerequisites are 100% complete. Readers can still open any document.

### Resume links

When stored progress is between 1 and 99 and `lastHeadingId` remains in the section index, show “Resume at <section title>” as a delegated tracked link carrying `data-document-id`, `data-heading-id`, and `data-auto-track="true"`. If the heading disappeared after regeneration, clear only `lastHeadingId`, retain percentage, and fall back to the tracked document URL. At 0%, show “Start”; at 100%, show “Revisit.”

### Document health

Health signals are diagnostics, not quality scores. Each signal records `type`, `evidence`, `action`, and `checkedAt`.

| Signal | Evidence rule |
|---|---|
| `stale` | An explicit freshness/expiry boundary has passed, or time-sensitive claims conflict with newer discovered evidence. Age alone is insufficient. |
| `review-due` | Last modified is at least 90 days old and the document contains time-sensitive claims or external dependencies. |
| `duplicate` | Another active document has the same reader job and answered questions with substantially overlapping evidence. Name similarity alone is insufficient. |
| `orphaned` | No relationship points to or from the document, and its contents do not identify it as standalone/reference material. |
| `superseded` | The document or another discovered source explicitly identifies its replacement. |
| `context-missing` | Prior context is `Required`, but a named prerequisite is absent, unresolved, or outside the discovery boundary. |

Display a health summary, filter, evidence details, and corrective actions. Do not automatically delete, merge, or rewrite documents from a health signal.

### Reading queues

Persist queues under `doc-map:v2:<map-id>:queues`:

```json
{
  "queues":[
    {"id":"today","name":"Today","documentIds":[],"createdAt":"2026-07-13T00:00:00.000Z","updatedAt":"2026-07-13T00:00:00.000Z"},
    {"id":"required","name":"Required","documentIds":[],"createdAt":"2026-07-13T00:00:00.000Z","updatedAt":"2026-07-13T00:00:00.000Z"},
    {"id":"reference","name":"Reference","documentIds":[],"createdAt":"2026-07-13T00:00:00.000Z","updatedAt":"2026-07-13T00:00:00.000Z"}
  ]
}
```

Create those three queues only when no queue state exists. Queue IDs are stable slugs unique within the map; names are editable. Preserve array order, support add/remove/reorder, deduplicate document IDs within a queue, and retain missing IDs as visibly unresolved until the user removes them or the document returns. A document may belong to multiple queues. Queue selection is UI state; queue contents are domain state.

### Annotations and bookmarks

Persist annotations under `doc-map:v2:<map-id>:annotations`:

```json
{
  "items":[
    {"id":"uuid","documentId":"report.html","headingId":"findings","kind":"note","text":"Compare with Q2.","createdAt":"2026-07-13T00:00:00.000Z","updatedAt":"2026-07-13T00:00:00.000Z"}
  ]
}
```

`kind` is `note` or `bookmark`. Notes require non-blank text; bookmarks may use an empty string. `headingId` is null for document-level items and otherwise must appear in the section index. Support create, edit, delete, filter, and direct navigation through the same delegated tracked-link contract used by resume links. Insert user text with `textContent`, not HTML. Preserve annotations whose document or heading is missing, label them unresolved, and never silently discard personal data during regeneration.

### Accessible interaction

- Use native range/progress controls or accessible equivalents with current percentage in the accessible name.
- Announce meaningful milestones through one `aria-live="polite"` region rather than every scroll update.
- Expose weighted overall completion with visible text and an ARIA progressbar.
- Keep filtering and sorting keyboard operable.
- Preserve visible focus and communicate progress with text, structure, and color together.

### Regeneration

Regenerate the inventory rather than patching arbitrary HTML fragments. Stable storage contracts preserve progress and UI state independently from file contents. Keep the default `lastModified`-descending sort unless persisted user state selects another. Include the suggested path, generated timestamp, discovery boundary/base, and state-schema version so the reader can judge freshness.
