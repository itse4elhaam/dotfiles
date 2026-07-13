---
name: doc-map
description: Document map for branch-local reading material. Use when local documents need an entry point or tracked read state, or when another skill creates a local document.
---

# Document Map

Maintain `DOC_MAP.html` at the root of the folder where this skill is invoked. The map is a registry: it explains which local documents matter on the current branch, what each answers, and what to read next.

Use `/readable-html-dossier` for the map's reading-first visual contract. When that skill invokes `/doc-map` after creating a dossier, update the map without invoking `/readable-html-dossier` again; this recursion guard keeps each skill responsible for one output.

## Steps

1. **Set the boundary.** Treat the invocation folder as both the scan boundary and the location of `DOC_MAP.html`. Exclude files outside it, ignored files, generated dependency trees, VCS internals, and `DOC_MAP.html` itself.
   Completion: one absolute invocation root governs discovery, links, document IDs, and output.

2. **Discover branch documents.** In a Git worktree, union untracked files, staged and unstaged changes, and files changed by both pushed and unpushed current-branch commits from their merge base. In a non-Git folder, scan the invocation root recursively. Keep human-readable documents such as HTML, Markdown, text, PDF, and office documents; include another format only when it is clearly intended for reading.
   Completion: every eligible document in the selected scope, including documents from pushed and unpushed branch commits, is accounted for once, and deleted or missing files are absent.

   Read [REFERENCE.md](REFERENCE.md#branch-aware-discovery) before running discovery; it defines the base-ref fallback and exact inventory semantics.

3. **Profile every document.** Read enough of each document to record:
   - what it is about;
   - the questions it answers;
   - whether it assumes prior context, and which context;
   - context richness as `lean`, `balanced`, or `rich`, with a neutral explanation;
   - estimated reading time;
   - relative path, format, branch state, and last known modification date;
   - useful relationships such as prerequisite, follow-up, or supersedes;
   - the stable IDs and titles of resumable sections in compatible HTML.

   Estimate prose at 200 words per minute, rounded up to a whole minute. Label media-heavy, tabular, or code-heavy estimates as approximate.
   Completion: every discovered document has all required fields, grounded in its contents rather than its filename alone.

4. **Assess document health.** Apply the registry's evidence rules for stale, review-due, duplicate, orphaned, superseded, and context-missing documents. Record evidence and one corrective action for every signal.
   Completion: every discovered document has a health result, and no warning is based only on age, filename, or missing relationships.

5. **Build the reading path.** Infer prerequisite, follow-up, and supersession edges only from document evidence. Produce a suggested reading order that respects prerequisites, explains why each document comes next, and isolates superseded material from the active path.
   Completion: every acyclic active document appears once in a deterministic suggested sequence, every ordering edge has a reason, and cycles or uncertainty are visible rather than guessed away.

6. **Create or reconcile the registry.** If `DOC_MAP.html` is absent, create it. If present, regenerate its document inventory from current evidence while retaining stable state contracts. Use relative encoded `href` links, searchable/filterable cards or rows, a dedicated suggested-reading view, health views, named reading queues, annotations/bookmarks, resume links, and per-document plus overall reading progress.
   Completion: `DOC_MAP.html` contains exactly one current entry per discovered document and no stale entry for a missing document.

   Read [REFERENCE.md](REFERENCE.md#registry-contract) before writing the file; it is the single source of truth for entry fields, state keys, accessibility, and regeneration behavior.

7. **Synchronize reader state.** Persist every registry-defined UI control, queue, annotation, bookmark, percentage, and last heading in the map's `localStorage`; restore state before first render and update visible UI and stored state together. Open compatible dossiers through the map and accept percentage plus heading progress through the validated opener bridge. Derive `isRead` automatically from 100% progress. Keep manual progress only as a clearly labeled fallback for formats or opening paths that cannot report progress.
   Completion: all reader state survives reloads, compatible dossiers resume at the last reported section, `isRead` matches progress, and storage failure degrades to session-only state.

8. **Verify and open.** Execute every applicable scenario in [FIXTURES.md](FIXTURES.md), then audit links, IDs, metadata, health evidence, suggested order, scaling, reflow, keyboard operation, state restoration, progress, resume links, queues, annotations, and storage fallback. Open `DOC_MAP.html` directly in the current browser using the `/readable-html-dossier` browser-opening procedure.
   Completion: all applicable fixture assertions pass, the map opens without a server, every local link resolves, and every reader-state control works with keyboard and pointer input.

## Completion contract

The run is complete only when `DOC_MAP.html` exists at the invocation root and every discovered branch-relevant document satisfies the complete registry contract in [REFERENCE.md](REFERENCE.md#registry-contract).
