---
description: List all enabled MCP servers with capabilities
agent: build
---

List all enabled MCP servers from the OpenCode configuration.

STEPS:
1. Parse enabled servers from ~/.config/opencode/opencode.json:
   !`jq -r '.mcp | to_entries[] | select(.value.enabled != false) | "\(.key) (\(.value.type))"' ~/.config/opencode/opencode.json`

2. For each enabled server listed above, read its description from @docs/ai-guide.md (MCP Servers section)

3. Format output as a clear, organized list grouped by category:
   - Documentation & Research
   - Code Analysis & GitHub
   - Development Tools
   - File & System Operations
   - Utilities

For each server include:
- **Server Name** (type)
- Purpose: [brief description from ai-guide.md]
- Use when: [use case]
- Example: [example command]

This provides both accuracy (from config) and educational value (from docs).
