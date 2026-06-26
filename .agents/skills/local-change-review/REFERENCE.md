# local-change-review — Reference

## Change-pattern taxonomy

The agent groups changes by **shared intent**. Use the table below as a guide, not a rigid spec — intent is what matters, not the label.

| Pattern | Signals | Commit-type hint |
|---|---|---|
| Refactor: rename | File renamed, references updated across files, no logic change | `refactor:` |
| Refactor: extract | New module/function file, old caller updated to use it | `refactor:` |
| Refactor: inline | Function removed, body folded into callers | `refactor:` |
| Fix: bug | Error/handle path added, assertion strengthened, regression test added | `fix:` |
| Fix: revert | `git log` shows last commit being undone | `revert:` |
| Feat: new surface | New exported symbol, new route, new CLI flag, new public type | `feat:` |
| Feat: extend | Existing exported symbol gains new param/branch | `feat:` |
| Config/infra | `*.config.*`, `package.json`, `tsconfig.json`, `Dockerfile`, CI yaml, env files | `chore:` or `build:` |
| Docs | `*.md`, comment-only changes, README updates | `docs:` |
| Tests | `*.test.*`, `*.spec.*`, snapshot files, fixture data | `test:` |
| Chore | Whitespace, formatting, `.gitignore`, `.editorconfig` | `chore:` |
| Migration | Files under `migrations/`, `*.sql` schema changes, adapter updates | per repo convention |
| Secrets | `.env*`, `*.pem`, `*.key`, tokens in code | (special — see STOP conditions) |

## When two files *look* like one group but aren't

- A `refactor:` rename of `foo.ts` → `bar.ts` **and** a `fix:` inside `bar.ts` are two groups. The first group is the rename only (file move + import updates); the second is the in-place logic edit.
- If you cannot split cleanly because Git records them as one hunk, merge them and note the merge in the explanation block.

## When the working tree has both staged and unstaged changes

- Treat the **already-staged** set as the user's prior intent. **Do not unstage** it unless it conflicts with a group boundary. If it does, surface the conflict and ask before restaging.
- A path that is both staged and unstaged (i.e., has staged changes and further unstaged edits) means the user staged an *earlier version* of the file. Surface this clearly: "### Note: `path` has staged changes (earlier) and unstaged changes (later) — treated as two groups: Group A (staged version), Group B (remaining unstaged delta)."

## Git plumbing reference

| Goal | Command | Notes |
|---|---|---|
| List changes | `git status --porcelain=v1` | One line per path, machine-readable |
| Unstaged diff | `git diff` | Working tree vs index |
| Staged diff | `git diff --staged` | Index vs HEAD |
| Stage specific paths | `git add <path...>` | Never `git add -A` in this workflow |
| Clear index | `git reset` | No flag — only unstages, working tree untouched |
| File rename detection | `git diff --find-renames=50% -M` | Helps group renames with their reference updates |
| Detect binary | `git diff --numstat` (`-` in place of counts = binary) | Skip diffstat for binary files |
| Detect large files | `git diff --stat \| sort -k3 -n` | Warn on hunks > ~200 LOC |

## Edge cases

### Empty diff after grouping
A group has paths but `git diff --staged` is empty — that means those paths are **identical to HEAD**. This happens when the working tree had changes that were already part of a prior commit and then reverted. Surface as "Group N: no net change (reverted)", with the file list. Skip the explanation block — note only the revert.

### Untracked files
Untracked files (`??` in porcelain) are part of the review. Stage them like any other path. Note in the explanation block that they are **new files** — UX impact usually "new capability" or "new module exposes …".

### Submodule changes
A submodule pointer change is its own group (`chore:`), with the submodule's internal diff summarized as "submodule <name> advanced from <shA> to <shB>, <N> commits". Do not recurse into the submodule in this workflow unless user explicitly asks.

### LFS / large diffs
If the diff or any single hunk exceeds ~1000 LOC, still group it, but in the explanation block use `git diff --stat <paths>` only and summarize in prose. Do not paste the whole diff.

## Verification rubric

Run these in order, fastest first:

1. **Typecheck** — `tsc --noEmit`, `mypy`, `pyright`, etc. (project-appropriate)
2. **Lint** — `eslint`, `ruff`, `golangci-lint`, etc., on the changed paths only
3. **Tests** — smallest reachable test set for the changed paths:
   - Jest/Vitest: `--testPathPattern` restricted to changed files' siblings
   - pytest: `pytest <changed_test_files>`
   - Go: `go test ./<changed_package>/...`
4. **Manual** — only if the agent cannot run any of the above. State clearly what manual step would verify.

If **nothing** was run for a group, the "How verified" section must say:
```
### How verified
- Tests: none run — no project test runner detected
- Manual: recommend running <specific command> against <specific scenario>
- Static: none run
```

Never fabricate test output. Never say "verified" when only "ran without errors" was observed — those are different claims.