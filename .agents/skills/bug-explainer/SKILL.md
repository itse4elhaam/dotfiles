---
name: bug-explainer
description: Use when a bug found by an agent (static analysis or testing) must be explained to a human who did not write the code — after an audit or on demand ("explain this bug to me"). Produces a symptom-first, plain-language bug report a non-implementer can act on.
---

# Bug Explainer

Explain a bug to the human who owns the product but did not write the code — so they can act on it without fighting the agent. The report is a story of what the user experiences, grounded in the implementation that causes it.

**Leading words:** _delta_ — the gap between what the code intends and what it does; _symptoms_ — the observable user-facing problem, stated before any mechanism; _anchor_ — a small dataset, traced from the user's eyes into the app, that holds the whole report in place.

**Voice.** The report is a _story_ told from the reader's eye in the user's product language: what the user brought, did, saw, and expected. The story carries at most one plain sentence of mechanism per beat; file:line anchors, SQL casts, and keys ride in the Evidence appendix; the story carries product language. Before writing the first sentence, load `/wait-what` from `~/.agents/skills/wait-what` and follow it — its plain-language rules bind every sentence.

## Scope

This skill explains bugs; it does not fix them. The fix appears only as a verifiable end-state statement. For implementation of the fix, hand off to implementation skills.

## Prerequisites

- The bug report (from an audit, test failure, or the agent's own finding).
- Access to the code (file tools, codegraph where indexed).
- `/understand-code-like-an-owner` — runs as Phase A; the data-flow narrative it produces is the foundation of this report.
- `/wait-what` — the single source of truth for language (STE + ubiquitous language).
- `/readable-html-dossier` — for the optional HTML delivery mode.

## Workflow

### 1. Phase A — understand the implementation first

Run `/understand-code-like-an-owner` for Phase A. The bug report rides on top of its narrative — the bug is the _delta_ between that narrative's intent and what actually happens. Phase A first; a report without the implementation narrative is the failure mode this skill exists to fix.

Completion: an ownership-grade narrative of the code path the bug lives in, with the concrete dataset established.

### 2. Report the symptom first

One sentence, under 60 words, active voice, in the reader's product language: what the user does, what the system shows, what it should show. Observable problem before any mechanism. Every jargon term carries a gloss or a plain equivalent.

Completion: the bug is stateable by a product person who has not read the code.

### 3. Anchor the bug on the dataset

The Phase A _anchor_ — the small dataset traced from the user's eyes into the app — is the anchor of the bug report too. Run the failure through it: the data the user brought, the action they took, what the system showed, what they expected to see. Land on where the issue is — the expected/actual divergence. When Phase A produced no dataset because the bug is value-independent, build one now: the smallest dataset that reproduces the failure (Stack Overflow's minimal reproducible example). Reduce the mechanism to one plain sentence; its detail — stage tables, SQL casts, keys — goes in the Evidence appendix. Then one sentence fading to the general rule.

Completion: a reader can replay the failure on one concrete input, traced from the user's eye into the app, and see where the issue is and what diverges.

### 4. State impact and propose severity

Who is affected, how many, what exactly they see, what they can no longer do, is there a workaround. Numbers where measurable; a labelled estimate where not — an estimate beats silence. Propose a severity tied to an observable symptom (e.g. Chromium's test: "would someone notice, in a bad way?") phrased as a suggestion for the human to confirm, not an assertion — reporters do not set severity; triagers do.

Completion: impact with numbers-or-estimate, plus one severity proposal with its observable basis.

### 5. Separate mechanism from trigger; give the fix an end state

Two labelled lines:
- _Mechanism_ — what the code does, in one plain sentence (detail goes in the Evidence appendix).
- _Trigger_ — the specific condition that trips it.

Then a before/after fix statement: "After the fix, [observable behavior]." The symptom is the problem; the mechanism only explains it.

Completion: mechanism and trigger each on their own labelled line, plus one verifiable before/after statement.

### 6. Say why it did not fail earlier

One honest paragraph on why tests, prior reviews, or the user's own usage did not surface this — e.g. "tests only used empty lists", "the e2e expects [5,5,0] but the final full page reports hasMore=true". If the reason is unknown, say so.

Completion: an honest account of the bug's survival, or an explicit unknown.

### 7. Build the Evidence appendix

The story's anchors and mechanism detail live here, linked from the story: engineering term → one plain meaning (ASD-STE100 one-word-one-meaning, scoped to this report); each code reference a permalink with a one-line gloss and the commit SHA. Every file:line and snippet sits in this appendix.

Completion: every engineering term glossed, every code reference a permalink with a gloss and a SHA, every file:line in this appendix.

### 8. Check the story against the Voice rule

Re-read the report in the story voice: every sentence reads aloud in one breath, every engineering term is glossed at first use, every mechanism claim is one plain sentence, and every file:line sits in the Evidence appendix.

Completion: the story passes all four checks, and a product-knowledgeable reader can paraphrase it back.

### 9. Deliver

Default: a normal conversational response — the full report in the chat, markdown. Sections in order: summary, walkthrough, impact, mechanism/trigger/fix, why-not-failed, evidence appendix.

Optional HTML: when the user asks for a dossier/HTML, hand the assembled report to `/readable-html-dossier` and report its path.

Completion: the report delivered in the default mode the user expects (conversation, or HTML path when requested).

## Bug-type routing

The narrative shape fits logic/state/cache bugs — the trace and the delta explain them fully. For concurrency or performance bugs, narrative alone is the wrong tool: gather observability data first (runtime traces, timings, interleavings) and anchor the walkthrough to that evidence.

## Completion contract

The run is complete when the human who owns the product can (1) restate the user-visible bug, (2) replay it on the _anchor_ dataset from their own eye and see where the issue is, and (3) say what observable behavior the fix will restore — with the story in product language and the mechanism detail in the Evidence appendix.
