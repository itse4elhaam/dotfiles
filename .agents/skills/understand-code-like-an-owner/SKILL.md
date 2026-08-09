---
name: understand-code-like-an-owner
description: Use when explaining code to someone who did not write it — how a module or feature works, onboarding to a codebase area, or the understand phase before explaining a bug. Produces an ownership-grade data-flow narrative in the reader's product language.
---

# Understand Code Like an Owner

Explain code to someone who did not write it as if they wrote it themselves. The reader leaves with the implementation's mental model — the data-flow story of what the code does and why — not a list of components.

**Leading words:** _trace_ — follow one user-visible outcome from the user action that triggers it, through request, query, transformation, to the result. Everything outside that path is noise; _anchor_ — a small dataset, traced from the user's eyes into the app, that holds the whole narrative in place.

**Voice.** The narrative is a _story_ told from the reader's eye in the user's product language: what the user brought, did, saw, and expected. File:line anchors ride beside the story as references; the story itself carries product language. Before writing the first sentence, load `/wait-what` from `~/.agents/skills/wait-what` and follow it — its plain-language rules bind every sentence.

## Scope

This skill produces explanations, not analysis. It reconstructs and narrates an implementation for the human who owns it. It does not fix bugs, make recommendations, or write code — for reporting a bug on top of the understanding, use `/bug-explainer`.

## Prerequisites

- Access to the code under explanation (file tools, codegraph where indexed).
- `/wait-what` for the writing rules — the single source of truth for language (ASD-STE100 Simplified Technical English + project ubiquitous language from `CONTEXT.md`). Keep no separate language rules in this skill.
- `/readable-html-dossier` for the optional HTML delivery mode.

## Workflow

### 1. Name the reader and their common ground

Before touching code, state who the reader is and what they already know:
- what they certainly know (role, stack, product domain);
- what the project glossary defines (`CONTEXT.md` ubiquitous language);
- what is privileged — the module's internal mechanics the reader has never seen.

Spend the explanation budget on the privileged layer; skip what the reader already holds. Calibrate to _a knowledgeable engineer who has not touched this module_ — not a beginner, not the author.

Completion: one line naming the reader, and three explicit common-ground lists (knows / glossary / privileged).

### 2. Trace the data flow

Pick the **slicing criterion**: the user-visible outcome this explanation serves (e.g. "the list the user sees after editing a SKU"). Follow it in **execution order** — user action → request → query → transformation → outcome — and include only the code that can affect that outcome. This is the program-slicing unit: everything else is noise the reader would skim anyway.

Answer the three question types as you go, in labeled beats:
- _what_ — what the code does (implementation);
- _how_ — how it produces the outcome (the trace);
- _why_ — why it is structured this way (rationale).

Completion: an ordered list of beats from user action to outcome, each named with its file:line anchor, covering only code on the outcome's causal path.

### 3. Anchor the narrative on a small dataset

Build the _anchor_ that holds the whole narrative: a small dataset traced from the user's eyes into the app. Start with what the user brought and saw, follow it through the beats, and end at what the user sees. Use a real row when one exists; when none does, construct the smallest dataset that exercises the path. Walk it value-by-value in literal values, then **fade to the abstraction**: one sentence generalising ("for any row where X, Y happens"). The concrete instance comes first, the general rule second — both present, in that order. The mechanism detail of each beat (the SQL, the cast, the key) stays beside the story, not in it. The dataset stays real — every value in it traces to the code's actual data.

Completion: one concrete input traced from the user's eye through every beat with literal values, then one sentence stating the general rule it demonstrates.

### 4. Shape the narrative

Assemble in execution order: intent before mechanism, mechanism before rationale. Segment into beats of 5–10 lines of code with one idea each. Skip standard patterns the reader already knows (framework idioms, imports, null checks). End each beat with a one-line "what this enables next" so the reader always knows where they are in the flow.

Completion: a narrative that reads in execution order, intent-first, with every beat anchored and no re-explanation of what the reader already knows.

### 5. Write in the reader's language

Every engineering term gets a plain product-language equivalent or a first-use definition; project ubiquitous-language terms are allowed as-is (they are the reader's own glossary). File:line anchors sit beside each step as references; the sentences carry product language.

Completion: every term plain or glossed at first use, every file:line beside the story rather than in it, and a product-knowledgeable, code-naive reader can follow without looking anything up.

### 6. Deliver

Default: a normal conversational response — the narrative in the chat, markdown, with code references inline. The reader should be able to paraphrase it back.

Optional HTML: when the user asks for a dossier/HTML, hand the assembled narrative to `/readable-html-dossier` for the standalone report, and report its path.

Completion: the narrative delivered in the default mode the user expects (conversation, or HTML path when requested).

## Completion contract

The run is complete when the reader who did not write the code can paraphrase the implementation back: the user-visible outcome, the data path that produces it, and why the code is shaped that way.
