---
description: Study current repository by analyzing project structure and key files (optional focus on specific module via arguments)
agent: build
---

Study the current repository to gain comprehensive context about the codebase.

**Arguments**: $ARGUMENTS (optional) - Specify module/directory to focus on (e.g., "auth module", "src/api", "database layer")

## MCP Server Integration

Before starting analysis, **ALWAYS** call the `list-mcp` tool to identify which MCP servers are available and relevant for this study.

### Required MCP Usage

**STEP 0A: Discover Available MCPs**

- Call `list-mcp` tool to see all enabled MCP servers
- Identify which servers are relevant for codebase study:
  - **octocode**: GitHub repo indexing and code search
  - **context7**: Latest framework/library documentation
  - **augments**: Framework-specific patterns and examples
  - **gh_grep**: Real-world code patterns from public repos
  - **memory**: Store codebase insights for future reference
  - **aid**: AI Distiller for code structure extraction

**STEP 0B: Index Current Repository with Octocode**
If `octocode` is available:

1. Detect if current directory is a GitHub repository:
   - !`git remote get-url origin 2>/dev/null || echo "Not a GitHub repo"`
2. If GitHub repo detected, extract owner/repo from remote URL
3. Use `octocode` tools to:
   - `githubViewRepoStructure`: Get complete directory structure
   - `githubSearchCode`: Index key patterns (exports, classes, functions)
   - Store results for quick reference during study

**STEP 0C: Gather Latest Framework Documentation**
If project uses known frameworks (Next.js, React, Express, Django, etc.):

- Use `context7` to fetch latest documentation for detected frameworks
- Reference official patterns and best practices during analysis
- Example: "Detected Next.js 14 → fetch App Router docs from context7"

**STEP 0D: Initialize Memory Storage**
Use `memory` MCP to create knowledge graph for this codebase:

1. Create entity for the repository:

   - Entity type: "codebase"
   - Name: Repository name
   - Observations: [project type, main language, framework, purpose]

2. During study, add entities for:

   - Key modules/directories (type: "module")
   - Important files (type: "file")
   - Architecture patterns (type: "pattern")
   - Dependencies (type: "dependency")
   - Entry points (type: "entrypoint")

3. Create relations between entities:

   - "uses" (e.g., "auth module" uses "database layer")
   - "depends_on" (e.g., API depends_on Redis)
   - "implements" (e.g., UserController implements REST API)

4. **CRITICAL**: If `.opencode/agent/*.md` exists in repo:
   - Read the agent file(s)
   - Add memory reference to each agent file
   - Format: Add observation to agent entity: "Studies codebase: [repo name] with architecture: [pattern]"
   - Example: Entity "git agent" → Observation "Studies codebase: dotfiles with architecture: shell scripts + config files"

**STEP 0E: Extract Code Structure with AI Distiller**
If `aid` is available and repo is complex:

- Use `aid_distill_directory` on key source directories
- Extract API signatures, types, and structure
- Store distilled output for quick reference
- Example: `aid_distill_directory` on `src/` for TypeScript projects

## Workflow

### STEP 1: Detect Project Type

Check for project indicators in root directory:

- !`ls -la | grep -E "package.json|pyproject.toml|requirements.txt|Cargo.toml|go.mod|composer.json|Gemfile|pom.xml|build.gradle"`

Based on files found, identify project type:

- **Node.js/TypeScript**: package.json, tsconfig.json
- **Python**: pyproject.toml, requirements.txt, setup.py
- **Go**: go.mod, go.sum
- **Rust**: Cargo.toml, Cargo.lock
- **PHP**: composer.json
- **Ruby**: Gemfile
- **Java**: pom.xml, build.gradle

### STEP 2: Identify Key Configuration Files

Based on project type, prioritize reading:

**For Node.js/TypeScript Projects**:

1. package.json - Dependencies, scripts, project metadata
2. tsconfig.json - TypeScript configuration
3. README.md - Project overview
4. .env.example or .env.template - Environment variables
5. next.config.js/ts OR vite.config.js/ts OR webpack.config.js - Build config

**For Python Projects**:

1. pyproject.toml OR requirements.txt - Dependencies
2. README.md - Project overview
3. setup.py - Package configuration
4. .env.example - Environment variables
5. main.py OR app.py OR **main**.py - Entry point

**For Go Projects**:

1. go.mod - Module dependencies
2. README.md - Project overview
3. main.go - Entry point
4. Makefile - Build commands

**For Rust Projects**:

1. Cargo.toml - Dependencies and metadata
2. README.md - Project overview
3. src/main.rs OR src/lib.rs - Entry point

### STEP 3: Analyze Project Structure

List directory structure (depth 2-3) to understand organization:

- !`tree -L 3 -I 'node_modules|.git|dist|build|target|vendor|venv|__pycache__|.next' || find . -maxdepth 3 -type d | grep -v 'node_modules\|.git\|dist\|build' | head -50`

Identify key directories:

- **Source code**: src/, lib/, app/, pages/, api/
- **Tests**: test/, tests/, **tests**, spec/
- **Configuration**: config/, .config/
- **Documentation**: docs/, documentation/
- **Public assets**: public/, static/, assets/

### STEP 4: Read Key Files

**Phase 1 - Configuration & Docs** (ALWAYS read these):

1. README.md
2. Main config file (package.json, pyproject.toml, etc.)
3. .env.example or similar
4. CONTRIBUTING.md (if exists)

**Phase 2 - Entry Points** (read based on project type):

- Node.js: index.ts/js, main.ts/js, server.ts/js
- Next.js: app/layout.tsx, pages/\_app.tsx, next.config.js
- Python: main.py, app.py, **init**.py in root package
- Go: main.go, cmd/\*/main.go
- Rust: src/main.rs, src/lib.rs

**Phase 3 - Core Business Logic** (selective based on size):
If $ARGUMENTS provided:

- Focus on files/directories matching the argument
- Example: If $ARGUMENTS = "auth", prioritize auth/, authentication/, login-related files

If NO $ARGUMENTS:

- Sample 3-5 key files from main source directory
- Prioritize: route definitions, API handlers, core modules, database schemas

### STEP 5: Identify Architecture Patterns

Based on files and structure, identify:

- **Architecture**: Monolith, microservices, serverless, monorepo
- **Frameworks**: Express, Next.js, Django, Flask, FastAPI, Rails, Laravel, etc.
- **Database**: PostgreSQL, MySQL, MongoDB, Redis, etc. (check config/deps)
- **API Style**: REST, GraphQL, gRPC, tRPC
- **State Management**: Redux, Zustand, Jotai, Pinia (for frontend)
- **Testing**: Jest, Vitest, Pytest, Go test, RSpec
- **Build Tool**: Webpack, Vite, esbuild, Rollup, Turbopack
- **Deployment**: Docker, Kubernetes, Vercel, Railway, etc.

### STEP 6: Store Insights in Memory

Before generating summary, **persist all insights to memory MCP**:

1. **Repository Entity**:

   ```
   Entity: [repo-name]
   Type: codebase
   Observations:
   - Project type: [Web app/API/CLI/Library]
   - Primary language: [TypeScript/Python/Go/etc.]
   - Main framework: [Next.js/Django/Express/etc.]
   - Architecture pattern: [Monolith/Microservices/etc.]
   - Database: [PostgreSQL/MongoDB/etc.]
   - Entry points: [list main files]
   ```

2. **Module Entities** (for each key directory):

   ```
   Entity: [module-name] (e.g., "auth-module", "api-layer")
   Type: module
   Observations:
   - Purpose: [what it does]
   - Key files: [list important files]
   - Technologies: [specific tech used]
   ```

3. **Relations**:

   ```
   - [repo-name] uses [framework-name]
   - [api-layer] depends_on [database-layer]
   - [auth-module] implements [authentication-pattern]
   ```

4. **Agent Integration** (CRITICAL):
   - Check if `.opencode/agent/` directory exists
   - If yes, read all `*.md` files in that directory
   - For each agent file:
     - Create/update memory entity for the agent
     - Add observation: "Studies codebase: [repo-name]"
     - Add observation: "Architecture: [detected architecture pattern]"
     - Add observation: "Primary tech: [main framework/language]"
     - Add relation: "[agent-name] operates_on [repo-name]"
   - Example:

     ```
     Entity: git-agent
     Type: agent
     Observations:
     - Studies codebase: dotfiles
     - Architecture: shell scripts + config files
     - Primary tech: Bash/Zsh
     - Purpose: Git operations with conventional commits

     Relation: git-agent operates_on dotfiles
     ```

### STEP 7: Generate Context Summary

Provide structured summary:

```
# Repository Study Summary

## MCP Integration Status
- **Octocode Index**: [✓ Indexed | ✗ Not available | ✗ Not a GitHub repo]
- **Framework Docs Fetched**: [List frameworks with context7 docs loaded]
- **Memory Stored**: [✓ Knowledge graph created | ✗ Memory MCP not available]
- **AI Distiller Used**: [✓ Code structure extracted | ✗ Aid MCP not available]
- **Agents Updated**: [✓ Updated N agent(s) | ✗ No agents found]

## Project Overview
- **Name**: [from package.json/README]
- **Type**: [Web app, API, CLI tool, library, etc.]
- **Language/Framework**: [Primary tech stack]
- **Purpose**: [Brief description from README]

## Architecture
- **Pattern**: [Monolith/Microservices/Serverless/etc.]
- **Framework(s)**: [Express, Next.js, Django, etc.]
- **Database**: [PostgreSQL, MongoDB, etc.]
- **API Style**: [REST, GraphQL, etc.]

## Project Structure
[Key directories and their purposes]

## Key Dependencies
[Top 5-10 important dependencies]

## Entry Points
[Main files where execution starts]

## Core Modules
[Important directories/files containing business logic]

## Configuration
[Environment variables, config files, build setup]

## Testing Strategy
[Test framework, test location, coverage approach]

## Deployment
[How the app is deployed - Docker, Vercel, etc.]

## Focus Area Context
[If $ARGUMENTS provided, detailed analysis of specified module]

## Memory Storage
[Summary of entities and relations stored in memory MCP]

## Next Steps
[Suggested areas to explore based on common development tasks]
```

### STEP 8: Optimization Guidelines

**Token Efficiency**:

- Don't read EVERY file - be selective
- Use grep/search for specific patterns instead of reading full files
- For large files, read only relevant sections (e.g., exports, types, main functions)
- Skip generated files (dist/, build/, .next/)
- Skip dependency directories (node_modules/, vendor/)

**Smart Sampling**:

- For repos with 100+ files: sample 10-15 key files
- For repos with 50-100 files: sample 20-25 key files
- For repos with <50 files: can read most files if needed

**User Guidance**:
If $ARGUMENTS provided, explain what you focused on and why.
If NO $ARGUMENTS and repo is large, explain what you sampled and offer to dive deeper into specific areas.

---

**Example Usage**:

- `/study` - General study of entire repo
- `/study auth module` - Focus on authentication-related code
- `/study src/api` - Focus on API layer
- `/study database` - Focus on database schema and queries
