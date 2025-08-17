# Gemini Style Guide

## Language Preferences

- Use **TypeScript** over JavaScript wherever possible.
- Prefer **ESM** syntax. Avoid `require()` or CommonJS unless necessary.
- Use `async/await` over `.then()` chains.
- Prefer concise, readable, and performant code.

---

## TypeScript Guidelines

- Use `interface` over `type` unless extending.
- Always prepend I with interfaces and T with types.
- Avoid `any`; use `unknown` if necessary.
- Prefer `readonly` arrays: `readonly string[]` over `string[]`.
- Lean on `zod` for runtime validation.

---

## Functional Style

- Prefer **pure functions** with no side effects unless explicitly required.
- Use `.map`, `.filter`, `.reduce` judiciously — don't chain unnecessarily.
- Use `for` loops for performance-sensitive logic.
- Prefer helper functions over inline duplication.

---

## Control Flow

- Use early returns and guard claues to avoid deep nesting.
- Don't use ternaries inside JSX or deeply nested logic.
- Use `switch` sparingly and only when semantically clear.

## Frontend (React/Next.js)

- Use functional components with hooks.
- Avoid `useEffect` misuse — prefer derived state and signals if available.
- Prefer `tailwindcss` or utility-first styles over CSS modules.
- Use `zod` for schema validation, especially in forms and APIs.
- Avoid unnecessary re-renders (memoize when needed).

---

## Performance-Sensitive Coding

- Avoid unnecessary allocations or abstractions in tight loops.
- Use `Set` for fast `.has()` checks.
- Avoid `forEach`/`map`/`filter` in critical paths — use `for` when performance matters.
- Avoid closures in loops unless essential.
- Profile before optimizing.

## Misc

- Use meaningful variable and function names, not abbreviations.
- prefer clear code over comments unless really needed
- Prefer clarity over cleverness — future you will thank you.
- Write short, composable utilities. Avoid deep object mutation.
- Keep functions under 30 lines unless justified - split functions always
- if params are > 2, prefer object based params
- destructure stuff in the params directly not below in seperate line

