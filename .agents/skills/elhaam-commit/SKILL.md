---
name: elhaam-commit
description: >
  Write git commit messages in Elhaam's handwritten style — a terse single-liner,
  lowercase, bare type, no scope, no body. Distilled from ~370 hand-written commits
  in party-rental-site (Aug–Nov 2025). Use when writing any commit message: "commit",
  "commit this", "write a commit", "commit message", "staging changes", "/commit".
---

Write the message the way he did by hand: a **single-liner** from his log — subject only, no body, no scope.

## Shape (check every line against these)

- **Subject only.** A change that needs explaining is too big — split the commit.
- **Bare type first.** `feat:`, `fix:`, `chore:`, `refactor:`, `perf:`, `docs:` — no `(scope)`.
- **Lowercase after the colon.** `feat: link based navigation instead of state based` — not `Feat:` / `Link based`.
- **Terse and concrete.** ~30 chars, name the thing: `feat: AddToCart.tsx`, `feat: bun.lock`, `fix: typo`. Cut filler.
- **Loose human phrasing.** Past tense and fragments are fine — `refactor: converted scattered local storage changes into a centerlized object`. Not AI-formal complete sentences.
- **Honest about state.** A checkpoint is a checkpoint: `wip`, `tmp: build issues fixed`, `feat: dummy commit for vercel deploy`.

## His type vocabulary

| Type | When |
|---|---|
| `feat:` | new behavior (most common) |
| `fix:` | bug fix |
| `fixes:` | batch of fixes |
| `refactor:` / `refactoring:` | restructure, both used |
| `chore:` | tooling, deps, cleanup |
| `perf:` | performance |
| `docs:` | docs |
| `wip` / `tmp:` | honest checkpoint |

## Examples (from his log)

```
feat: link based navigation instead of state based
fix: typo
fixes: size of the logo
refactor: converted scattered local storage changes into a centerlized object
feat: AddToCart.tsx
feat: 9AM early delivery
chore: removed unused imports
wip
```

## Done when

Every message is a single-liner that reads like a line from his log — terse, lowercase, bare type, no body. If a message would look out of place in the list above, rewrite it until it fits.
