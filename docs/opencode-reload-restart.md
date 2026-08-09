# OpenCode: Configuration Reload & Restart

**Date researched:** 2026-08-09 · **User version:** 1.17.18 · **Latest stable at research time:** 1.18.15 (2026-08-07) · **Repo HEAD researched:** `38e10eb` (dev branch), `84fd347` (v2 branch)

---

## Verdict (TL;DR)

| Question | Answer |
|---|---|
| (a) Built-in reload command / keybind / CLI flag? | **No documented one in stable (≤1.18.15).** No `/reload` slash command, no keybind, no CLI flag. The only built-in (undocumented) mechanism is **sending `SIGUSR2` to the opencode process**, which disposes all instances and forces the TUI to re-bootstrap, re-reading config/commands/agents from disk. A `/reload` slash command exists only as an **open, unmerged PR (#9871)**. |
| (b) Does opencode hot-reload config files? | **No, not in stable.** Config is loaded once at startup; the built-in `customize-opencode` skill explicitly instructs agents to "tell the user to quit and restart opencode" after config edits. Partial hot-reload (config change feed → command reload, MCP reload, TUI plugin hot-reload) is being built **only on the `v2` branch**, not released. |
| (c) Plugin that adds reload/restart? | **None verified.** No plugin in the official ecosystem list or npm does this. The `/reload` PR #9871 is unmerged; plugin API has no config-reload hook. |
| (d) Recommended official way? | **Quit and restart the TUI** (`/exit` or `Ctrl+x q`, then `opencode`). For a lighter path, `SIGUSR2` reloads without exiting the process (undocumented, kills in-memory session state). |

---

## 1. Built-in reload/restart mechanism

### 1.1 No slash command, keybind, or CLI flag (stable ≤ 1.18.15)

- **TUI built-in commands** (`/help` list): `connect, compact, details, editor, exit, export, help, init, models, new, redo, sessions, share, themes, thinking, undo, unshare` — **no reload/restart**. Source: [TUI docs — Commands](https://opencode.ai/docs/tui#commands).
- **Keybinds**: full inventory in [Keybinds docs](https://opencode.ai/docs/keybinds) — no `reload`/`restart`/`config_reload` action exists. (The `app_exit` keybind is `ctrl+c,ctrl+d,<leader>q`; `/exit` = `ctrl+x q`.)
- **CLI**: full command list in [CLI docs](https://opencode.ai/docs/cli) (`tui, agent, attach, auth, github, mcp, models, run, serve, session, stats, export, import, web, acp, plugin, pr, db, debug, uninstall, upgrade`) — no `reload`/`restart` subcommand, no reload flag.
- **Config schema** (`opencode.ai/config.json`, `opencode.ai/tui.json`): no `reload`/`restart` key.

### 1.2 The undocumented built-in: `SIGUSR2` reload (present in v1.17.18)

There **is** a hidden reload path: the TUI registers a `SIGUSR2` signal handler that tells the backend worker to invalidate config and dispose all instances, which makes the TUI re-bootstrap and re-read everything from disk.

**Evidence (current dev, 1.18.15; verified identical in tag v1.17.18):**

1. Signal handler in the TUI launcher — [`packages/opencode/src/cli/cmd/tui.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/cli/cmd/tui.ts#L216-L219):
```typescript
const reload = () => {
  client.call("reload", undefined).catch(() => {})
}
process.on("SIGUSR2", reload)
```
2. Worker RPC — [`packages/opencode/src/cli/tui/worker.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/cli/tui/worker.ts#L63-L71):
```typescript
async reload() {
  await AppRuntime.runPromise(
    Effect.gen(function* () {
      const cfg = yield* Config.Service
      yield* cfg.invalidate()
      yield* disposeAllInstancesAndEmitGlobalDisposed({ swallowErrors: true })
    }),
  )
}
```
3. Dispose emits `server.instance.disposed` per instance — [`packages/opencode/src/project/instance-store.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/project/instance-store.ts#L79-L87):
```typescript
payload: { type: "server.instance.disposed", properties: { directory: input.directory } }
```
4. TUI subscribes to that event and re-bootstraps — [`packages/tui/src/context/sync.tsx`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/tui/src/context/sync.tsx#L176-L180):
```typescript
event.subscribe((event, { directory, workspace }) => {
  switch (event.type) {
    case "server.instance.disposed":
      void bootstrap()
      break
```
5. `bootstrap()` re-fetches agents, config, providers, and commands — [`packages/tui/src/context/sync.tsx`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/tui/src/context/sync.tsx#L451-L477) + command list at line 523:
```typescript
sdk.client.command.list({ workspace }).then((x) => setStore("command", reconcile(x.data ?? [])))
```

**How to use it:** `kill -USR2 <opencode-pid>` (or from inside tmux, bind a key / use `tmux send-keys`). **Caveats (unverified in docs — read from source):**
- It disposes **all** instances — in-memory session state is torn down (sessions reload from disk on bootstrap). This matches PR #13409's note that instance-dispose "kills all active sessions".
- It is **not documented** anywhere (docs, `--help`, release notes) — treat as internal/unofficial.
- Because `SIGUSR2` is only registered in the TUI launcher process (`tui.ts`), it works for the TUI; a plain `opencode run`/`serve` process does not register this handler (verified: handler is only in the TUI command path).

### 1.3 HTTP dispose endpoint (equivalent)

The server exposes `POST /global/dispose` which does the same "dispose all instances" (used by `/reload` PR). Source: [`packages/opencode/src/server/routes/instance/httpapi/groups/global.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/server/routes/instance/httpapi/groups/global.ts#L69) and handler [`global.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/server/routes/instance/httpapi/handlers/global.ts#L92-L95). Not documented as user-facing.

---

## 2. Is config hot-reloaded? (No, in stable)

### 2.1 Official documentation says: load once, restart required

The built-in `customize-opencode` skill (shipped inside opencode) states it explicitly — [`packages/core/src/plugin/skill/customize-opencode.md`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/core/src/plugin/skill/customize-opencode.md#L32-L36):
```
Config is loaded once when opencode starts and is not hot-reloaded. After
saving changes to `opencode.json`, an agent file, a skill, a plugin, or any
other config-time file, **tell the user to quit and restart opencode** for
the changes to take effect. The running session will keep using the
already-loaded config until then.
```
Also lines 452-453: "After saving any config change, remind the user to quit and restart opencode — running sessions keep using the already-loaded config."

### 2.2 Source confirms config is read once at startup

- The whole config (including `~/.config/opencode/command/*.md` commands via `ConfigCommand.load`) is materialized inside `Config.state`, a per-directory cache — [`packages/opencode/src/config/config.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/config/config.ts#L600-L604). Markdown command files are globbed and merged here — [`config/command.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/config/command.ts#L13-L39) scans `{command,commands}/**/*.md`.
- The Command service builds its registry once from config + MCP prompts + skills, and serves from that cached state — [`packages/opencode/src/command/index.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/command/index.ts#L65-L169) (`Command.get`/`list` just read `state.commands`).
- The cache is only invalidated when the instance is disposed (e.g. process exit or the SIGUSR2 path) — [`packages/opencode/src/effect/instance-state.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/effect/instance-state.ts#L26-L45), disposer at line 38 invalidates the `ScopedCache`.
- **No watcher subscribes to config files in stable.** The file watcher (`packages/core/src/filesystem/watcher.ts`) publishes file events but is not wired to reload config; the `watcher.ignore` config option only controls ignore patterns. Confirmed by issue #39987 (below).

### 2.3 Community confirmation (issues)

- **#39987 [open]** — "[FEATURE]: apply plugin / MCP / config changes without restarting the running session" (2026-08-01): body states "Config is read once at startup, plugins are resolved/imported once, and MCP servers are connected once" and "nothing watches the files afterwards (there is an experimental `OPENCODE_EXPERIMENTAL_FILEWATCHER` flag, but it does not reload config)". https://github.com/anomalyco/opencode/issues/39987
- **#34408 [open]** — "Skills not hot-reloaded: must restart opencode after creating a new skill" (2026-06-29). https://github.com/anomalyco/opencode/issues/34408
- **#34443 [open]** — "Skill file changes (add/remove/edit) not picked up until app restart due to never-evict in-memory cache" (2026-06-xx). https://github.com/anomalyco/opencode/issues/34443
- **#36405 [open]** — "new skills dont show up in current session" (2026-07-11). https://github.com/anomalyco/opencode/issues/36405
- **#8751 [open]** — "[FEATURE]: Hot-reload agents, skills and commands." (2026-01-15). https://github.com/anomalyco/opencode/issues/8751
- **#34492 [open]** — "[FEATURE]: Add unified file watching and hot reload service". https://github.com/anomalyco/opencode/issues/34492

---

## 3. How custom slash commands load (startup-only, not re-read per invocation)

Your `~/.config/opencode/command/paste-image.md` (+ `.sh`) is loaded by the config loader:

- Glob pattern is `{command,commands}/**/*.md` (both singular and plural dir names supported) — [`packages/opencode/src/config/command.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/config/command.ts#L15). Frontmatter (`description`, `agent`, etc.) + body become the command template.
- These are merged into `result.command` inside the config state at instance load — [`packages/opencode/src/config/config.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/config/config.ts#L459) (line verified at tag v1.17.18 too).
- The Command service reads that config **once** into a per-directory cache; `get`/`list` never re-scan the directory — [`packages/opencode/src/command/index.ts`](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/command/index.ts#L90-L103) and lines 161-169.

**Conclusion:** New/edited command files are **not** picked up by an already-running stable TUI — not per-invocation, not on a timer. Restart (or SIGUSR2) is required. The advice you received ("restart opencode to load it") is correct for stable 1.17.18.

---

## 4. Plugin / extension that adds reload

- **No plugin exists** in the official ecosystem list — [Ecosystem docs](https://opencode.ai/docs/ecosystem#plugins) (40+ plugins; none is a reload/restart plugin).
- **npm search** (2026-08-09) for `opencode reload` / `opencode plugin`: no reload/restart plugin. Only unrelated packages (e.g. `vite-plugin-full-reload`, `use-hot-module-reload`, `chrome-extension-hot-reload`) matched the word "reload".
- **Plugin API has no config-reload hook.** The documented plugin events ([Plugins docs](https://opencode.ai/docs/plugins#events)) include `command.executed`, `file.watcher.updated`, `tui.command.execute`, etc. — no `config.reload`/`config.updated` event, and no API to force a reload. The plugin `client` is an SDK client; no documented method reloads config.
- **PR #9871 [open]** — "feat: add /reload slash command" (created 2026-01-21, updated 2026-08-08, unmerged). Adds `/reload` that hot-reloads config, plugins, MCP servers without quitting the TUI (queues until sessions idle, uses `POST /config/reload`, shows "Reloading configuration..." overlay). Closes #6719. NOT available in stable. https://github.com/anomalyco/opencode/pull/9871
- **PR #13409 [open]** — "feat(experimental): add endpoint to allow reloading config programmatically" — experimental `/experimental/hotreload` endpoint + `opencode.hotreload.{changed,applied}` events. Unmerged. https://github.com/anomalyco/opencode/pull/13409
- **#6719 [open]** — "[FEATURE]: slash command for reload" (2026-01-03), the feature request that #9871 would close. https://github.com/anomalyco/opencode/issues/6719

---

## 5. Hot reload work on the v2 branch (not released)

A "config change feed" + watcher-based reload is being built on the **`v2` branch** (206 open PRs target v2 at research time; v2 is a separate development branch, not the released stable line):

- **PR #39160 [merged 2026-07-27, base=v2]** — "feat(core): reload commands from config change feed": subscribes `config.changes()` (filesystem updates under config roots) + `config.updated` events, debounced 100 ms, then `ctx.command.reload()`. https://github.com/anomalyco/opencode/pull/39160
- **PR #39216 [merged 2026-07-28, base=v2]** — "test(core): add native watcher command reload test". https://github.com/anomalyco/opencode/pull/39216
- **PR #39776 [merged 2026-07-31, base=v2]** — "feat(tui): hot-reload local TUI plugins". https://github.com/anomalyco/opencode/pull/39776
- **PR #41204 [merged 2026-08-08, base=v2]** — "fix(core): reload changed MCP config" (closes #37421 "Hot reload MCP server configuration"). https://github.com/anomalyco/opencode/pull/41204
- **PR #38533 [open, base=v2]** — "fix(core): reload MCP config updates". https://github.com/anomalyco/opencode/pull/38533
- **PR #37979 [open, base=v2]** — "fix(core): reload config directory changes". https://github.com/anomalyco/opencode/pull/37979
- v2 config change feed source: [`packages/core/src/config.ts` (v2)](https://github.com/anomalyco/opencode/blob/v2/packages/core/src/config.ts) exposes `changes(): Stream<Watcher.Update>`; v2 command plugin merges `sourceChanges` (file watcher) + `configUpdates` (config.updated) with 100 ms debounce — [`packages/core/src/config/plugin/command.ts` (v2)](https://github.com/anomalyco/opencode/blob/v2/packages/core/src/config/plugin/command.ts).

**These are NOT in stable 1.17.18 or 1.18.15.** The `dev` branch (stable line) still has the "load once" behavior documented in §2.

---

## 6. Recommended workflow (stable 1.17.18)

1. **Official, guaranteed:** quit the TUI and start it again.
   - `/exit` (alias `/quit`, `/q`; keybind `ctrl+x q`) — [TUI docs](https://opencode.ai/docs/tui#exit).
   - Then `opencode` in the same directory (or `opencode -c` to continue the last session).
2. **Lighter (undocumented, internal):** send `SIGUSR2` to the TUI process — `kill -USR2 $(pgrep -n opencode)`. It re-reads config, agents, commands, and MCP definitions without exiting the process, but tears down in-memory instances (sessions reload from disk). Use at your own risk; it is not part of the public API and could change.
3. **Do not rely on hot reload** — it does not exist in stable. Track these for when it ships:
   - `/reload` command: PR #9871 (open)
   - Config change feed / command reload: PR #39160 (v2, merged)
   - Unified watcher/hot-reload service: #34492 (open)
   - "Apply config without restart": #39987 (open)

### For your `paste-image` command specifically

After creating `~/.config/opencode/command/paste-image.{md,sh}`, restart the TUI (or SIGUSR2) once. After that the command definition is read from disk at startup and `/paste-image` will appear in the command palette. Editing the `.md` body later also requires a restart/SIGUSR2 to take effect in a running stable TUI.

---

## Appendix: verification notes & unverified items

- **Verified**: SIGUSR2 handler exists in both tag `v1.17.18` and current dev HEAD `38e10eb` (checked via GitHub API file contents at `ref=v1.17.18` and `ref=v2`). Worker `reload()` implementation identical in both.
- **Unverified**: whether SIGUSR2 fully reloads MCP servers in stable (MCP config reload only landed on v2). The dispose-all path re-creates instances, so MCP servers defined in config are re-read on re-bootstrap, but this was not directly tested; source-level reading suggests yes (MCP service is instance-scoped).
- **Unverified**: exact SIGUSR2 behavior on Windows (signal semantics differ; POSIX-only feature by nature).
- **Not applicable**: no modifications were made to any opencode config files during this research.
