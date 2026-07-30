/**
 * Exposes OpenCode session ID to external tools via pane-keyed temp files.
 *
 * Writes /tmp/opencode-session-<TMUX_PANE> on every tool execution so that
 * scripts can read the current session ID + directory. Each tmux pane gets
 * its own file, so forked sessions never collide.
 */

import type { Plugin } from "@opencode-ai/plugin"
import { writeFile, mkdir } from "fs/promises"

const SESSION_DIR = "/tmp"

function sessionFilePath(): string {
  const paneId = process.env.TMUX_PANE ?? "nopane"
  return `${SESSION_DIR}/opencode-session-${paneId}`
}

async function writeSessionContext(
  sessionId: string,
  directory: string,
): Promise<void> {
  const payload = JSON.stringify({
    sessionId,
    directory,
    timestamp: Date.now(),
  })

  try {
    await mkdir(SESSION_DIR, { recursive: true })
    await writeFile(sessionFilePath(), payload, { encoding: "utf-8" })
  } catch (_) {} /* prettier-ignore */
}

export const SessionExposePlugin: Plugin = async (ctx) => {
  const { directory } = ctx

  return {
    "tool.execute.before": async (input) => {
      const sid =
        typeof input.sessionID === "string" ? input.sessionID : ""
      if (sid) {
        await writeSessionContext(sid, directory)
      }
    },

    "tool.execute.after": async (input) => {
      const sid =
        typeof input.sessionID === "string" ? input.sessionID : ""
      if (sid) {
        await writeSessionContext(sid, directory)
      }
    },
  }
}

export default SessionExposePlugin
