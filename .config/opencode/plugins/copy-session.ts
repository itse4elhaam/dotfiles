import type { Plugin } from "@opencode-ai/plugin"
import type { TuiPlugin } from "@opencode-ai/plugin/tui"
import { execSync } from "node:child_process"

const CLIPBOARD_TOOLS = ["wl-copy", "xsel -b", "xclip -selection clipboard", "pbcopy"]

function copyToClipboard(text: string): boolean {
  for (const command of CLIPBOARD_TOOLS) {
    const bin = command.split(" ")[0]
    try {
      execSync(`command -v ${bin}`, { stdio: "ignore" })
      execSync(`printf '%s' '${text}' | ${command}`, { stdio: "ignore" })
      return true
    } catch {
      // clipboard tool not available; try the next one
    }
  }
  return false
}

// Server side: expose the exact session id to every shell opencode spawns, so
// the TUI supports a zero-LLM fallback:
//   !printf %s "$OPENCODE_SESSION" | xsel -b
const server: Plugin = async () => ({
  "shell.env": async (input, output) => {
    if (input.sessionID) {
      output.env.OPENCODE_SESSION = input.sessionID
    }
  },
})

// TUI side: register /copy-session (and a keybind) that runs onSelect
// deterministically in the TUI process - no agent, no LLM.
const tui: TuiPlugin = async (api) => {
  api.command.register(() => [
    {
      title: "Copy session id",
      value: "copy-session",
      description: "Copy the current session id to the clipboard",
      category: "Session",
      slash: { name: "copy-session" },
      keybind: "<leader>k",
      onSelect: () => {
        const route = api.route.current
        if (route.name !== "session") {
          api.ui.toast({
            title: "No active session",
            message: "Open a session first",
            variant: "warning",
          })
          return
        }
        const sessionID = (route.params as { sessionID: string }).sessionID
        if (copyToClipboard(sessionID)) {
          api.ui.toast({ title: "Session id copied", message: sessionID, variant: "success" })
        } else {
          api.ui.toast({
            title: "Copy failed",
            message: "No clipboard tool found (wl-copy, xsel, xclip, pbcopy)",
            variant: "error",
          })
        }
      },
    },
  ])
}

export default { id: "copy-session", server, tui }
