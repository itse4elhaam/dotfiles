import { execFileSync } from "node:child_process"
import { createHash, randomUUID } from "node:crypto"
import { mkdirSync, renameSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { z } from "zod"

const PaneIdentitySchema = z.string().regex(/^[^:\r\n]+:\d+\.\d+$/).brand<"PaneIdentity">()
const SessionIdSchema = z.string().min(1).brand<"SessionID">()

export type PaneIdentity = z.infer<typeof PaneIdentitySchema>
export type SessionID = z.infer<typeof SessionIdSchema>

type RecordPaneBindingInput = {
  readonly dataHome: string
  readonly pane: PaneIdentity
  readonly sessionID: SessionID
  readonly now: Date
}

export const parsePaneIdentity = (value: string): PaneIdentity | null => {
  const result = PaneIdentitySchema.safeParse(value.trim())
  return result.success ? result.data : null
}

export const parseSessionID = (value: unknown): SessionID | null => {
  const result = SessionIdSchema.safeParse(value)
  return result.success ? result.data : null
}

export const bindingFilePath = (dataHome: string, pane: PaneIdentity): string => {
  const digest = createHash("sha256").update(pane).digest("hex")
  return join(dataHome, "opencode", "pane-sessions", `${digest}.json`)
}

export const opencodeDataHome = (): string => {
  return process.env["XDG_DATA_HOME"] ?? join(process.env["HOME"] ?? tmpdir(), ".local", "share")
}

export const currentPaneIdentity = (): PaneIdentity | null => {
  const override = process.env["OPENCODE_PANE_IDENTITY"]
  if (override) {
    return parsePaneIdentity(override)
  }

  const paneID = process.env["TMUX_PANE"]
  if (!paneID) {
    return null
  }

  try {
    const output = execFileSync(
      "tmux",
      ["display-message", "-p", "-t", paneID, "#{session_name}:#{window_index}.#{pane_index}"],
      { encoding: "utf8" },
    )
    return parsePaneIdentity(output)
  } catch (error) {
    if (error instanceof Error) {
      return null
    }
    throw error
  }
}

export const recordPaneBinding = (input: RecordPaneBindingInput): void => {
  const target = bindingFilePath(input.dataHome, input.pane)
  const directory = dirname(target)
  const temporary = join(directory, `.${randomUUID()}.tmp`)
  const binding = {
    pane: input.pane,
    sessionID: input.sessionID,
    updatedAt: input.now.toISOString(),
  } as const

  mkdirSync(directory, { recursive: true, mode: 0o700 })
  try {
    writeFileSync(temporary, `${JSON.stringify(binding, null, 2)}\n`, { encoding: "utf8", mode: 0o600 })
    renameSync(temporary, target)
  } catch (error) {
    rmSync(temporary, { force: true })
    throw error
  }
}
