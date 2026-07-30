import { readFileSync, writeFileSync, renameSync, existsSync, mkdirSync } from "fs"
import { join, dirname } from "path"
import { tmpdir } from "os"

function isPaneRestoreEnabled(): boolean {
  const val = process.env.OPENCODE_PANE_RESTORE ?? ""
  if (!val) return true
  const lower = val.toLowerCase()
  return ["1", "true", "yes", "on", "enabled"].includes(lower)
}

function isInTmux(): boolean {
  return !!process.env.TMUX_PANE
}

function buildPaneKey(): string | null {
  const session = process.env.tmux_session_name
  const windowIdx = process.env.tmux_window_index
  const paneIdx = process.env.tmux_pane_index
  const cwd = process.env.pane_current_path
  if (!session || !windowIdx || !paneIdx || !cwd) return null
  return `${session}:${windowIdx}.${paneIdx}|${cwd}`
}

function getBindingStorePath(): string {
  const dataHome = process.env.XDG_DATA_HOME || join(process.env.HOME || tmpdir(), ".local/share")
  return join(dataHome, "opencode", "pane-bindings.json")
}

function writeBinding(key: string, sessionID: string): void {
  const storePath = getBindingStorePath()
  const dir = dirname(storePath)

  try {
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true })
    }
  } catch {
    return
  }

  let store: Record<string, { sessionID: string; updatedAt: string }> = {}
  try {
    if (existsSync(storePath)) {
      store = JSON.parse(readFileSync(storePath, "utf-8"))
    }
  } catch {
    store = {}
  }

  store[key] = {
    sessionID,
    updatedAt: new Date().toISOString(),
  }

  const tmpPath = join(dir, `.pane-bindings-${process.pid}.tmp`)
  try {
    writeFileSync(tmpPath, JSON.stringify(store, null, 2), "utf-8")
    renameSync(tmpPath, storePath)
  } catch {
    try { existsSync(tmpPath) && renameSync(tmpPath, storePath) } catch {}
  }
}

function recordBindingForCurrentPane(sessionID: string): void {
  if (!isPaneRestoreEnabled() || !isInTmux() || !sessionID) return
  const key = buildPaneKey()
  if (key) {
    writeBinding(key, sessionID)
  }
}

async function createTmuxPaneBindPlugin(_ctx: { directory?: string }): Promise<Record<string, (input: any) => Promise<void>>> {
  if (!isPaneRestoreEnabled() || !isInTmux()) {
    return {}
  }

  return {
    "chat.message": async (input: { sessionID?: string }) => {
      if (input?.sessionID) {
        recordBindingForCurrentPane(input.sessionID)
      }
    },
  }
}

export { createTmuxPaneBindPlugin, buildPaneKey, getBindingStorePath, writeBinding, isPaneRestoreEnabled, isInTmux }
export default createTmuxPaneBindPlugin
