import type { Plugin } from "@opencode-ai/plugin"

const HANDOFF_AT_TOKENS = 250_000
const TOAST_DURATION_MS = 15_000

const warnedSessions = new Set<string>()

const promptTokens = (info: any): number => {
  const tokens = info.tokens
  return (
    (tokens?.input ?? 0) +
    (tokens?.cache?.read ?? 0) +
    (tokens?.cache?.write ?? 0)
  )
}

const formatTokens = (tokens: number): string => `${Math.round(tokens / 1_000)}k`

export const ContextHandoff: Plugin = async ({ client }) => ({
  event: async ({ event }) => {
    if (event.type === "session.compacted") {
      warnedSessions.delete(event.properties.sessionID)
      return
    }

    if (event.type === "session.deleted") {
      warnedSessions.delete(event.properties.info.id)
      return
    }

    if (event.type !== "message.updated") {
      return
    }

    const info = event.properties.info

    if (
      info.role !== "assistant" ||
      !info.time?.completed ||
      warnedSessions.has(info.sessionID)
    ) {
      return
    }

    const used = promptTokens(info)
    if (used < HANDOFF_AT_TOKENS) {
      return
    }

    warnedSessions.add(info.sessionID)

    await client.tui
      .showToast({
        body: {
          title: "Context handoff",
          message: `Context is ${formatTokens(used)}. Run /handoff and continue in a fresh session.`,
          variant: "warning",
          duration: TOAST_DURATION_MS,
        },
      })
      .catch(() => {})
  },
})
