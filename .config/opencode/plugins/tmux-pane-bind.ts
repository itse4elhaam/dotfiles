import { readFileSync, writeFileSync, renameSync, existsSync, mkdirSync } from "fs"
import { execFileSync } from "child_process"
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
  const override = [
    process.env.tmux_session_name,
    process.env.tmux_window_index,
    process.env.tmux_pane_index,
    process.env.pane_current_path,
  ]

  if (override.every(Boolean)) {
    return `${override[0]}:${override[1]}.${override[2]}|${override[3]}`
  }

  const pane = process.env.TMUX_PANE
  if (!pane) return null

  try {
    const format = "#{session_name}\t#{window_index}\t#{pane_index}\t#{pane_current_path}"
    const output = execFileSync("tmux", ["display-message", "-p", "-t", pane, format], {
      encoding: "utf-8",
    }).trim()
    const [session, windowIdx, paneIdx, cwd] = output.split("\t")
    if (!session || !windowIdx || !paneIdx || !cwd) return null
    return `${session}:${windowIdx}.${paneIdx}|${cwd}`
  } catch {
    return null
  }
}

function getBindingStorePath(): string {
  const dataHome = process.env.XDG_DATA_HOME || join(process.env.HOME || tmpdir(), ".local/share")
  return join(dataHome, "opencode", "pane-bindings.json")
}

function writeBinding(key: string, sessionID: string): void {
  const storePath = getBindingStorePath()
  const dir = dirname(storePath)

  try {
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
  } catch {
    return
  }

  let store: Record<string, { sessionID: string; updatedAt: string }> = {}
  try {
    if (existsSync(storePath)) store = JSON.parse(readFileSync(storePath, "utf-8"))
  } catch {
    store = {}
  }

  store[key] = {
    sessionID,
    updatedAt: new Date().toISOString(),
  }

  const tmpPath = join(dir, `.pane-bindings-${process.pid}-${Date.now()}.tmp`)
  try {
    writeFileSync(tmpPath, JSON.stringify(store, null, 2), "utf-8")
    renameSync(tmpPath, storePath)
  } catch {
    try {
      if (existsSync(tmpPath)) renameSync(tmpPath, storePath)
    } catch {}
  }
}

function recordBindingForCurrentPane(sessionID: string): void {
  if (!isPaneRestoreEnabled() || !isInTmux() || !sessionID) return
  const key = buildPaneKey()
  if (key) writeBinding(key, sessionID)
}

type SessionInfo = {
  id?: string
  parentID?: string
  directory?: string
}

function rootSessionFromEvent(event: any, directory?: string): string | null {
  if (event?.type !== "session.created" && event?.type !== "session.updated") return null
  const info = event?.properties?.info as SessionInfo | undefined
  if (!info?.id || info.parentID) return null
  if (directory && info.directory && info.directory !== directory) return null
  return info.id
}

async function createTmuxPaneBindPlugin(ctx: { directory?: string }): Promise<Record<string, (input: any) => Promise<void>>> {
  if (!isPaneRestoreEnabled() || !isInTmux()) return {}

  const rootSessions = new Set<string>()

  return {
    "chat.message": async (input: { sessionID?: string }) => {
      if (!input?.sessionID) return
      rootSessions.add(input.sessionID)
      recordBindingForCurrentPane(input.sessionID)
    },
    event: async ({ event }: { event?: any }) => {
      const rootSessionID = rootSessionFromEvent(event, ctx.directory)
      if (rootSessionID) {
        rootSessions.add(rootSessionID)
        recordBindingForCurrentPane(rootSessionID)
        return
      }

      if (event?.type === "session.idle") {
        const sessionID = event?.properties?.sessionID
        if (sessionID && rootSessions.has(sessionID)) {
          recordBindingForCurrentPane(sessionID)
        }
      }
    },
  }
}

export {
  createTmuxPaneBindPlugin,
  buildPaneKey,
  getBindingStorePath,
  writeBinding,
  recordBindingForCurrentPane,
  rootSessionFromEvent,
  isPaneRestoreEnabled,
  isInTmux,
}
export default createTmuxPaneBindPlugin
