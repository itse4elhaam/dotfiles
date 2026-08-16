import { createEffect } from "solid-js"
import type { TuiPlugin, TuiPluginModule } from "@opencode-ai/plugin/tui"
import { recordBindingForCurrentPane } from "./tmux-pane-bind"

export function sessionIDFromRoute(route: unknown): string | null {
  if (!route || typeof route !== "object") return null
  const current = route as { name?: string; params?: { sessionID?: string } }
  if (current.name !== "session") return null
  return current.params?.sessionID || null
}

const tui: TuiPlugin = async (api) => {
  let activeSessionID: string | null = null

  const persistActiveSession = () => {
    const sessionID = sessionIDFromRoute(api.route.current)
    if (!sessionID || sessionID === activeSessionID) return
    activeSessionID = sessionID
    recordBindingForCurrentPane(sessionID)
  }

  createEffect(persistActiveSession)

  api.lifecycle.onDispose(() => {
    const sessionID = sessionIDFromRoute(api.route.current) || activeSessionID
    if (sessionID) recordBindingForCurrentPane(sessionID)
  })
}

const plugin: TuiPluginModule & { id: string } = {
  id: "elhaam.tmux-pane-bind",
  tui,
}

export default plugin
