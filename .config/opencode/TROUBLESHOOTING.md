# OpenCode Troubleshooting Guide

Quick reference for common OpenCode issues.

## Cursor Proxy Issues

### Server Not Starting

**Symptoms**: No "Cursor proxy running" message on OpenCode startup

**Check**:
```bash
# Is the server running?
lsof -i :9876

# Check logs
tail -f .opencode/cursor-proxy.log
```

**Fix**:
```bash
# Restart OpenCode
# The server should auto-start

# If port conflict:
lsof -ti:9876 | xargs kill
```

### Server Shutting Down Prematurely

**Symptoms**: Logs show "shutting down" shortly after "started"

**Expected Behavior** (after fix):
- ✅ Server starts once when OpenCode launches
- ✅ Stays alive for entire session
- ✅ Only shuts down when OpenCode terminates

**If still happening**:
1. Restart OpenCode to load latest code
2. Check you're on commit `eefc9d6` or later
3. Verify plugin file is up to date

### Connection Refused Errors

**Symptoms**: "ECONNREFUSED" when using Cursor models

**Check**:
```bash
# Is server running?
lsof -i :9876

# Recent logs
tail -20 .opencode/cursor-proxy.log
```

**Fix**:
1. Restart OpenCode
2. Wait 2-3 seconds for server to start
3. Try Cursor model again

## Tool Import Errors

### "Cannot find module '@opencode-ai/plugin'"

**Symptoms**: Error when loading custom tools

**Fix**:
```bash
cd .config/opencode
npm install
```

**Verify**:
```bash
ls -la node_modules/@opencode-ai/plugin
# Should exist
```

## Plugin Not Loading

### Custom tools/plugins not available

**Check**:
```bash
# Are symlinks correct?
ls -la ~/.config/opencode/plugin/
ls -la ~/.config/opencode/tool/

# Is package.json present?
cat .config/opencode/package.json
```

**Fix**:
```bash
# Reinstall dependencies
cd .config/opencode
npm install

# Restart OpenCode
```

## Logs Location

Logs are in the **project directory**, not dotfiles:

```bash
# Current project
tail -f .opencode/cursor-proxy.log

# Dotfiles (when working in dotfiles repo)
tail -f /home/e4elhaam/dotfiles/.opencode/cursor-proxy.log
```

## Health Checks

### Quick System Check

```bash
# 1. Check proxy server
lsof -i :9876

# 2. Check dependencies
ls .config/opencode/node_modules/@opencode-ai/

# 3. Check recent logs
tail -5 .opencode/cursor-proxy.log

# 4. Test proxy health
curl -s http://127.0.0.1:9876/v1/models | jq .
```

### Expected Output

**Healthy system**:
- ✅ Port 9876 has a listening process
- ✅ `@opencode-ai/plugin` installed
- ✅ Logs show "started" but NOT recent "shutting down"
- ✅ `/v1/models` returns JSON with Cursor models

## Common Issues & Fixes

| Issue | Symptom | Fix |
|-------|---------|-----|
| Import error | "Cannot find module" | `cd .config/opencode && npm install` |
| Server down | Port 9876 not listening | Restart OpenCode |
| Port conflict | "EADDRINUSE" | `lsof -ti:9876 \| xargs kill` |
| Premature shutdown | Server stops after 1-2s | Update to latest commit, restart |
| Wrong workspace | Using old directory | Restart OpenCode (auto-updates) |

## Getting Help

1. **Check logs**: `.opencode/cursor-proxy.log`
2. **Verify versions**: `git log --oneline -5` (should include `eefc9d6`)
3. **Run health check**: See "Quick System Check" above
4. **Restart OpenCode**: Fixes most issues

## Recent Fixes

- **2025-12-04**: Fixed premature server shutdown (commit `eefc9d6`)
- **2025-12-04**: Fixed plugin import errors (commit `94ac37a`)

---

**Last Updated**: December 4, 2025  
**Applies To**: OpenCode 1.0.132+
