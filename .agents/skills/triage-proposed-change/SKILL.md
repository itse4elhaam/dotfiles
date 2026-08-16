---
name: triage-proposed-change
description: Triage a proposed code change before it is implemented: assign a risk level, estimate the fix size, and name the test debt (existing pins, required test changes, required new tests) plus the architectural and data-flow consequences. Use when a change is proposed and needs a go/no-go risk assessment before approval, when reviewing a PR or a plan, or when asked what a change would take to fix, test, or safely land.
---

# Triage a Proposed Change

Turn a proposed change into a precise go/no-go assessment. The report is the deliverable: a fixed set of questions, each answered in one line, ending in one risk level. The human who must approve the change reads the report, not the reasoning behind it.

**Leading words:** _reach_, every surface the change can affect; _pins_, tests or validations that lock the core behavior so a regression fails loudly; _reversible_, a change whose failure the rollback fully undoes; _silent_, a break that produces a wrong answer instead of an error — the expensive kind.

**Scope.** Produces an assessment, not an implementation. It does not write the change, and it does not fix the tests; it says what each would take. The change may be a proposal, a branch, or a PR — triage what is proposed, and flag what is not yet specified rather than assuming it.

## Workflow

Answer the thirteen questions in order. Each ends on a completion criterion; do not move on until it is met. The first twelve gather evidence; question 13 assigns the level from that evidence — never before it.

### 1. What is the change?

State the change in one sentence: the behavior it alters, in the product's language, not the code's. The behavior is what is being risked; the syntax is how it is written.

Completion: a sentence a non-author can verify against the diff or proposal.

### 2. How many lines would it take to fix?

Estimate the size of the change as written code: a band, not a false-precise number, with the files that carry it. For a bug fix, the fix; for a feature, the implementation.

Completion: a line band plus the files, or an explicit "cannot be estimated" with the reason.

### 3. What is its reach?

Name every surface the change can affect: callers, modules, services, users, storage, and other code paths. Trace the callers beyond the changed files — the change's _reach_ is what it can affect, not what it edits.

Completion: every surface the change can touch is named, or "reach limited to [files]" with the boundary stated.

### 4. Is it reversible?

Decide whether a failure survives the rollback. Check for external side effects (emails, webhooks, payments), data deletion or mutation outside migrations, in-flight job payloads, and object destruction. A code rollback is not a full rollback if it leaves such effects behind.

Completion: a verdict — reversible or irreversible — with the irreversible consequence named when it applies.

### 5. What pins the core behavior?

Find the existing tests or validations that lock the behavior this change touches. Name them: file, test, what they assert. A pin is what turns a future regression into a red suite instead of a silent deploy.

Completion: every behavior the change touches is either named with its pinning test or explicitly flagged unpinned.

### 6. What test changes does it require?

List the existing tests that must be modified because the change alters the behavior they assert. A test that breaks because the behavior changed is a required change, not a failure of the change.

Completion: every affected existing test named, or "no existing test changes" stated.

### 7. What new tests does it require?

List the tests that must be written to pin the new or altered behavior. A behavior change without a new pin is a regression hole; name the hole when it exists.

Completion: every new behavior from step 1 is paired with a test to write, or the absence is flagged as the regression hole it is.

### 8. Does it change the data flow?

Decide whether the change alters who produces, transports, stores, or consumes what. Check field shapes, serialization, storage, message types, and request/response contracts — including the _silent_ kind: same shape, changed meaning (defaults, timezone, precision, error codes, sort order).

Completion: the data-flow change stated, or "no data-flow change" with the boundary that proves it.

### 9. What architecture does it commit to?

Name the durable direction the change commits the codebase to: new seams, coupling, module boundaries, or tech choices that outlive this change. The commitment is what the next change inherits; a contained fix commits nothing.

Completion: the architectural commitment named, or "none — contained" stated with the boundary that keeps it contained.

### 10. Does it touch a contract or security surface?

Name any external contract (public API, wire format, enums, deprecations) or security surface (auth, tokens, permissions, secrets) the change reaches. These dominate risk regardless of line count.

Completion: every contract or security surface touched is named, or "none" stated.

### 11. How would we know it broke?

Decide whether a failure is _loud_ (synchronous error, failed test, alert) or _silent_ (wrong value, no alert), and whether telemetry exists on the changed path. A _silent_ failure that nothing watches is effectively permanent.

Completion: a detection mode named for the change's failure modes, or "undetectable" stated as the finding it is.

### 12. What containment exists?

Name the path back if it breaks: feature flag, canary, kill-switch, tested rollback, N-1 compatibility. A change with a containment path is less risky than an identical one without; a change with no path is a finding, not a skip.

Completion: a concrete containment path named, or "no containment" stated.

### 13. Assign the risk level

Assign exactly one level from the risk ladder, driven by the evidence above — reach, reversibility, surfaces, detection, containment. The level is a verdict on the change as proposed, not as it could be after mitigation.

Completion: one level from the ladder, consistent with steps 3, 4, 10, 11, and 12, with the deciding evidence cited.

## Risk ladder

| Level | Name | Definition |
|---|---|---|
| **1** | **LOW** | Cosmetic or additive; cannot change runtime behavior or stored data; rollback is complete. |
| **2** | **MEDIUM** | Changes internal behavior or contracts, but every consumer is updated in the same change; rollback is a code rollback; no migration, no external side effects. |
| **3** | **HIGH** | Touches security, data, migrations, or shared/cross-service code; needs a coordinated rollout; rollback is multi-step or flag-dependent; or reach is wide. |
| **4** | **CRITICAL** | Irreversible consequences (data loss, unsendable side effects, in-flight jobs) or cross-repo contract breakage; requires sign-off, a containment plan, and a rollback drill before merge. |
| **5** | **BLOCKED** | Core behavior unpinned, reach unknown, or irreversible with no containment — no-go as proposed. |

**Modifiers** (applied to the evidence, never to a level already assigned): a feature flag that fully gates the change lowers it one step (never below MEDIUM, never from CRITICAL); external side effects or security-surface touches raise it one step regardless of size; purely additive changes can lower within LOW/MEDIUM.

## Guardrails

### Rationalizations that hide risk

| Rationalization | Correction |
|---|---|
| "It's a small change." | Size is not risk: one auth condition can be HIGH while a 300-line refactor is LOW. The ladder runs on reach and reversibility, not line count. |
| "We can revert it." | Revert only undoes code. Emails sent, data deleted, and jobs already processed survive the rollback — those make it irreversible. |
| "The tests will catch it." | Only the pins catch it. If step 5 found the behavior unpinned, a green suite proves nothing about it. |
| "The tests pass." | Tests pass against the old behavior; step 6 names which tests this change is allowed to break. A change that needs no test change and adds no pin changed nothing observable. |
| "It's additive, so it's safe." | Additive shapes can still be _silently_ breaking: a new default, a changed error code, a reordered result. Step 8 checks meaning, not just shape. |
| "We'll watch it in prod." | Watching is only detection, and only if something is watching. Step 11 names the detection mode; "we'll watch" with no alert is not one. |
| "The architecture will sort itself out." | Step 13 forces a decision now, because the level gates whether the change can merge at all. |

## Output format

Deliver the report in this exact order, one line per item, no prose between items:

```
RISK: <level> — <one-line evidence citing reach/reversibility/surface>
CHANGE: <one sentence from step 1>
SIZE: <band> across <files>
PINS: <named pins, or "core behavior unpinned">
TEST CHANGES: <named existing tests, or "none">
NEW TESTS: <named tests, or "none">
DATA FLOW: <change or "unchanged">
CONTRACT/SECURITY: <surfaces or "none">
DETECTION: <loud/silent + what watches it>
CONTAINMENT: <path or "none">
ARCHITECTURE: <durable direction, or "none">
REACH: <surfaces from step 3>
UNKNOWNS: <every gap in the evidence>
```

## Verification

Before delivering, confirm every item:

- The RISK line cites evidence from the workflow, not an impression.
- Every behavior the change touches is pinned or flagged unpinned — never silently assumed covered.
- The SIZE band matches the reach, and the files are named.
- DATA FLOW and CONTRACT/SECURITY are answered even when the answer is "none" — an empty answer is a claim, not an omission.
- DETECTION names who or what watches, not a vague "monitoring".
- UNKNOWNS lists every gap, including anything the proposal left unspecified.
- The report is written for the human who must approve: product language first, engineering terms glossed.

## Done when

The human who must approve the change can answer, from the report alone: how risky it is and why, how big it is, what it breaks, what it needs, whether it moves data, and what architecture it commits to — and has one level to accept, gate, or reject.
