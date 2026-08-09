# OPENCODE CONFIG KNOWLEDGE BASE

## OVERVIEW
Configuration for OpenCode AI environment, defining agents, tools, and commands.

## STRUCTURE
```
.config/opencode/
├── opencode.json   # Main configuration
├── agent/          # Custom agent definitions
├── command/        # Slash command definitions
├── tool/           # Custom MCP tools
└── context/        # Context files
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| **Config** | `opencode.json` | Enabled MCPs, instructions |
| **Agents** | `agent/*.md` | YAML frontmatter definitions |
| **Commands** | `command/*.md` | Slash command definitions |

## CONVENTIONS
- **Schema**: JSON for config, Markdown+YAML for agents/commands
- **Paths**: relative to project root or `~/.config/opencode`

## Browser Automation

- Use `agent-browser` (skill or CLI) for ALL browser operations: navigation, screenshots, scraping, form interaction, E2E.
- Playwright, playwright-cli, dev-browser, Puppeteer, Selenium are BLOCKED. If you get a denial/permission error when trying them, switch to `agent-browser` immediately.
- If agent-browser is unavailable, stop and report. Never fall back.

## NOTES
