# OpenCode Configuration

This directory contains custom OpenCode configuration including agents, commands, tools, plugins, and context guides.

## Setup

After cloning this repository or pulling updates that modify OpenCode tools/plugins:

```bash
cd .config/opencode
npm install
```

This installs the required `@opencode-ai/plugin` package needed for custom tools.

## Structure

```
.config/opencode/
├── agent/          # Custom agents (3 primary + 12 subagents)
├── command/        # Custom commands (commit, study, test, etc.)
├── tool/           # Custom tools (requires @opencode-ai/plugin)
├── plugin/         # Plugins (Cursor proxy)
├── context/        # Context guides and documentation
├── opencode.json   # Main configuration
├── package.json    # Node.js dependencies
└── .gitignore      # Ignores node_modules, logs, etc.
```

## Custom Tools

Custom tools in `tool/` use the `@opencode-ai/plugin` API:

```typescript
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Tool description",
  args: {},
  async execute(args, context) {
    // Tool implementation
    return "Result"
  },
})
```

## Cursor AI Provider

The Cursor proxy plugin (`plugin/cursor-proxy.ts`) provides native Cursor AI integration:

- **Port**: 9876
- **Models**: Auto, Claude 4.5, GPT-5.1, Gemini 3 Pro, etc.
- **Requirements**: Cursor Pro subscription
- **Docs**: See `plugin/README-cursor-plugin.md`

## Troubleshooting

### "Cannot find module '@opencode-ai/plugin'" Error

This means the dependencies aren't installed. Run:

```bash
cd .config/opencode
npm install
```

### Tool Not Loading

1. Check that `package.json` exists
2. Verify `node_modules/@opencode-ai/plugin` is installed
3. Restart OpenCode

### Testing Setup

Run the test script:

```bash
cd /path/to/dotfiles
bash /tmp/test-opencode-tool.sh
```

## Git Workflow

- `node_modules/` is ignored (don't commit)
- `package.json` is tracked (commit this)
- `package-lock.json` is ignored (npm generates this)
- Logs (`.log` files) are ignored

## Documentation

- **AGENTS.md**: Agent guide and project overview (in repository root)
- **ai-guide.md**: AI assistant instructions (in `docs/`)
- **plugin/README-cursor-plugin.md**: Cursor integration details
