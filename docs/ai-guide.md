**⚠️ CRITICAL: NEVER COMMIT CHANGES UNLESS EXPLICITLY ASKED BY THE USER ⚠️**

---

## Technology Documentation Lookup Protocol

**MANDATORY: When the user mentions ANY technology, library, framework, or tool, you MUST look up current documentation FIRST before providing guidance.**

### Lookup Priority Order

1. **context7** (HIGHEST PRIORITY) - Official up-to-date library/framework docs
   ```
   Example: context7_resolve-library-id(libraryName: "react")
            context7_get-library-docs(context7CompatibleLibraryID: "/facebook/react")
   ```

2. **webfetch** - Official documentation websites
   ```
   Example: webfetch(url: "https://nextjs.org/docs", format: "markdown")
   ```

3. **gh_grep** - Real-world production code examples
   ```
   Example: gh_grep_searchGitHub(query: "useState(", language: ["TypeScript", "TSX"])
   ```

### When to Use Each Tool

| Technology Mentioned | Action Required | Tool to Use | Example |
|---------------------|-----------------|-------------|---------|
| Framework/Library | Get official API docs | context7 | "React hooks" → context7(react) |
| Configuration | Fetch current syntax | webfetch | "Tailwind config" → webfetch(tailwindcss.com/docs/configuration) |
| Best Practices | Find real implementations | gh_grep | "Error boundaries" → gh_grep("ErrorBoundary", language=["TSX"]) |
| Version-specific | Check current docs | context7 + webfetch | "Next.js 15 API" → context7(/vercel/next.js/v15) |

### Workflow Example

```
User mentions: "Add authentication with NextAuth"

REQUIRED STEPS:
1. context7_resolve-library-id(libraryName: "next-auth")
2. context7_get-library-docs(context7CompatibleLibraryID: "/nextauthjs/next-auth", topic: "authentication")
3. gh_grep_searchGitHub(query: "NextAuth(", language: ["TypeScript"], repo: "nextauthjs/next-auth-example")
4. Only THEN provide implementation guidance based on CURRENT documentation
```

### Critical Rules

- ❌ **NEVER** rely on training data knowledge for technology guidance
- ✅ **ALWAYS** verify current API syntax, configuration, and patterns
- ✅ **CHECK** for version-specific changes (especially major versions)
- ✅ **VALIDATE** deprecated patterns before suggesting them
- ✅ **SEARCH** for production examples when patterns are unclear

### Technologies Requiring Immediate Lookup

**Always lookup before advising on:**
- JavaScript/TypeScript frameworks (React, Vue, Angular, Svelte, Next.js)
- Build tools (Vite, Webpack, Turbopack, esbuild)
- State management (Redux, Zustand, Jotai, Recoil)
- UI libraries (Tailwind, MUI, Chakra, shadcn/ui)
- Backend frameworks (Express, Fastify, NestJS, Hono)
- ORMs (Prisma, Drizzle, TypeORM)
- Testing tools (Vitest, Jest, Playwright, Cypress)
- AI/ML libraries (LangChain, OpenAI SDK, Anthropic SDK)

**Example of CORRECT workflow:**

```
User: "Help me set up Drizzle ORM with PostgreSQL"

Assistant MUST do:
1. context7_resolve-library-id(libraryName: "drizzle-orm")
2. context7_get-library-docs(context7CompatibleLibraryID: "/drizzle-team/drizzle-orm", topic: "postgresql setup")
3. gh_grep_searchGitHub(query: "drizzle(", language: ["TypeScript"])
4. Provide setup guidance based on CURRENT docs (not training data)

Assistant MUST NOT do:
❌ Suggest setup steps from memory/training data
❌ Use outdated API patterns
❌ Skip documentation lookup
```

---

## Quick Start

### Code Review Workflow
1. **Review changes**: `git diff` before committing
2. **Run CodeRabbit**: `coderabbit review --plain` for security, performance, best practices
3. **Apply feedback**: Fix issues, improve code quality
4. **Stage & commit**: Use conventional commit format

### Core Philosophy
- **Fail Fast, Defend Early**: Validate inputs, fail loudly with clear errors
- **Edge-Case Driven**: Consider null/undefined, empty arrays, out-of-range values
- **Clarity > Cleverness**: Code readable by new engineer in minutes, not hours

### Language Preferences
- **TypeScript** (never plain JavaScript unless absolutely unavoidable)
- **ESM** syntax — no `require()` or CommonJS
- `async/await` over `.then()` chains

---

## Language-Specific Guidelines

### TypeScript Guidelines
- Use `interface` (prefixed with `I`) over `type` unless extending
- Prefix types with `T`
- Avoid `any`; use `unknown` if unavoidable
- Mark arrays as `readonly string[]` over `string[]`
- Use `as const` to make types stricter
- Use **zod** for runtime validation at all input/output boundaries

### Shell Scripts (Bash/Zsh)
- Use `#!/bin/bash` or `#!/usr/bin/env bash` as shebang
- Always include `set -euo pipefail` for robustness
- Use shellcheck for linting: `shellcheck **/*.sh`
- Naming: snake_case for variables/functions (e.g., `script_dir`)
- Quote variables: `"$variable"` not `$variable`
- Use `[[ ]]` over `[ ]` for conditionals
- Document complex logic with comments
- Pass arguments with `"$@"` to preserve spacing

### Frontend (React/Next.js)
- Functional components with hooks
- Avoid misuse of `useEffect` (derive state where possible)
- Prefer **TailwindCSS** utilities over CSS modules
- Schema validation (`zod`) for forms and APIs
- Optimize rendering (memoize intelligently, don't overdo)

---

## Coding Principles

### Defensive Programming
- Always null-check inputs and external data
- Validate function parameters at the top (fail fast)
- Avoid silent failures — log or throw with meaningful messages
- Treat every exported function as if it could be called by untrusted code

### Functional Style
- Pure functions by default (no hidden side effects)
- Use `.map`, `.filter`, `.reduce` only when semantically clear
- Use `for` loops for performance-sensitive code
- Prefer helper functions over inline duplication

### Control Flow
- Guard clauses & early returns > deep nesting
- Avoid complex ternaries inside JSX
- Use `switch` only when semantically appropriate
- Use map (object) based logic for complicated logic (strategy pattern)
- Use `VALUES.includes` pattern over multi OR conditions

### Performance-Sensitive Coding
- Avoid unnecessary allocations or object churn
- Prefer `Set` for `.has()` lookups
- Don't use `.forEach`/`.map` in critical paths — use `for`
- Avoid closures in hot loops
- Profile before micro-optimizing

### Quality & Maintainability
- Clear, meaningful names (no abbreviations)
- Prefer clarity over comments — self-documenting code
- Functions should be **short, composable, <30 lines** unless justified
- Prefer object-based params if >2 arguments
- Destructure params in function signatures, not inside function bodies
- Follow https://refactoring.guru/refactoring guidelines

---

## OpenCode Customization

### Custom Tools (.opencode/tool/)
- Use TypeScript with `@opencode-ai/plugin` SDK
- Export with `tool()` helper for type-safety and validation
- Tools auto-load from `.opencode/tool/` or `~/.config/opencode/tool/`
- Filename becomes tool name (e.g., `list-mcp.ts` → `list-mcp` tool)
- Cannot be invoked directly with Node.js — only through OpenCode
- Use `tool.schema` (Zod) for argument validation

### Custom Agents (.opencode/agent/)
- Markdown files with YAML frontmatter
- Specify: name, description, mode (primary/subagent), temperature
- Choose MCP servers wisely:
  - **Subagents**: 2-3 focused servers (e.g., git agent: octocode, context7)
  - **Primary agents**: 5-10 servers (e.g., sales agent: 7 servers)
- Temperature guide:
  - 0.0-0.2: Deterministic (git, code generation)
  - 0.4-0.6: Balanced (general coding)
  - 0.6-0.8: Creative (writing, proposals)

### Custom Commands (.opencode/command/)
- Markdown files with YAML frontmatter
- Can route to agents with `agent: <name>` field
- Use `$ARGUMENTS` for user input
- Set `subtask: true` to invoke subagents
- Commands are invoked with `/command-name`

---

## Tool Strategy

### File Operation Priority
1. **Read tool** - Direct file access (FASTEST)
   - Use for: Known file paths, configuration files
   - Example: Read package.json, tsconfig.json

2. **Octocode** - GitHub repo access
   - Use for: Remote repos, no local clone needed
   - Example: Study public repos without cloning

3. **Desktop Commander** - Advanced file operations
   - Use for: Search, process management, system operations
   - Example: Search for patterns, manage processes

### Task Tool Strategy
**When to Use Task Tool**:
- Open-ended searches (don't know exact file/pattern)
- Exploratory codebase analysis
- Multi-step research workflows
- When you need multiple search attempts

**When NOT to Use Task Tool**:
- Know exact file path → Use Read tool
- Know class/function name → Use Glob/Grep directly
- Simple file operations → Use basic tools

**Examples**:
❌ Bad: Task("Find the UserController class")
✅ Good: grep("class UserController", include="*.ts")

❌ Bad: Task("Read package.json")
✅ Good: read("package.json")

### Memory MCP Usage
**When to Use Memory**:
- Store project-specific facts across sessions
- Remember user preferences and coding style
- Track codebase architecture and patterns
- Link agents to codebases they work with

**Entity Design**:
- **Codebases**: Store project metadata (type, language, architecture)
- **Modules**: Store component/module information
- **Agents**: Store agent context and capabilities
- **Relations**: Link entities with meaningful relations

**Best Practices**:
- Use descriptive entity types: `codebase`, `module`, `agent`, `pattern`
- Store observations as facts (not prose)
- Create relations for discoverability: `contains`, `uses`, `depends_on`, `operates_on`
- Update agents when studying new codebases

---

## MCP Servers

### Quick Reference Matrix

| Server | Type | Use Case | Priority |
|--------|------|----------|----------|
| context7 | Docs | Latest framework docs | HIGH |
| octocode | GitHub | Repo analysis | HIGH |
| memory | Storage | Cross-session memory | HIGH |
| aid | Analysis | Code structure | MEDIUM |
| gh_grep | Search | Real-world patterns | MEDIUM |
| augments | Docs | Framework examples | MEDIUM |
| playwright | Browser | UI testing | AS_NEEDED |
| next-devtools | Dev | Next.js debugging | AS_NEEDED |
| desktop-commander | System | File ops | AS_NEEDED |
| mindpilot | Viz | Diagrams | AS_NEEDED |
| ddg-search | Search | Web search | LOW |
| sequential-thinking | Reasoning | Complex problems | LOW |
| mcp-compass | Discovery | Find MCP servers | LOW |
| chrome-devtools | Browser | Deep debugging | LOW |

### Workflow Integration
- **Study workflow**: octocode + memory + aid
- **Documentation**: context7 + augments + gh_grep
- **Development**: next-devtools + playwright
- **Research**: ddg-search + gh_grep

### Octocode Workflows
**Repository Discovery**:
1. `githubSearchRepositories`: Find repos by topic/keywords
2. `githubViewRepoStructure`: Get directory tree (depth=1 for overview, depth=2 for deep dive)
3. `githubSearchCode`: Search for code patterns (match="path" for files, match="file" for content)
4. `githubGetFileContent`: Read specific files (use `matchString` for targeted extraction)

**Best Practices**:
- Start with `githubViewRepoStructure` (depth=1) for overview
- Use `match="path"` for fast file discovery
- Use `match="file"` with `limit=5` for detailed matches
- Always scope searches with owner/repo to avoid rate limits
- Use `matchString` with `matchStringContextLines` for precise content extraction

### Server Categories

#### Documentation & Research
- **context7**: Fetch up-to-date library/framework docs (e.g., React, Next.js, MongoDB)
  - Use when: Need official API docs or examples
  - Example: "Get Next.js App Router documentation"

- **augments**: Framework documentation and code examples
  - Use when: Need framework-specific patterns
  - Example: "Show TailwindCSS grid examples"

- **gh_grep**: Search GitHub code repositories for real-world examples
  - Use when: Need production code patterns
  - Example: "Find useState patterns in popular React repos"

#### Code Analysis & GitHub
- **octocode**: Advanced GitHub operations (search code, PRs, repo structure)
  - Use when: Deep GitHub codebase analysis
  - Example: "Search for auth patterns in facebook/react"

- **aid**: AI Distiller - extract code structure, generate analysis prompts
  - Use when: Need code signatures, bug hunting, refactoring suggestions
  - Example: "Distill API signatures from src/"

#### Development Tools
- **next-devtools**: Next.js runtime debugging, cache components, upgrades
  - Use when: Working with Next.js projects
  - Example: "Check Next.js dev server errors"

- **playwright**: Browser automation for testing and verification
  - Use when: Need to test web apps or verify UI
  - Example: "Navigate to localhost:3000 and test login flow"

- **chrome-devtools**: Chrome DevTools protocol for browser inspection
  - Use when: Need deep browser debugging
  - Example: "Inspect network requests on page load"

#### File & System Operations
- **desktop-commander**: Advanced file operations, process management, search
  - Use when: Need file manipulation beyond basic tools
  - Example: "Search for 'validateUser' in src/"

- **mindpilot**: Generate Mermaid diagrams (flowcharts, sequences, architecture)
  - Use when: Need visual documentation
  - Example: "Create architecture diagram for auth flow"

#### Utilities
- **ddg-search**: DuckDuckGo web search for general information
  - Use when: Need external knowledge or documentation
  - Example: "Search for TypeScript best practices"

- **sequential-thinking**: Structured reasoning for complex problems
  - Use when: Need systematic problem-solving
  - Example: "Break down multi-step refactoring task"

- **memory**: Persistent context storage across sessions
  - Use when: Need to remember facts long-term
  - Example: "Remember user prefers Zod for validation"

- **mcp-compass**: Discover and recommend MCP servers
  - Use when: Looking for new MCP capabilities
  - Example: "Find MCP server for AWS Lambda"

### Usage Guidelines
- **Prefer specialized tools**: Use MCP servers over generic bash commands when available
- **Check enabled status**: Only enabled servers are accessible
- **Context efficiency**: Use Task tool for exploratory searches to reduce token usage
- **Parallel execution**: Batch independent MCP calls in a single message

## Git Usage

- Always study the git diff before committing.
- **NEVER** commit unless you are ASKED to.
- You may ask the user to use the gh cli if it is relevant (Creating PR or reading linked issue)
- If the branch named contains a number, it is the issue number, you can use gh to study the linked issue
- Keep the commit message short and descriptive, follow the [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) guidelines.
- If there is extra detail regarding the commit, it should be in the commit description.
- When the user asks you to review changes, you must ask them for the base branch and then study the relevant diff.

### Code Review Workflow

**Before Committing**:
1. Review your changes: `git diff`
2. Run CodeRabbit: `coderabbit review --plain`
3. Apply feedback (security, performance, best practices)
4. Stage changes: `git add <files>`
5. Commit with conventional format

**CodeRabbit Focus Areas**:
- Security vulnerabilities
- Performance issues
- Best practice violations
- Code smells and anti-patterns
- Type safety improvements

---

## Engineer's Mindset

- Ship code you'd trust your **future self** to maintain.
- Don't chase speed at the expense of stability.
- AI-generated code must **pass your quality checks**, not the other way around.
