Important: Run `coderabbit review --plain` to get comprehensive code analysis and improvement suggestions. Apply the feedback to write **cleaner, safer, and more maintainable code**.

## Core Philosophy

- **Fail Fast, Defend Early**:  
  Every function should validate its inputs and fail loudly with clear errors.
- **Edge-Case Driven**:  
  Always consider null/undefined, empty arrays/objects, out-of-range values, and unexpected inputs.
- **Clarity > Cleverness**:  
  Code should be readable by a new engineer in minutes, not hours.

---

## Language Preferences

- Use **TypeScript** (never plain JavaScript unless absolutely unavoidable).
- Prefer **ESM** syntax — no `require()` or CommonJS.
- Use `async/await` over `.then()` chains.

---

## TypeScript Guidelines

- Use `interface` (prefixed with `I`) over `type` unless extending.
- Prefix types with `T`.
- Avoid `any`; use `unknown` if unavoidable.
- Mark arrays as `readonly string[]` over `string[]`.
- Use **zod** for runtime validation at all input/output boundaries.

---

## Defensive Programming

- Always null-check inputs and external data.
- Validate function parameters at the top (fail fast).
- Avoid silent failures — log or throw with meaningful messages.
- Treat every exported function as if it could be called by untrusted code.

---

## Functional Style

- Pure functions by default (no hidden side effects).
- Use `.map`, `.filter`, `.reduce` only when semantically clear.
- Use `for` loops for performance-sensitive code.
- Prefer helper functions over inline duplication.

---

## Control Flow

- Guard clauses & early returns > deep nesting.
- Avoid complex ternaries inside JSX.
- Use `switch` only when semantically appropriate.

---

## Frontend (React/Next.js)

- Functional components with hooks.
- Avoid misuse of `useEffect` (derive state where possible).
- Prefer **TailwindCSS** utilities over CSS modules.
- Schema validation (`zod`) for forms and APIs.
- Optimize rendering (memoize intelligently, don’t overdo).

---

## Performance-Sensitive Coding

- Avoid unnecessary allocations or object churn.
- Prefer `Set` for `.has()` lookups.
- Don’t use `.forEach`/`.map` in critical paths — use `for`.
- Avoid closures in hot loops.
- Profile before micro-optimizing.

---

## Quality & Maintainability

- Clear, meaningful names (no abbreviations).
- Prefer clarity over comments — self-documenting code.
- Functions should be **short, composable, <30 lines** unless justified.
- Prefer object-based params if >2 arguments.
- Destructure params in function signatures, not inside function bodies.

---

## Testing & Verification

- Always add **unit tests** for core logic.
- Focus tests on edge cases and failure paths (not just happy path).
- Mock external dependencies cleanly.
- Ensure all public APIs are validated and tested.

---

## Engineer’s Mindset

- Ship code you’d trust your **future self** to maintain.
- Don’t chase speed at the expense of stability.
- AI-generated code must **pass your quality checks**, not the other way around.
