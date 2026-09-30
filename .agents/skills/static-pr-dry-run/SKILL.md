---
name: static-pr-dry-run
description: Static dry-run of a change set. Use when the user wants a pre-ship decision from repository evidence without running code, or an auditable source-traced case ledger with exact row counts.
disable-model-invocation: true
---

# Static PR dry-run

Assess `<base>..<head>` from source, contracts, configuration, existing tests, and PR metadata. Do not run builds, tests, application code, migrations, setup commands, or other repository code.

This is a bounded static review, not proof of all runtime behavior. State any exhaustiveness claim as: "exhaustive over the declared change manifest and obligation matrix; runtime behavior not established."

Keep the worktree unchanged. Reading existing CI results is allowed. A CI result counts as runtime evidence only when it applies to the exact reviewed head revision and the relevant check.

## Review model

An _obligation_ is one behavior claim that the review must resolve. Derive obligations from acceptance criteria, changed branches and outcomes, contracts, and affected boundaries.

A _seam_ is a producer-consumer hand-off where assumptions can disagree.

A _vertical_ is one ordered path from an entry point through its seams to one terminal outcome. Data or state variants remain cases on the same vertical unless they change the path or terminal outcome.

_Closure_ means every change-manifest item and discovered obligation maps to source evidence, one or more ledger cases, or an explicit gap.

## Workflow

### 1. Establish the evidence boundary

Resolve and record the base and head revisions. Read the PR description or linked specification, repository instructions, the complete diff, every changed file, relevant PR metadata, and existing tests that describe the changed behavior.

Create a change manifest. Give every diff hunk an ID. Split a hunk into multiple manifest rows when it contains more than one intended behavior.

For each manifest row, record:

- diff hunk ID and source locations
- intended behavior and its evidence source
- `RELATED`, `UNRELATED`, or `UNKNOWN`
- affected symbols or contracts
- unavailable evidence or conflicts between intent, contracts, and current behavior

Treat conflicting or missing intent as a gap. Do not choose an expected result without a cited source.

Completion: the base and head are explicit; every diff hunk appears in at least one manifest row; every row has a classification and intent source; every conflict or unavailable input is recorded as a gap.

### 2. Close the impact graph

Seed a work queue from every `RELATED` or `UNKNOWN` manifest row. For each queued symbol or contract, inspect direct callers, callees, configuration, schemas, persisted shapes, side effects, user-visible outcomes, and relevant tests.

Add an affected node when the change can alter its branch, contract, state transition, side effect, or terminal outcome.

Close an edge only when cited source evidence shows that an unchanged contract contains the effect. Record a gap when dynamic dispatch, reflection, generated code, external behavior, missing configuration, or unavailable source prevents closure.

Create stable IDs for:

- each seam
- each distinct vertical
- each obligation from intent, changed branches, seam contracts, state transitions, terminal outcomes, and material runtime properties

Completion: the work queue is empty; every discovered edge is closed by cited evidence or linked to a gap; every related manifest row maps to at least one obligation; every discovered seam and terminal outcome maps to an obligation.

### 3. Build the case set

Create an applicability matrix for every obligation with these columns:

- success
- rejection or failure
- boundary
- state
- interaction
- compatibility

Every cell must contain one or more case IDs or `N/A` with a source-backed reason.

Generate a case only when its preconditions or input can change a branch, contract, state transition, side effect, or terminal outcome. Generate combinations when conditions share control flow, data, state, or an effect and their combined result cannot be derived from the individual cases. For independent conditions, cite the independence evidence and cover them separately.

Store one row for each unique scenario. A case may reference several obligations, seams, or verticals. Assign one primary class from the applicability columns and optional secondary tags.

An existing test may supply a scenario or expected result. Store that scenario once and record the test as its origin. An unexecuted test does not establish that the implementation passes.

Completion: the applicability matrix has no blank cells; every obligation maps to a case or gap; duplicate scenario keys are zero; every case has a stable ID and exactly one primary class.

### 4. Source-trace every case

For each case, record concrete preconditions and input, then trace the ordered source path through relevant branches, refinements, transformations, calls, state transitions, and side effects.

Record one status:

- `SUPPORTED`: the expected result follows from the complete source path and contract-backed assumptions; no material runtime-only fact decides the result
- `DEFECT`: the source path proves a mismatch with the cited obligation
- `UNRESOLVED`: missing, dynamic, external, or runtime-only evidence decides the result

For `DEFECT`, cite the shortest source trace that proves the mismatch. For `UNRESOLVED`, cite the nearest unresolved source edge and name the missing evidence and exact check that would resolve it.

Runtime-only evidence includes dependency behavior, scheduling and concurrency outcomes, browser rendering or accessibility semantics, database and migration behavior, deployment configuration, and generated code that is not available for inspection.

Completion: every case has one status and a reproducible source trace; every unresolved case links to a gap and a decisive check or states that no decisive static check exists.

### 5. Reconcile the ledger and decide

Count unique ledger rows, not obligation links, seam links, vertical links, or test origins.

Require both invariants:

- `total = supported + defect + unresolved`
- `total = success + rejection/failure + boundary + state + interaction + compatibility`

Also report:

- duplicate scenario keys
- blank applicability cells
- resolved obligations over total obligations
- open impact-frontier gaps
- runtime checks already evidenced for the exact head revision
- runtime checks still required

Apply the repository's release policy when one exists. Otherwise classify findings as:

- `BLOCKER`: security exposure, data loss, irreversible unsafe effect, or broken core contract
- `HIGH`: reachable wrong behavior on an important path, unknown impact reach, or material unresolved behavior without safe containment
- `NON-BLOCKING`: a bounded issue that does not violate the stated acceptance or release criteria

Give exactly one verdict:

- `SHIP`: every material obligation is resolved, no finding violates release policy, and every required runtime check already has passing evidence for the exact head revision or is not needed
- `SHIP AFTER CHECKS`: no proven finding violates release policy, but named checks must pass before shipping; each check has a required result and an owner or responsible role
- `DO NOT SHIP`: a finding violates release policy, impact reach is unknown, a manifest item or material obligation is unassessed, or a material unresolved risk has no decisive pre-ship check

`SHIP AFTER CHECKS` means the change is not ready to ship yet.

Completion: both count equations reconcile; duplicate keys and blank cells are zero; every obligation is resolved or linked to a gap and required check; the verdict follows directly from the release policy and recorded evidence.

## Output contract

Lead with:

```md
BASIS: static review of <base>..<head>; no repository code executed
RUNTIME EVIDENCE: <none | exact-head checks and results>
VERDICT: <SHIP | SHIP AFTER CHECKS | DO NOT SHIP>
CASES: <total> ledger rows; <supported> SUPPORTED, <defect> DEFECT, <unresolved> UNRESOLVED
OBLIGATIONS: <resolved>/<total> resolved; <gaps> open gaps

## Required before ship
- <check, required result, owner or role, affected obligations>

## Findings
- [severity] `path:line` | obligation IDs | failure or risk | shortest proving trace | smallest safe fix

## Change manifest
| ID | Diff hunk | Locations | Classification | Intended behavior | Evidence | Obligations or gap |

## Impact inventory
| ID | Kind | Producer or entry | Consumer or outcome | Contract | Evidence |

## Obligation matrix
| Obligation | Claim | Evidence | Success | Failure | Boundary | State | Interaction | Compatibility |

## Case ledger
| Case | Obligations | Seam/vertical | Primary class | Tags | Preconditions and input | Source trace | Expected | Result | Status |

## Gaps and runtime checks
| Gap | Nearest source edge | Missing evidence | Decisive check | Required result | Owner or role |

## Count audit
- Status: <total> = <supported> + <defect> + <unresolved>
- Class: <total> = <success> + <failure> + <boundary> + <state> + <interaction> + <compatibility>
- Duplicate scenario keys: 0
- Blank applicability cells: 0
```

Include every ledger row, including `SUPPORTED` rows. If the complete report exceeds the response limit, write it to `/tmp/static-pr-dry-run-<short-head>.md` and return the path, basis, verdict, counts, findings, and required checks. Write inside the repository only when the user supplies that path explicitly.
