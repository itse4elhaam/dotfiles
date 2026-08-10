---
name: analyze-pr-review
description: Pull down review comments on the raised PR using graphql and present an analysis
disable-model-invocation: true
---

Pull down review comments from the current raised PR, for each of the pulled comment, strive to gather relevant context and then present an analysis with these included:

Use /github-graphql-first to pull down the comments.

1. Stated severity vs actual severity
2. Blocking vs non-blocking
3. Is this suggesting a solution to a problem that only exists in theory?
4. What real user experience does this impact?
5. If an architectural issue, at what scale would this become a problem?
6. What is the risk level implementing this vs not implementing this?
7. What tests do we have related to this that would ensure this "suggested" change doesn't cause a regression?
8. If it is a bug, why didn't our tests catch this?
9. Is this a problem that's caused by how our AGENTs.md, linting and tests are structed? Can we make a structural change to prevent this in the future?
10. Is the suggested solution too complex for a simpler problem?

At the end, state the fastest and simplest way to, without compromising correctness and quality, get this merged.
