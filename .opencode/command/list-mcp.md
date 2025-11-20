---
description: List all enabled MCP servers with capabilities and detailed documentation
agent: build
---

List all enabled MCP servers from the OpenCode configuration with comprehensive details.

STEPS:

1. **Parse enabled servers** from ~/.config/opencode/opencode.json:
   !`jq -r '.mcp | to_entries[] | select(.value.enabled != false) | "\(.key) (\(.value.type))"' ~/.config/opencode/opencode.json`

2. **Read MCP documentation** from @docs/ai-guide.md:
   - Extract the entire "## MCP Servers" section
   - This section contains all server descriptions, use cases, and examples

3. **Cross-reference and format** the output:
   - Group by category (Documentation & Research, Code Analysis, etc.)
   - For each enabled server from step 1, pull its full description from step 2
   - Include:
     - **Server Name** (type)
     - Purpose: [description from ai-guide.md]
     - Use when: [use case from ai-guide.md]
     - Example: [example from ai-guide.md]

4. **Add usage guidelines** at the end:
   - Prefer specialized tools over bash commands
   - Check enabled status before using
   - Use Task tool for exploratory searches
   - Batch independent MCP calls in parallel

This command provides both accuracy (from opencode.json) and educational value (from ai-guide.md documentation).
