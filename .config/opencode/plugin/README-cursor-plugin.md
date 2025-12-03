# Cursor AI Provider for OpenCode

Native integration of **all Cursor AI models** (including Auto mode) into OpenCode's model switcher via local proxy server.

## Features

✨ **Native Experience**: Cursor models appear in OpenCode's model switcher - select and chat naturally
🔄 **Auto Mode**: Let Cursor automatically pick the best model for your task
🤖 **All Models**: Access GPT-5.1, Claude 4.5, Gemini 3 Pro, and more
🌐 **Local Proxy**: Transparent HTTP proxy translates OpenAI format to cursor-agent CLI
📊 **Error Logging**: Detailed logs in `.opencode/cursor-proxy.log`
🔗 **Global Setup**: Install once, use in all projects

## How It Works

```
YOU → Select "Cursor: Auto" in OpenCode
  ↓
OpenCode → Sends OpenAI-format request to http://127.0.0.1:9876
  ↓
Proxy Plugin → Translates to cursor-agent CLI call
  ↓
Cursor API → Processes with selected model
  ↓
Proxy Plugin → Returns OpenAI-format response
  ↓
OpenCode → Displays response naturally
```

**Result**: Chat with Cursor exactly like Claude or GPT-4 - no special commands needed!

## Prerequisites

### ⚠️ **IMPORTANT: Cursor Pro Subscription Required**

The Cursor Cloud Agent API (which this plugin uses) is **only available for Cursor Pro subscribers**. Free tier users cannot access the API.

**Pricing**: ~$20/month for Pro  
**Upgrade**: https://www.cursor.com/pricing

---

1. **Cursor CLI** installed:
   ```bash
   curl https://cursor.com/install -fsS | bash
   ```

2. **✨ Cursor Pro Subscription** (Pro/Max/Business) for API access
   - **Free tier does NOT have API access**
   - You'll see "resource_exhausted" errors without Pro

3. **OpenCode** installed:
   ```bash
   npm install -g opencode-ai
   ```

4. **Authentication** (choose one):
   - Interactive login: `cursor-agent` (follow prompts)
   - API Key: Export `CURSOR_API_KEY` in your shell profile

## Installation

### Quick Install

```bash
cd /home/elhaam/dotfiles
./.config/opencode/plugin/install-cursor-plugin.sh
```

This will:
- ✓ Check for `cursor-agent` installation
- ✓ Verify authentication status
- ✓ Create symlink: `~/.config/opencode/plugin/cursor-cli.ts`
- ✓ Enable plugin globally for all projects

### Manual Installation

1. Copy plugin to global OpenCode directory:
   ```bash
   mkdir -p ~/.config/opencode/plugin
   ln -s /home/elhaam/dotfiles/.config/opencode/plugin/cursor-cli.ts ~/.config/opencode/plugin/cursor-cli.ts
   ```

2. Restart OpenCode or reload configuration

## Authentication Setup

### Option 1: Interactive Login (Recommended)
```bash
cursor-agent
# Follow the prompts to authenticate with your Cursor account
```

### Option 2: API Key
```bash
# Get API key from https://cursor.com/settings
export CURSOR_API_KEY=your_api_key_here

# Add to your shell profile (~/.zshrc or ~/.bashrc):
echo 'export CURSOR_API_KEY=your_api_key_here' >> ~/.zshrc
```

## Usage

### Native Model Selection

1. **Start OpenCode**: The proxy server starts automatically when OpenCode loads
2. **Select Model**: Use `/models` command or model switcher
3. **Choose Cursor**: Select any Cursor model (e.g., "Cursor: Auto")
4. **Chat Naturally**: Type your messages - no special commands needed!

```
# In OpenCode TUI
/models
> Select: Cursor: Auto

# Then just chat normally
> Explain this authentication function
[Cursor AI responds directly]

> Refactor this code to use async/await
[Cursor AI responds directly]
```

### Available Models in Switcher

When you run `/models`, you'll see:

- **Cursor: Auto** - Cursor picks the best model automatically (⭐ recommended)
- **Cursor: Claude 4.5 Opus High Thinking** - Claude 4.5 with high reasoning
- **Cursor: Claude 4.5 Sonnet Thinking** - Claude 4.5 with thinking mode
- **Cursor: GPT 5.1 Codex** - OpenAI GPT-5.1 for coding
- **Cursor: GPT 5.1 Codex High** - GPT-5.1 with higher quality
- **Cursor: Gemini 3 Pro** - Google Gemini 3 Pro

### Model Comparison

| Model | Best For | Context | Speed |
|-------|----------|---------|-------|
| **Auto** | Everything (Cursor picks) | 200K | Varies |
| **Claude 4.5 Opus** | Complex reasoning, architecture | 200K | Slow |
| **Claude 4.5 Sonnet** | Balanced coding tasks | 200K | Medium |
| **GPT 5.1 Codex** | Fast code generation | 128K | Fast |
| **GPT 5.1 Codex High** | High-quality code | 128K | Medium |
| **Gemini 3 Pro** | Massive context needs | 1M | Medium |

### Example Workflows

**Quick Coding**
```
/models → Select "Cursor: GPT 5.1 Codex"
> Create a React component for user authentication
```

**Complex Architecture**
```
/models → Select "Cursor: Claude 4.5 Opus High Thinking"
> Design a microservices architecture for this e-commerce platform
```

**Let Cursor Decide**
```
/models → Select "Cursor: Auto"
> Whatever you ask, Cursor picks the best model automatically
```

## Real-World Usage Examples

### Code Review

```
Use cursor_chat with model=claude-4-sonnet-thinking to review this pull request:
- Check for security vulnerabilities
- Identify potential bugs
- Suggest performance improvements
- Verify best practices compliance
```

### Refactoring

```
Use cursor_agent with force=true to:
1. Extract repeated logic into reusable functions
2. Apply modern JavaScript patterns
3. Improve error handling
4. Add TypeScript types where missing
```

### Documentation

```
Use cursor_agent with force=true and model=gpt-5 to generate comprehensive API documentation:
- Document all public methods
- Add usage examples
- Include parameter descriptions
- Create README sections
```

### Architecture Analysis

```
Use cursor_chat with model=claude-4-opus-thinking to:
- Analyze the current architecture
- Identify coupling issues
- Suggest design pattern improvements
- Propose refactoring strategy
```

## Output & Streaming

The plugin uses `--stream-partial-output` for real-time streaming:

```
🤖 Using Cursor model: claude-4-sonnet-thinking

[Streaming response text appears character by character...]

🔧 Tool executing: {"readToolCall":{"args":{"path":"src/auth.ts"}}}
✅ Tool completed: {"readToolCall":{"result":{"success":{...}}}}

⏱️  Completed in 3456ms
```

## Error Handling

### User-Friendly Messages

All errors show clear, actionable messages:

```
⚠️  Cursor Pro subscription required.
The Cloud Agent API is only available for Pro users.
Upgrade at https://www.cursor.com/pricing
```

```
⚠️  Cursor authentication required.
Run 'cursor-agent' to login or set CURSOR_API_KEY environment variable.
```

```
⚠️  Cursor CLI not installed.
Install with: curl https://cursor.com/install -fsS | bash
```

### Detailed Error Logs

All errors are logged to `.opencode/cursor-errors.log` with:
- Timestamp
- Error context
- Full stack trace

**View logs:**
```bash
tail -f .opencode/cursor-errors.log
```

## Troubleshooting

### Plugin Not Loading

1. Check plugin is symlinked correctly:
   ```bash
   ls -la ~/.config/opencode/plugin/cursor-cli.ts
   ```

2. Restart OpenCode:
   ```bash
   opencode
   ```

3. Check OpenCode logs for TypeScript errors

### "resource_exhausted" or "not available for free users" Error

**This is the most common issue!**

The Cursor Cloud Agent API requires a **Cursor Pro subscription**. Free tier users will see:
```
ConnectError: [resource_exhausted] Error
```
or
```
Cloud Agent is not available for free users
```

**Solution**: Upgrade to Cursor Pro at https://www.cursor.com/pricing (~$20/month)

The plugin will still work after upgrading - just restart OpenCode.

### Authentication Issues

1. Verify cursor-agent works:
   ```bash
   cursor-agent -p "test prompt"
   ```

2. Check API key is set:
   ```bash
   echo $CURSOR_API_KEY
   ```

3. Re-authenticate:
   ```bash
   cursor-agent  # Interactive login
   ```

### Rate Limiting

If you hit rate limits:
- Wait a few minutes and retry
- Use `model=auto` for better rate limit management
- Consider upgrading your Cursor subscription

### Empty Responses

If responses are empty:
1. Check error log: `tail .opencode/cursor-errors.log`
2. Verify cursor-agent CLI works directly
3. Ensure subscription is active

## Advanced Configuration

### Custom Model Preferences

Edit `.opencode/plugin/cursor-cli.ts` to change the default model:

```typescript
// Change line ~184
.default("gpt-5")  // Instead of "auto"
```

### Disable Streaming

For JSON-only output, modify the execute functions to use:
```typescript
--output-format json  // Instead of stream-json
```

### Add New Models

When Cursor releases new models, add them to the `CURSOR_MODELS` array (line ~116):

```typescript
const CURSOR_MODELS = [
	"auto",
	"gpt-5",
	"new-model-name",  // Add here
	// ...
] as const;
```

## File Structure

```
dotfiles/
└── .opencode/
    ├── plugin/
    │   ├── cursor-cli.ts              # Main plugin (586 lines)
    │   └── install-cursor-plugin.sh   # Installation script
    └── cursor-errors.log              # Error logs (auto-generated)

~/.config/opencode/plugin/
└── cursor-cli.ts -> /home/elhaam/dotfiles/.opencode/plugin/cursor-cli.ts
```

## Uninstallation

```bash
# Remove symlink
rm ~/.config/opencode/plugin/cursor-cli.ts

# Remove error logs
rm /home/elhaam/dotfiles/.opencode/cursor-errors.log
```

## Contributing

This plugin is part of the dotfiles repository. To contribute:

1. Edit `.opencode/plugin/cursor-cli.ts`
2. Test changes: `opencode` in any project
3. Check error logs: `tail -f .opencode/cursor-errors.log`
4. Commit with conventional format: `feat(cursor-plugin): description`

## Support

- **Cursor CLI Docs**: https://cursor.com/docs/cli
- **OpenCode Plugins**: https://opencode.ai/docs/plugins
- **Issues**: Check `.opencode/cursor-errors.log` for detailed errors
- **Cursor Support**: https://cursor.com/support

## License

Part of personal dotfiles. Use freely, no warranty provided.

---

**Version**: 1.0.0  
**Author**: elhaam  
**Date**: December 2025  
**Cursor CLI Version**: 2025.11.06-8fe8a63  
**OpenCode Version**: 1.x
