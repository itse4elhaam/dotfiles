---

<protocol name="technology_documentation_lookup">
  <requirement type="mandatory">
    When the user mentions ANY technology, library, framework, or tool, you MUST look up current documentation FIRST before providing guidance.
  </requirement>

<lookup_priority>
<tool priority="1" name="context7">
<description>Official up-to-date library/framework docs</description>
<example>
context7_resolve-library-id(libraryName: "react")
context7_get-library-docs(context7CompatibleLibraryID: "/facebook/react")
</example>
</tool>

    <tool priority="2" name="webfetch">
      <description>Official documentation websites</description>
      <example>
        webfetch(url: "https://nextjs.org/docs", format: "markdown")
      </example>
    </tool>

    <tool priority="3" name="gh_grep">
      <description>Real-world production code examples</description>
      <example>
        gh_grep_searchGitHub(query: "useState(", language: ["TypeScript", "TSX"])
      </example>
    </tool>

</lookup_priority>

<decision_matrix>
<scenario type="framework_library">
<action>Get official API docs</action>
<tool>context7</tool>
<example>"React hooks" → context7(react)</example>
</scenario>

    <scenario type="configuration">
      <action>Fetch current syntax</action>
      <tool>webfetch</tool>
      <example>"Tailwind config" → webfetch(tailwindcss.com/docs/configuration)</example>
    </scenario>

    <scenario type="best_practices">
      <action>Find real implementations</action>
      <tool>gh_grep</tool>
      <example>"Error boundaries" → gh_grep("ErrorBoundary", language=["TSX"])</example>
    </scenario>

    <scenario type="version_specific">
      <action>Check current docs</action>
      <tool>context7 + webfetch</tool>
      <example>"Next.js 15 API" → context7(/vercel/next.js/v15)</example>
    </scenario>

</decision_matrix>

<workflow_example>
<user_message>Add authentication with NextAuth</user_message>
<required_steps>
<step number="1">context7_resolve-library-id(libraryName: "next-auth")</step>
<step number="2">context7_get-library-docs(context7CompatibleLibraryID: "/nextauthjs/next-auth", topic: "authentication")</step>
<step number="3">gh_grep_searchGitHub(query: "NextAuth(", language: ["TypeScript"], repo: "nextauthjs/next-auth-example")</step>
<step number="4">Only THEN provide implementation guidance based on CURRENT documentation</step>
</required_steps>
</workflow_example>

<critical_rules>
<rule type="forbidden">❌ NEVER rely on training data knowledge for technology guidance</rule>
<rule type="mandatory">✅ ALWAYS verify current API syntax, configuration, and patterns</rule>
<rule type="mandatory">✅ CHECK for version-specific changes (especially major versions)</rule>
<rule type="mandatory">✅ VALIDATE deprecated patterns before suggesting them</rule>
<rule type="mandatory">✅ SEARCH for production examples when patterns are unclear</rule>
</critical_rules>

<technologies_requiring_lookup>
<category name="frontend_frameworks">
<items>React, Vue, Angular, Svelte, Next.js</items>
</category>
<category name="build_tools">
<items>Vite, Webpack, Turbopack, esbuild</items>
</category>
<category name="state_management">
<items>Redux, Zustand, Jotai, Recoil</items>
</category>
<category name="ui_libraries">
<items>Tailwind, MUI, Chakra, shadcn/ui</items>
</category>
<category name="backend_frameworks">
<items>Express, Fastify, NestJS, Hono</items>
</category>
<category name="orms">
<items>Prisma, Drizzle, TypeORM</items>
</category>
<category name="testing_tools">
<items>Vitest, Jest, Playwright, Cypress</items>
</category>
<category name="ai_ml_libraries">
<items>LangChain, OpenAI SDK, Anthropic SDK</items>
</category>
</technologies_requiring_lookup>

<correct_workflow_example>
<user_request>Help me set up Drizzle ORM with PostgreSQL</user_request>

    <assistant_must_do>
      <action>context7_resolve-library-id(libraryName: "drizzle-orm")</action>
      <action>context7_get-library-docs(context7CompatibleLibraryID: "/drizzle-team/drizzle-orm", topic: "postgresql setup")</action>
      <action>gh_grep_searchGitHub(query: "drizzle(", language: ["TypeScript"])</action>
      <action>Provide setup guidance based on CURRENT docs (not training data)</action>
    </assistant_must_do>

    <assistant_must_not_do>
      <forbidden>Suggest setup steps from memory/training data</forbidden>
      <forbidden>Use outdated API patterns</forbidden>
      <forbidden>Skip documentation lookup</forbidden>
    </assistant_must_not_do>

</correct_workflow_example>
</protocol>

---

<quick_start>
<code_review_workflow>
<step number="1">Review changes: `git diff` before committing</step>
<step number="2">Run CodeRabbit: `coderabbit review --plain` for security, performance, best practices</step>
<step number="3">Apply feedback: Fix issues, improve code quality</step>
<step number="4">Stage & commit: Use conventional commit format</step>
</code_review_workflow>

<core_philosophy>
<principle>Fail Fast, Defend Early: Validate inputs, fail loudly with clear errors</principle>
<principle>Edge-Case Driven: Consider null/undefined, empty arrays, out-of-range values</principle>
<principle>Clarity > Cleverness: Code readable by new engineer in minutes, not hours</principle>
</core_philosophy>

<language_preferences>
<preference>TypeScript (never plain JavaScript unless absolutely unavoidable)</preference>
<preference>ESM syntax — no `require()` or CommonJS</preference>
<preference>`async/await` over `.then()` chains</preference>
</language_preferences>
</quick_start>

---

<language_specific_guidelines>
<language name="typescript">
<guideline>Use `interface` (prefixed with `I`) over `type` unless extending</guideline>
<guideline>Prefix types with `T`</guideline>
<guideline>Avoid `any`; use `unknown` if unavoidable</guideline>
<guideline>Mark arrays as `readonly string[]` over `string[]`</guideline>
<guideline>Use `as const` to make types stricter</guideline>
<guideline>Use **zod** for runtime validation at all input/output boundaries</guideline>
</language>

  <language name="shell_scripts">
    <guideline>Use `#!/bin/bash` or `#!/usr/bin/env bash` as shebang</guideline>
    <guideline>Always include `set -euo pipefail` for robustness</guideline>
    <guideline>Use shellcheck for linting: `shellcheck **/*.sh`</guideline>
    <guideline>Naming: snake_case for variables/functions (e.g., `script_dir`)</guideline>
    <guideline>Quote variables: `"$variable"` not `$variable`</guideline>
    <guideline>Use `[[ ]]` over `[ ]` for conditionals</guideline>
    <guideline>Document complex logic with comments</guideline>
    <guideline>Pass arguments with `"$@"` to preserve spacing</guideline>
  </language>

  <language name="frontend_react_nextjs">
    <guideline>Functional components with hooks</guideline>
    <guideline>Avoid misuse of `useEffect` (derive state where possible)</guideline>
    <guideline>Prefer **TailwindCSS** utilities over CSS modules</guideline>
    <guideline>Schema validation (`zod`) for forms and APIs</guideline>
    <guideline>Optimize rendering (memoize intelligently, don't overdo)</guideline>
  </language>
</language_specific_guidelines>

---

<coding_principles>
<category name="defensive_programming">
<principle>Always null-check inputs and external data</principle>
<principle>Validate function parameters at the top (fail fast)</principle>
<principle>Avoid silent failures — log or throw with meaningful messages</principle>
<principle>Treat every exported function as if it could be called by untrusted code</principle>
</category>

  <category name="functional_style">
    <principle>Pure functions by default (no hidden side effects)</principle>
    <principle>Use `.map`, `.filter`, `.reduce` only when semantically clear</principle>
    <principle>Use `for` loops for performance-sensitive code</principle>
    <principle>Prefer helper functions over inline duplication</principle>
  </category>

  <category name="control_flow">
    <principle>Guard clauses & early returns > deep nesting</principle>
    <principle>Avoid complex ternaries inside JSX</principle>
    <principle>Use `switch` only when semantically appropriate</principle>
    <principle>Use map (object) based logic for complicated logic (strategy pattern)</principle>
    <principle>Use `VALUES.includes` pattern over multi OR conditions</principle>
  </category>

  <category name="performance_sensitive">
    <principle>Avoid unnecessary allocations or object churn</principle>
    <principle>Prefer `Set` for `.has()` lookups</principle>
    <principle>Don't use `.forEach`/`.map` in critical paths — use `for`</principle>
    <principle>Avoid closures in hot loops</principle>
    <principle>Profile before micro-optimizing</principle>
  </category>

  <category name="quality_maintainability">
    <principle>Clear, meaningful names (no abbreviations)</principle>
    <principle>Prefer clarity over comments — self-documenting code</principle>
    <principle>Functions should be **short, composable, <30 lines** unless justified</principle>
    <principle>Prefer object-based params if >2 arguments</principle>
    <principle>Destructure params in function signatures, not inside function bodies</principle>
    <principle>Follow https://refactoring.guru/refactoring guidelines</principle>
  </category>
</coding_principles>

---

<opencode_customization>
<custom_tools location=".opencode/tool/">
<guideline>Use TypeScript with `@opencode-ai/plugin` SDK</guideline>
<guideline>Export with `tool()` helper for type-safety and validation</guideline>
<guideline>Tools auto-load from `.opencode/tool/` or `~/.config/opencode/tool/`</guideline>
<guideline>Filename becomes tool name (e.g., `list-mcp.ts` → `list-mcp` tool)</guideline>
<guideline>Cannot be invoked directly with Node.js — only through OpenCode</guideline>
<guideline>Use `tool.schema` (Zod) for argument validation</guideline>

<available_tools>
<tool name="list-mcp">
<purpose>List all enabled MCP servers with capabilities</purpose>
<usage>Use to discover available MCP functionality</usage>
<when_to_use>Before using MCP servers, to check what's available</when_to_use>
</tool>
</available_tools>
</custom_tools>

<custom_agents location=".opencode/agent/">
<guideline>Markdown files with YAML frontmatter</guideline>
<guideline>Specify: name, description, mode (primary/subagent), temperature</guideline>

<mcp_server_selection>
<subagents>
<description>2-3 focused servers</description>
<example>git agent: octocode, context7</example>
</subagents>
<primary_agents>
<description>5-10 servers</description>
<example>sales agent: 7 servers</example>
</primary_agents>
</mcp_server_selection>

<temperature_guide>
<range value="0.0-0.2">Deterministic (git, code generation)</range>
<range value="0.4-0.6">Balanced (general coding)</range>
<range value="0.6-0.8">Creative (writing, proposals)</range>
</temperature_guide>

<available_agents>
<category name="primary">
<agent name="openagent">
<description>Main orchestrator agent with full capabilities</description>
<temperature>0.5</temperature>
<capabilities>General coding, coordination, complex reasoning</capabilities>
<when_to_use>Default agent for most tasks, delegates to specialists when needed</when_to_use>
<mcp_servers>10+ servers (comprehensive toolkit)</mcp_servers>
</agent>

<agent name="codebase-agent">
<description>Specialized in codebase analysis and understanding</description>
<temperature>0.5</temperature>
<capabilities>Code navigation, pattern detection, architecture analysis, dependency mapping</capabilities>
<when_to_use>Deep codebase exploration, understanding project structure, analyzing relationships</when_to_use>
<mcp_servers>octocode, aid, memory, context7</mcp_servers>
</agent>

<agent name="system-builder">
<description>Builds and organizes agent systems and workflows</description>
<temperature>0.5</temperature>
<capabilities>Agent creation, context organization, workflow design, command generation</capabilities>
<when_to_use>Building new agent systems, organizing OpenCode setups, designing multi-agent workflows</when_to_use>
<mcp_servers>memory, context7</mcp_servers>
<delegates_to>domain-analyzer, agent-generator, context-organizer, workflow-designer, command-creator</delegates_to>
</agent>

<agent name="git">
<description>Git operations with conventional commits</description>
<temperature>0.1</temperature>
<capabilities>Commits, branching, PR creation, conventional commits, CodeRabbit integration</capabilities>
<when_to_use>All git operations, especially via /commit command</when_to_use>
<mcp_servers>octocode, linear</mcp_servers>
</agent>

<agent name="sales">
<description>Sales and business operations</description>
<temperature>0.7</temperature>
<capabilities>Proposals, outreach, business writing, stakeholder communication</capabilities>
<when_to_use>Sales materials, business documents, client-facing content</when_to_use>
<mcp_servers>7 servers for comprehensive business tasks</mcp_servers>
</agent>

<agent name="teach">
<description>Teaching agent using Socratic method</description>
<temperature>0.7</temperature>
<capabilities>Guided learning, questioning, concept explanation, skill development</capabilities>
<when_to_use>Learning new concepts, understanding without direct answers, skill building</when_to_use>
<mcp_servers>context7, ddg-search, gh_grep</mcp_servers>
<note>Never provides direct solutions, only guides through questions</note>
</agent>

<agent name="ask">
<description>Interactive Q&A agent</description>
<temperature>0.5</temperature>
<capabilities>Answering questions, providing information, clarification</capabilities>
<when_to_use>Direct questions requiring factual answers</when_to_use>
<mcp_servers>context7, ddg-search, memory</mcp_servers>
</agent>
</category>

<category name="code_subagents">
<agent name="coder-agent">
<description>Code generation and implementation</description>
<temperature>0.2</temperature>
<capabilities>Writing code, implementing features, following patterns, type-safe implementations</capabilities>
<when_to_use>Implementing features, writing new code, following specifications</when_to_use>
<invocation>Via task tool or direct delegation from primary agents</invocation>
</agent>

<agent name="reviewer">
<description>Code review and quality checks</description>
<temperature>0.3</temperature>
<capabilities>Security analysis, performance review, best practices validation, code smells detection</capabilities>
<when_to_use>Code review, quality assurance, pre-commit validation</when_to_use>
<integrates_with>CodeRabbit for enhanced analysis</integrates_with>
</agent>

<agent name="tester">
<description>Test creation and validation</description>
<temperature>0.2</temperature>
<capabilities>Unit tests, integration tests, edge case identification, test coverage analysis</capabilities>
<when_to_use>Writing tests, validating functionality, TDD workflows</when_to_use>
<invocation>Via /test command or direct delegation</invocation>
</agent>

<agent name="build-agent">
<description>Build processes and CI/CD</description>
<temperature>0.2</temperature>
<capabilities>Build configuration, CI/CD setup, deployment scripts, type checking</capabilities>
<when_to_use>Build issues, CI/CD setup, deployment configuration</when_to_use>
</agent>

<agent name="codebase-pattern-analyst">
<description>Pattern detection and analysis</description>
<temperature>0.4</temperature>
<capabilities>Identifying patterns, anti-patterns, refactoring opportunities, architecture analysis</capabilities>
<when_to_use>Code refactoring, architecture review, pattern consistency checks</when_to_use>
</agent>
</category>

<category name="core_subagents">
<agent name="task-manager">
<description>Task planning and tracking</description>
<temperature>0.3</temperature>
<capabilities>Breaking down tasks, creating subtask lists, tracking progress, dependency mapping</capabilities>
<when_to_use>Complex multi-step tasks, project planning, task organization</when_to_use>
<invocation>Automatically or via explicit delegation</invocation>
</agent>

<agent name="documentation">
<description>Documentation generation</description>
<temperature>0.5</temperature>
<capabilities>READMEs, API docs, guides, code comments, markdown formatting</capabilities>
<when_to_use>Creating documentation, explaining code, writing guides</when_to_use>
</agent>
</category>

<category name="system_builder_subagents">
<agent name="domain-analyzer">
<description>Domain-driven analysis</description>
<temperature>0.4</temperature>
<capabilities>Domain modeling, concept extraction, business rule identification, terminology mapping</capabilities>
<when_to_use>Understanding domain requirements, building domain models</when_to_use>
<invocation>Via system-builder agent</invocation>
</agent>

<agent name="agent-generator">
<description>Generate new agents</description>
<temperature>0.3</temperature>
<capabilities>Creating agent files, XML optimization, capability definition, MCP server selection</capabilities>
<when_to_use>Creating new specialized agents</when_to_use>
<invocation>Via system-builder agent</invocation>
</agent>

<agent name="context-organizer">
<description>Organize context files</description>
<temperature>0.3</temperature>
<capabilities>Context file structure, knowledge organization, modularity, dependency mapping</capabilities>
<when_to_use>Organizing agent context, structuring knowledge bases</when_to_use>
<invocation>Via system-builder agent or /context command</invocation>
</agent>

<agent name="workflow-designer">
<description>Design workflows</description>
<temperature>0.4</temperature>
<capabilities>Multi-stage workflows, context dependencies, success criteria, checkpoint definition</capabilities>
<when_to_use>Creating complex workflows, process automation</when_to_use>
<invocation>Via system-builder agent</invocation>
</agent>

<agent name="command-creator">
<description>Create custom commands</description>
<temperature>0.3</temperature>
<capabilities>Slash command creation, routing logic, parameter handling, documentation</capabilities>
<when_to_use>Creating custom /commands for frequent tasks</when_to_use>
<invocation>Via system-builder agent</invocation>
</agent>
</category>

</available_agents>
</custom_agents>

<custom_commands location=".opencode/command/">
<guideline>Markdown files with YAML frontmatter</guideline>
<guideline>Can route to agents with `agent: <name>` field</guideline>
<guideline>Use `$ARGUMENTS` for user input</guideline>
<guideline>Set `subtask: true` to invoke subagents</guideline>
<guideline>Commands are invoked with `/command-name`</guideline>

<available_commands>
<command name="/commit">
<purpose>Commit workflow with CodeRabbit review</purpose>
<agent>git</agent>
<workflow>Review diff → CodeRabbit analysis → Conventional commit</workflow>
<usage>Always use this instead of manual git commit</usage>
</command>
<command name="/study">
<purpose>Deep codebase analysis with MCP tools</purpose>
<workflow>Uses octocode, memory, and aid for comprehensive study</workflow>
<usage>Study repos, analyze patterns, understand architecture</usage>
</command>
<command name="/test">
<purpose>Run tests with comprehensive reporting</purpose>
<agent>tester</agent>
<usage>Execute test suites and validate functionality</usage>
</command>
<command name="/context">
<purpose>Build and organize context files</purpose>
<agent>context-organizer</agent>
<usage>Create structured context for agents</usage>
</command>
<command name="/clean">
<purpose>Clean up codebase (dead code, unused imports)</purpose>
<usage>Refactor and optimize code quality</usage>
</command>
<command name="/optimize">
<purpose>Performance optimization analysis</purpose>
<usage>Identify and fix performance bottlenecks</usage>
</command>
<command name="/prompt-enchancer">
<purpose>Enhance and improve user prompts</purpose>
<usage>Get better results by improving prompt quality</usage>
</command>
<command name="/worktrees">
<purpose>Git worktree management</purpose>
<usage>Manage multiple working directories</usage>
</command>
<command name="/build-context-system">
<purpose>Build complete context system for project</purpose>
<agent>system-builder</agent>
<usage>Initialize OpenAgents framework for project</usage>
</command>
</available_commands>
</custom_commands>

<parallel_execution>
<capability>
OpenCode supports concurrent/parallel execution of independent subagent tasks through multi-session capability and task tool batching
</capability>

<when_to_parallelize>
<scenario>Multiple independent research tasks (e.g., analyze repo A + study docs for library B)</scenario>
<scenario>Parallel code reviews (e.g., review security + review performance simultaneously)</scenario>
<scenario>Multiple file operations with no dependencies (e.g., read 3 different config files)</scenario>
<scenario>Concurrent documentation lookups (e.g., context7 + gh_grep + webfetch in parallel)</scenario>
<scenario>Multi-agent delegation for complex workflows (e.g., coder-agent writes code while documentation agent prepares docs)</scenario>
</when_to_parallelize>

<how_to_parallelize>
<method name="task_tool_batching">
<description>Call multiple task tools in a single response block</description>
<example>
```
task(subagent_type="explore", prompt="Find auth patterns in repo")
task(subagent_type="documentation", prompt="Create API docs")
```
</example>
<benefit>Both tasks run concurrently, reducing total execution time</benefit>
</method>

<method name="mcp_batching">
<description>Call multiple MCP tools in a single function_calls block</description>
<example>
```
context7_query-docs(libraryId="/facebook/react", query="hooks")
gh_grep_searchGitHub(query="useState(", language=["TypeScript"])
webfetch(url="https://react.dev/reference/react", format="markdown")
```
</example>
<benefit>All MCP calls execute in parallel, fetching data faster</benefit>
</method>

<method name="multi_agent_coordination">
<description>Delegate to multiple subagents for complex workflows</description>
<example>
```
# Task 1: Write feature implementation
task(subagent_type="subagents/code/coder-agent", prompt="Implement auth middleware")

# Task 2: Write tests (can start immediately)
task(subagent_type="subagents/code/tester", prompt="Create tests for auth middleware")

# Task 3: Update documentation (can start immediately)
task(subagent_type="subagents/core/documentation", prompt="Document auth middleware API")
```
</example>
<benefit>Three subagents work simultaneously, completing the feature faster</benefit>
</method>
</how_to_parallelize>

<when_not_to_parallelize>
<case>Tasks have dependencies (e.g., must read file before editing it)</case>
<case>Sequential logic required (e.g., analyze → plan → implement)</case>
<case>Shared state modifications (e.g., multiple agents editing same file)</case>
<case>Token budget concerns (parallel execution uses more tokens upfront)</case>
</when_not_to_parallelize>

<efficiency_guidelines>
<guideline>Default to parallel execution when tasks are independent</guideline>
<guideline>Use sequential execution when output of one task feeds into another</guideline>
<guideline>Batch MCP calls whenever possible (research shows significant speedup)</guideline>
<guideline>Delegate to subagents for specialized tasks rather than doing everything in main agent</guideline>
<guideline>Monitor token usage: parallel execution is faster but uses more tokens initially</guideline>
</efficiency_guidelines>

<examples>
<example name="parallel_research">
<description>Research React hooks and Next.js patterns simultaneously</description>
<code>
# Both lookups happen in parallel
context7_query-docs(libraryId="/facebook/react", query="useEffect cleanup")
context7_query-docs(libraryId="/vercel/next.js", query="server actions")
</code>
</example>

<example name="parallel_code_review">
<description>Review security and performance concurrently</description>
<code>
task(subagent_type="subagents/code/reviewer", prompt="Review code for security vulnerabilities")
task(subagent_type="subagents/code/reviewer", prompt="Review code for performance issues")
</code>
</example>

<example name="parallel_implementation">
<description>Implement feature + tests + docs simultaneously</description>
<code>
task(subagent_type="subagents/code/coder-agent", prompt="Implement user authentication")
task(subagent_type="subagents/code/tester", prompt="Write unit tests for authentication")
task(subagent_type="subagents/core/documentation", prompt="Document authentication API")
</code>
</example>

<example name="sequential_required">
<description>When NOT to parallelize (dependencies exist)</description>
<code>
# WRONG: Can't test before implementing
task(subagent_type="subagents/code/coder-agent", prompt="Implement auth")
task(subagent_type="subagents/code/tester", prompt="Test the auth implementation")

# RIGHT: Sequential execution
1. Implement auth (coder-agent)
2. Wait for completion
3. Then test auth (tester)
</code>
</example>
</examples>
</parallel_execution>

<mcp_server_management>
<default_state>
All MCP servers are DISABLED by default in opencode.json for performance and cost optimization
</default_state>

<enabling_strategy>
<when_to_enable>
<case>Need specific functionality not available through basic tools</case>
<case>Require specialized MCP capabilities (e.g., browser automation, GitHub deep analysis)</case>
<case>Working on tasks that benefit from MCP server features</case>
</when_to_enable>

<how_to_enable>
<step number="1">Identify which MCP server(s) you need for the task</step>
<step number="2">Edit .config/opencode/opencode.json</step>
<step number="3">Set `"enabled": true` for required servers</step>
<step number="4">Restart OpenCode session if needed</step>
<step number="5">Disable servers when done to reduce overhead</step>
</how_to_enable>

<server_priority_guide>
<high_priority>
<server>context7 - Enable when working with frameworks/libraries (docs lookup)</server>
<server>octocode - Enable when analyzing GitHub repositories</server>
<server>memory - Enable when need cross-session persistence</server>
</high_priority>

<medium_priority>
<server>gh_grep - Enable when searching for production code patterns</server>
<server>aid - Enable for advanced code analysis and refactoring</server>
<server>augments - Enable for framework-specific examples</server>
</medium_priority>

<as_needed>
<server>playwright - Enable only for UI testing tasks</server>
<server>next-devtools - Enable only when debugging Next.js projects</server>
<server>desktop-commander - Enable for advanced file operations</server>
<server>mindpilot - Enable when creating diagrams</server>
</as_needed>

<low_priority>
<server>ddg-search - Enable for web searches (use sparingly)</server>
<server>sequential-thinking - Enable for complex problem-solving</server>
<server>mcp-compass - Enable when discovering new MCP servers</server>
<server>chrome-devtools - Enable for deep browser debugging</server>
</low_priority>
</server_priority_guide>

<workflow_specific_enablement>
<workflow name="study_codebase">
<enable>octocode, memory, aid</enable>
<reason>Deep repo analysis, pattern detection, cross-session memory</reason>
</workflow>

<workflow name="framework_development">
<enable>context7, gh_grep, augments</enable>
<reason>Official docs, real-world patterns, framework examples</reason>
</workflow>

<workflow name="ui_testing">
<enable>playwright, chrome-devtools</enable>
<reason>Browser automation, network inspection, UI validation</reason>
</workflow>

<workflow name="research_task">
<enable>ddg-search, gh_grep, context7</enable>
<reason>Web search, code patterns, documentation lookup</reason>
</workflow>

<workflow name="nextjs_debugging">
<enable>next-devtools, playwright</enable>
<reason>Next.js-specific errors, UI testing</reason>
</workflow>
</workflow_specific_enablement>

<optimization_tips>
<tip>Keep only necessary servers enabled to reduce token overhead</tip>
<tip>Use basic tools (read, edit, glob) when MCP servers aren't required</tip>
<tip>Enable servers at start of session, disable when done</tip>
<tip>Group related tasks to minimize server enable/disable cycles</tip>
<tip>Monitor performance: too many enabled servers can slow response time</tip>
</optimization_tips>
</mcp_server_management>
</opencode_customization>

---

<tool_strategy>
<file_operations>
<priority level="1" tool="Read">
<use_case>Direct file access (FASTEST)</use_case>
<examples>
<example>Known file paths, configuration files</example>
<example>Read package.json, tsconfig.json</example>
</examples>
</priority>

    <priority level="2" tool="Octocode">
      <use_case>GitHub repo access</use_case>
      <examples>
        <example>Remote repos, no local clone needed</example>
        <example>Study public repos without cloning</example>
      </examples>
    </priority>

    <priority level="3" tool="Desktop Commander">
      <use_case>Advanced file operations</use_case>
      <examples>
        <example>Search, process management, system operations</example>
        <example>Search for patterns, manage processes</example>
      </examples>
    </priority>

</file_operations>

<task_tool_strategy>
<when_to_use>
<case>Open-ended searches (don't know exact file/pattern)</case>
<case>Exploratory codebase analysis</case>
<case>Multi-step research workflows</case>
<case>When you need multiple search attempts</case>
</when_to_use>

    <when_not_to_use>
      <case>Know exact file path → Use Read tool</case>
      <case>Know class/function name → Use Glob/Grep directly</case>
      <case>Simple file operations → Use basic tools</case>
    </when_not_to_use>

    <examples>
      <bad_example>Task("Find the UserController class")</bad_example>
      <good_example>grep("class UserController", include="*.ts")</good_example>
      <bad_example>Task("Read package.json")</bad_example>
      <good_example>read("package.json")</good_example>
    </examples>

</task_tool_strategy>

<memory_mcp_usage>
<when_to_use>
<case>Store project-specific facts across sessions</case>
<case>Remember user preferences and coding style</case>
<case>Track codebase architecture and patterns</case>
<case>Link agents to codebases they work with</case>
</when_to_use>

    <entity_design>
      <entity type="codebases">Store project metadata (type, language, architecture)</entity>
      <entity type="modules">Store component/module information</entity>
      <entity type="agents">Store agent context and capabilities</entity>
      <entity type="relations">Link entities with meaningful relations</entity>
    </entity_design>

    <best_practices>
      <practice>Use descriptive entity types: `codebase`, `module`, `agent`, `pattern`</practice>
      <practice>Store observations as facts (not prose)</practice>
      <practice>Create relations for discoverability: `contains`, `uses`, `depends_on`, `operates_on`</practice>
      <practice>Update agents when studying new codebases</practice>
    </best_practices>

</memory_mcp_usage>
</tool_strategy>

---

<mcp_servers>
<quick_reference>
<server name="context7" type="Docs" use_case="Latest framework docs" priority="HIGH"/>
<server name="octocode" type="GitHub" use_case="Repo analysis" priority="HIGH"/>
<server name="memory" type="Storage" use_case="Cross-session memory" priority="HIGH"/>
<server name="aid" type="Analysis" use_case="Code structure" priority="MEDIUM"/>
<server name="gh_grep" type="Search" use_case="Real-world patterns" priority="MEDIUM"/>
<server name="augments" type="Docs" use_case="Framework examples" priority="MEDIUM"/>
<server name="playwright" type="Browser" use_case="UI testing" priority="AS_NEEDED"/>
<server name="next-devtools" type="Dev" use_case="Next.js debugging" priority="AS_NEEDED"/>
<server name="desktop-commander" type="System" use_case="File ops" priority="AS_NEEDED"/>
<server name="mindpilot" type="Viz" use_case="Diagrams" priority="AS_NEEDED"/>
<server name="ddg-search" type="Search" use_case="Web search" priority="LOW"/>
<server name="sequential-thinking" type="Reasoning" use_case="Complex problems" priority="LOW"/>
<server name="mcp-compass" type="Discovery" use_case="Find MCP servers" priority="LOW"/>
<server name="chrome-devtools" type="Browser" use_case="Deep debugging" priority="LOW"/>
</quick_reference>

<workflow_integration>
<workflow name="study">octocode + memory + aid</workflow>
<workflow name="documentation">context7 + augments + gh_grep</workflow>
<workflow name="development">next-devtools + playwright</workflow>
<workflow name="research">ddg-search + gh_grep</workflow>
</workflow_integration>

<octocode_workflows>
<repository_discovery>
<step number="1" function="githubSearchRepositories">Find repos by topic/keywords</step>
<step number="2" function="githubViewRepoStructure">Get directory tree (depth=1 for overview, depth=2 for deep dive)</step>
<step number="3" function="githubSearchCode">Search for code patterns (match="path" for files, match="file" for content)</step>
<step number="4" function="githubGetFileContent">Read specific files (use `matchString` for targeted extraction)</step>
</repository_discovery>

    <best_practices>
      <practice>Start with `githubViewRepoStructure` (depth=1) for overview</practice>
      <practice>Use `match="path"` for fast file discovery</practice>
      <practice>Use `match="file"` with `limit=5` for detailed matches</practice>
      <practice>Always scope searches with owner/repo to avoid rate limits</practice>
      <practice>Use `matchString` with `matchStringContextLines` for precise content extraction</practice>
    </best_practices>

</octocode_workflows>

<server_categories>
<category name="documentation_research">
<server name="context7">
<use_when>Need official API docs or examples</use_when>
<example>Get Next.js App Router documentation</example>
</server>
<server name="augments">
<use_when>Need framework-specific patterns</use_when>
<example>Show TailwindCSS grid examples</example>
</server>
<server name="gh_grep">
<use_when>Need production code patterns</use_when>
<example>Find useState patterns in popular React repos</example>
</server>
</category>

    <category name="code_analysis_github">
      <server name="octocode">
        <use_when>Deep GitHub codebase analysis</use_when>
        <example>Search for auth patterns in facebook/react</example>
      </server>
      <server name="aid">
        <use_when>Need code signatures, bug hunting, refactoring suggestions</use_when>
        <example>Distill API signatures from src/</example>
      </server>
    </category>

    <category name="development_tools">
      <server name="next-devtools">
        <use_when>Working with Next.js projects</use_when>
        <example>Check Next.js dev server errors</example>
      </server>
      <server name="playwright">
        <use_when>Need to test web apps or verify UI</use_when>
        <example>Navigate to localhost:3000 and test login flow</example>
      </server>
      <server name="chrome-devtools">
        <use_when>Need deep browser debugging</use_when>
        <example>Inspect network requests on page load</example>
      </server>
    </category>

    <category name="file_system_operations">
      <server name="desktop-commander">
        <use_when>Need file manipulation beyond basic tools</use_when>
        <example>Search for 'validateUser' in src/</example>
      </server>
      <server name="mindpilot">
        <use_when>Need visual documentation</use_when>
        <example>Create architecture diagram for auth flow</example>
      </server>
    </category>

    <category name="utilities">
      <server name="ddg-search">
        <use_when>Need external knowledge or documentation</use_when>
        <example>Search for TypeScript best practices</example>
      </server>
      <server name="sequential-thinking">
        <use_when>Need systematic problem-solving</use_when>
        <example>Break down multi-step refactoring task</example>
      </server>
      <server name="memory">
        <use_when>Need to remember facts long-term</use_when>
        <example>Remember user prefers Zod for validation</example>
      </server>
      <server name="mcp-compass">
        <use_when>Looking for new MCP capabilities</use_when>
        <example>Find MCP server for AWS Lambda</example>
      </server>
    </category>

</server_categories>

<usage_guidelines>
<guideline>Prefer specialized tools: Use MCP servers over generic bash commands when available</guideline>
<guideline>Check enabled status: Only enabled servers are accessible</guideline>
<guideline>Context efficiency: Use Task tool for exploratory searches to reduce token usage</guideline>
<guideline>Parallel execution: Batch independent MCP calls in a single message</guideline>
</usage_guidelines>
</mcp_servers>

---

<git_usage>
<rules>
<rule>Always study the git diff before committing</rule>
<rule>When invoked via `/commit` command, commit immediately after analysis (no user confirmation needed)</rule>
<rule>**Staging logic**: Commit staged files if any exist; if nothing is staged, stage all changes with `git add -A`</rule>
<rule>You may ask the user to use the gh cli if it is relevant (Creating PR or reading linked issue)</rule>
<rule>If the branch named contains a number, it is the issue number, you can use gh to study the linked issue</rule>
<rule>Keep the commit message short and descriptive, follow the [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) guidelines</rule>
<rule>**CRITICAL**: Commit messages MUST be written in past tense (e.g., "added feature", "fixed bug", "removed files")</rule>
<rule>If there is extra detail regarding the commit, it should be in the commit description</rule>
<rule>When the user asks you to review changes, you must ask them for the base branch and then study the relevant diff</rule>
<rule>Use the `/commit` command for committing changes (invokes commit workflow with CodeRabbit review)</rule>
</rules>

<branching_strategy>
<user_info>
<name>elhaam</name>
<git_author>Elhaam / Elhaam Basheer Chaudhry</git_author>
</user_info>

<branch_naming_convention>
<rule>Check commit authors BEFORE creating branch</rule>
<workflow>
<step number="1">Run: `git log --all --format='%an' | sort | uniq -c`</step>
<step number="2">Analyze if commits contain ONLY user's commits or mixed authors</step>
<step number="3">Apply naming convention based on analysis</step>
</workflow>

<solo_work>
<condition>All commits in history are by elhaam only</condition>
<format>type/short-desc</format>
<examples>
<example>feat/setup-script</example>
<example>feat/vi-mode</example>
<example>fix/tmux-config</example>
<example>chore/update-deps</example>
<example>perf/optimize-loading</example>
<example>refactor/clean-scripts</example>
</examples>
</solo_work>

<collaborative_work>
<condition>Commits contain multiple authors OR working with others</condition>
<format>type/elhaam/short-desc</format>
<examples>
<example>feat/elhaam/add-auth</example>
<example>fix/elhaam/resolve-conflict</example>
<example>refactor/elhaam/cleanup-api</example>
</examples>
<rationale>Namespace prevents branch name conflicts when multiple developers work on same feature type</rationale>
</collaborative_work>

<conventional_types>
<type name="feat">New feature or functionality</type>
<type name="fix">Bug fix</type>
<type name="chore">Maintenance tasks (deps, configs, tooling)</type>
<type name="perf">Performance improvements</type>
<type name="refactor">Code restructuring without behavior change</type>
<type name="docs">Documentation only changes</type>
<type name="style">Formatting, whitespace, style changes</type>
<type name="test">Adding or updating tests</type>
</conventional_types>

<short_desc_guidelines>
<guideline>Use kebab-case (lowercase with hyphens)</guideline>
<guideline>Be descriptive but concise (2-4 words max)</guideline>
<guideline>Avoid redundancy (don't repeat type in description)</guideline>
<guideline>Use imperative mood (add, not adding)</guideline>
<examples>
<good>feat/openagents-integration</good>
<good>fix/api-timeout</good>
<good>perf/reduce-bundle-size</good>
<bad>feat/adding-new-feature</bad>
<bad>fix/fix-the-bug</bad>
<bad>feat/IMPLEMENT_OAUTH</bad>
</examples>
</short_desc_guidelines>
</branch_naming_convention>

<branch_creation_workflow>
<step number="1">Check commit history: `git log --all --format='%an' | sort | uniq -c`</step>
<step number="2">Determine if solo (all elhaam) or collaborative (mixed authors)</step>
<step number="3">Create branch with appropriate naming convention</step>
<step number="4">Verify branch created: `git branch --show-current`</step>
</branch_creation_workflow>
</branching_strategy>

<code_review_workflow>
<before_committing>
<step number="1">Review your changes: `git diff`</step>
<step number="2">Run CodeRabbit: `coderabbit review --plain`</step>
<step number="3">Apply feedback (security, performance, best practices)</step>
<step number="4">Stage changes: `git add <files>`</step>
<step number="5">Commit with conventional format</step>
</before_committing>

<using_commit_command>
<preferred_method>Use `/commit` command instead of manual git commit</preferred_method>
<benefits>
<benefit>Automatic CodeRabbit review integration</benefit>
<benefit>Enforces conventional commit format</benefit>
<benefit>Validates changes before committing</benefit>
<benefit>Consistent commit workflow across all tasks</benefit>
</benefits>
<usage>
<example>User: "commit these changes"</example>
<example>Agent: Uses `/commit` command (routes to commit agent)</example>
<example>Commit agent: Reviews diff → CodeRabbit → Conventional commit</example>
</usage>
</using_commit_command>

<coderabbit_focus_areas>
<area>Security vulnerabilities</area>
<area>Performance issues</area>
<area>Best practice violations</area>
<area>Code smells and anti-patterns</area>
<area>Type safety improvements</area>
</coderabbit_focus_areas>
</code_review_workflow>
</git_usage>

---

<engineers_mindset>
<principle>Ship code you'd trust your **future self** to maintain</principle>
<principle>Don't chase speed at the expense of stability</principle>
<principle>AI-generated code must **pass your quality checks**, not the other way around</principle>
</engineers_mindset>
