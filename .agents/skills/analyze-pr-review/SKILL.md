---
name: analyze-pr-review
description: Pull down review comments on the raised PR using graphql and present an analysis.
disable-model-invocation: true
---

Pull down unresolved review comments from the current raised PR.

Use `/github-graphql-first` to retrieve review threads and comments.

For each comment, gather the relevant code, callers, tests, and surrounding context before judging it.

Evaluate each comment using:

* **Claim** — What is the reviewer saying?
* **Verify** — Does the problem actually exist on current HEAD?
* **Severity** — Stated severity vs actual severity.
* **Blocking** — Should this block merge?
* **Reality** — Demonstrated problem, plausible risk, or theoretical concern?
* **Reproduce** — What concrete state/input causes it?
* **Impact** — What real user experience does this affect?
* **Scale** — If architectural/performance-related, when does it become a real problem?
* **Risk** — Risk of implementing the change vs leaving it unchanged.
* **Coverage** — What existing tests protect this behavior?
* **Regression** — For a confirmed bug, what is the smallest test that fails before the fix and passes after?
* **Gap** — If this is a bug, why did the existing tests miss it?
* **Prevention** — Could AGENTS.md, linting, types, tests, tooling, or architecture prevent this class of issue?
* **Complexity** — Is the suggested solution proportional to the demonstrated problem?
* **Staleness** — Has the referenced code changed since the comment was written?
* **Confidence** — High / medium / low, based on evidence.
* **Simplest correct action** — What is the smallest change, if any, that fully resolves the concern?

End every comment with exactly one disposition:

* **FIX NOW**
* **REPLY & RESOLVE**
* **DEFER**
* **CLARIFY**

Do not expand the PR with speculative refactors.

At the end, provide the **Merge Path**:

1. What must change before merge.
2. What only needs a reply/resolution.
3. What should be deferred.
4. What tests must pass or be added.
5. The fastest and simplest path to merge without compromising correctness or quality.

**Complete when:** every unresolved actionable comment has evidence, confidence, a disposition, and a simplest correct action.
