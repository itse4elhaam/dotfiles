import { afterEach, beforeEach, describe, expect, test } from "bun:test"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import {
  bindingFilePath,
  parsePaneIdentity,
  recordPaneBinding,
} from "../.config/opencode/lib/continue-with-pane"
import ContinueWithPanePlugin from "../.config/opencode/plugins/continue-with-pane"

let testRoot = ""
let originalDataHome
let originalPaneIdentity

beforeEach(() => {
  testRoot = mkdtempSync(join(tmpdir(), "continue-with-pane-"))
  originalDataHome = process.env.XDG_DATA_HOME
  originalPaneIdentity = process.env.OPENCODE_PANE_IDENTITY
})

afterEach(() => {
  if (originalDataHome === undefined) delete process.env.XDG_DATA_HOME
  else process.env.XDG_DATA_HOME = originalDataHome
  if (originalPaneIdentity === undefined) delete process.env.OPENCODE_PANE_IDENTITY
  else process.env.OPENCODE_PANE_IDENTITY = originalPaneIdentity
  rmSync(testRoot, { recursive: true, force: true })
})

describe("parsePaneIdentity", () => {
  test("returns a pane identity when tmux reports session, window, and pane", () => {
    const result = parsePaneIdentity("peasy:2.3\n")

    expect(result).toBe("peasy:2.3")
  })

  test("rejects output that is not a complete tmux pane identity", () => {
    const result = parsePaneIdentity("peasy:2\n")

    expect(result).toBeNull()
  })
})

describe("recordPaneBinding", () => {
  test("persists the OpenCode session for the pane", () => {
    recordPaneBinding({
      dataHome: testRoot,
      pane: "peasy:2.3",
      sessionID: "ses_exact",
      now: new Date("2026-08-10T00:00:00Z"),
    })

    const stored = JSON.parse(readFileSync(bindingFilePath(testRoot, "peasy:2.3"), "utf8"))
    expect(stored).toEqual({
      pane: "peasy:2.3",
      sessionID: "ses_exact",
      updatedAt: "2026-08-10T00:00:00.000Z",
    })
  })

  test("keeps pane bindings isolated in separate files", () => {
    recordPaneBinding({
      dataHome: testRoot,
      pane: "peasy:2.3",
      sessionID: "ses_first",
      now: new Date("2026-08-10T00:00:00Z"),
    })
    recordPaneBinding({
      dataHome: testRoot,
      pane: "peasy:2.4",
      sessionID: "ses_second",
      now: new Date("2026-08-10T00:00:01Z"),
    })

    const first = JSON.parse(readFileSync(bindingFilePath(testRoot, "peasy:2.3"), "utf8"))
    const second = JSON.parse(readFileSync(bindingFilePath(testRoot, "peasy:2.4"), "utf8"))
    expect(first.sessionID).toBe("ses_first")
    expect(second.sessionID).toBe("ses_second")
  })
})

describe("ContinueWithPanePlugin", () => {
  test("records the session from a chat message for the launching pane", async () => {
    process.env.XDG_DATA_HOME = testRoot
    process.env.OPENCODE_PANE_IDENTITY = "peasy:2.3"
    const hooks = await ContinueWithPanePlugin({})
    const chatMessage = hooks["chat.message"]
    expect(chatMessage).toBeFunction()
    if (!chatMessage) return

    await chatMessage({ sessionID: "ses_from_hook" }, { message: {}, parts: [] })

    const stored = JSON.parse(readFileSync(bindingFilePath(testRoot, "peasy:2.3"), "utf8"))
    expect(stored.sessionID).toBe("ses_from_hook")
  })
})
