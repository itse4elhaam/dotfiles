import type { Plugin } from "@opencode-ai/plugin"
import {
  currentPaneIdentity,
  opencodeDataHome,
  parseSessionID,
  recordPaneBinding,
} from "../lib/continue-with-pane"

const ContinueWithPanePlugin: Plugin = async () => {
  const pane = currentPaneIdentity()
  if (!pane) {
    return {}
  }

  return {
    "chat.message": async (input) => {
      const sessionID = parseSessionID(input.sessionID)
      if (!sessionID) {
        return
      }

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
    },
  }
}

export default ContinueWithPanePlugin
