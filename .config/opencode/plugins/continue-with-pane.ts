import type { Plugin } from "@opencode-ai/plugin"
import {
  currentPaneIdentity,
  opencodeDataHome,
  parseSessionID,
  recordPaneBinding,
} from "../lib/continue-with-pane"

type SessionInfo = {
  readonly id?: unknown
  readonly parentID?: unknown
  readonly directory?: unknown
}

const ContinueWithPanePlugin: Plugin = async (ctx) => {\n  const directory = ctx.directory
  const pane = currentPaneIdentity()
  if (!pane) {
    return {}
  }

  const knownRootSessions = new Set<string>()

  const record = (value: unknown): void => {
    const sessionID = parseSessionID(value)
    if (!sessionID) {
      return
    }

    knownRootSessions.add(sessionID)
    try {
      recordPaneBinding({
        dataHome: opencodeDataHome(),
        pane,
        sessionID,
        now: new Date(),
      })
    } catch (error) {
      if (error instanceof Error) {
        return
      }
      throw error
    }
  }

  return {
    "chat.message": async (input) => {
      record(input.sessionID)
    },
    event: async ({ event }) => {
      if (event.type === "session.created" || event.type === "session.updated") {
        const info = event.properties.info as SessionInfo
        if (info.parentID) {
          return
        }
        if (directory && info.directory && info.directory !== directory) {
          return
        }
        record(info.id)
        return
      }

      if (event.type === "session.idle" || event.type === "session.error") {
        const sessionID = parseSessionID(event.properties.sessionID)
        if (sessionID && knownRootSessions.has(sessionID)) {
          record(sessionID)
        }
      }
    },
  }
}

export default ContinueWithPanePlugin
