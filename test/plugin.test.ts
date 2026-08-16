import { describe, it, expect, beforeEach, afterEach } from "vitest"
import {
  createTmuxPaneBindPlugin,
  buildPaneKey,
  getBindingStorePath,
  isPaneRestoreEnabled,
  isInTmux,
  rootSessionFromEvent,
} from "../.config/opencode/plugins/tmux-pane-bind"
import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync } from "fs"
import { join } from "path"
import { tmpdir } from "os"

describe("isPaneRestoreEnabled", () => {
  beforeEach(() => {
    delete process.env.OPENCODE_PANE_RESTORE
  })

  it("returns true when env is unset", () => {
    expect(isPaneRestoreEnabled()).toBe(true)
  })

  it("returns true when env is empty", () => {
    process.env.OPENCODE_PANE_RESTORE = ""
    expect(isPaneRestoreEnabled()).toBe(true)
  })

  it("returns true when env is 1", () => {
    process.env.OPENCODE_PANE_RESTORE = "1"
    expect(isPaneRestoreEnabled()).toBe(true)
  })

  it("returns true when env is true", () => {
    process.env.OPENCODE_PANE_RESTORE = "true"
    expect(isPaneRestoreEnabled()).toBe(true)
  })

  it("returns false when env is 0", () => {
    process.env.OPENCODE_PANE_RESTORE = "0"
    expect(isPaneRestoreEnabled()).toBe(false)
  })

  it("returns false when env is false", () => {
    process.env.OPENCODE_PANE_RESTORE = "false"
    expect(isPaneRestoreEnabled()).toBe(false)
  })

  it("returns true when env is yes", () => {
    process.env.OPENCODE_PANE_RESTORE = "yes"
    expect(isPaneRestoreEnabled()).toBe(true)
  })

  it("returns true when env is on", () => {
    process.env.OPENCODE_PANE_RESTORE = "on"
    expect(isPaneRestoreEnabled()).toBe(true)
  })

  it("returns true when env is enabled", () => {
    process.env.OPENCODE_PANE_RESTORE = "enabled"
    expect(isPaneRestoreEnabled()).toBe(true)
  })

  it("returns true for case-insensitive TRUE", () => {
    process.env.OPENCODE_PANE_RESTORE = "TRUE"
    expect(isPaneRestoreEnabled()).toBe(true)
  })

  it("returns false for case-insensitive FALSE", () => {
    process.env.OPENCODE_PANE_RESTORE = "FALSE"
    expect(isPaneRestoreEnabled()).toBe(false)
  })

  it("returns false for no", () => {
    process.env.OPENCODE_PANE_RESTORE = "no"
    expect(isPaneRestoreEnabled()).toBe(false)
  })

  it("returns false for off", () => {
    process.env.OPENCODE_PANE_RESTORE = "off"
    expect(isPaneRestoreEnabled()).toBe(false)
  })

  it("returns false for disabled", () => {
    process.env.OPENCODE_PANE_RESTORE = "disabled"
    expect(isPaneRestoreEnabled()).toBe(false)
  })

  it("returns false for random string", () => {
    process.env.OPENCODE_PANE_RESTORE = "garbage"
    expect(isPaneRestoreEnabled()).toBe(false)
  })
})

describe("isInTmux", () => {
  beforeEach(() => {
    delete process.env.TMUX_PANE
  })

  it("returns true when TMUX_PANE is set", () => {
    process.env.TMUX_PANE = "%1"
    expect(isInTmux()).toBe(true)
  })

  it("returns false when TMUX_PANE is unset", () => {
    expect(isInTmux()).toBe(false)
  })

  it("returns false when TMUX_PANE is empty", () => {
    process.env.TMUX_PANE = ""
    expect(isInTmux()).toBe(false)
  })
})

describe("buildPaneKey", () => {
  beforeEach(() => {
    delete process.env.tmux_session_name
    delete process.env.tmux_window_index
    delete process.env.tmux_pane_index
    delete process.env.pane_current_path
  })

  it("builds key from env vars", () => {
    process.env.tmux_session_name = "test-session"
    process.env.tmux_window_index = "1"
    process.env.tmux_pane_index = "2"
    process.env.pane_current_path = "/home/user/project"
    expect(buildPaneKey()).toBe("test-session:1.2|/home/user/project")
  })

  it("returns null when session is missing", () => {
    process.env.tmux_window_index = "1"
    process.env.tmux_pane_index = "1"
    process.env.pane_current_path = "/tmp"
    expect(buildPaneKey()).toBeNull()
  })

  it("returns null when window is missing", () => {
    process.env.tmux_session_name = "s"
    process.env.tmux_pane_index = "1"
    process.env.pane_current_path = "/tmp"
    expect(buildPaneKey()).toBeNull()
  })

  it("handles cwd with special characters", () => {
    process.env.tmux_session_name = "s"
    process.env.tmux_window_index = "1"
    process.env.tmux_pane_index = "1"
    process.env.pane_current_path = "/home/user/project (copy)"
    expect(buildPaneKey()).toBe("s:1.1|/home/user/project (copy)")
  })

  it("handles zero indices (tmux base-index 1 by default but 0 is valid)", () => {
    process.env.tmux_session_name = "test"
    process.env.tmux_window_index = "0"
    process.env.tmux_pane_index = "0"
    process.env.pane_current_path = "/tmp"
    expect(buildPaneKey()).toBe("test:0.0|/tmp")
  })

  it("returns null when pane index is missing", () => {
    process.env.tmux_session_name = "s"
    process.env.tmux_window_index = "1"
    process.env.pane_current_path = "/tmp"
    expect(buildPaneKey()).toBeNull()
  })

  it("returns null when cwd is missing", () => {
    process.env.tmux_session_name = "s"
    process.env.tmux_window_index = "1"
    process.env.tmux_pane_index = "1"
    expect(buildPaneKey()).toBeNull()
  })

  it("returns null when all env vars are missing", () => {
    expect(buildPaneKey()).toBeNull()
  })
})

describe("getBindingStorePath", () => {
  beforeEach(() => {
    delete process.env.XDG_DATA_HOME
  })

  it("uses XDG_DATA_HOME when set", () => {
    process.env.XDG_DATA_HOME = "/custom/data"
    const path = getBindingStorePath()
    expect(path).toBe("/custom/data/opencode/pane-bindings.json")
  })

  it("falls back to HOME/.local/share", () => {
    const path = getBindingStorePath()
    expect(path).toContain(".local/share/opencode/pane-bindings.json")
  })
})

describe("createTmuxPaneBindPlugin", () => {
  beforeEach(() => {
    delete process.env.TMUX_PANE
    delete process.env.OPENCODE_PANE_RESTORE
    delete process.env.tmux_session_name
    delete process.env.tmux_window_index
    delete process.env.tmux_pane_index
    delete process.env.pane_current_path
    delete process.env.XDG_DATA_HOME
  })

  afterEach(() => {
    const testDir = join(tmpdir(), "tmux-pane-bind-test")
    try { rmSync(testDir, { recursive: true, force: true }) } catch {}
  })

  it("returns empty hooks when feature flag is disabled", async () => {
    process.env.TMUX_PANE = "%1"
    process.env.OPENCODE_PANE_RESTORE = "0"
    const hooks = await createTmuxPaneBindPlugin({ directory: "/tmp" })
    expect(hooks).toEqual({})
  })

  it("returns empty hooks when not in tmux", async () => {
    const hooks = await createTmuxPaneBindPlugin({ directory: "/tmp" })
    expect(hooks).toEqual({})
  })

  it("returns chat.message hook when enabled and in tmux", async () => {
    process.env.TMUX_PANE = "%1"
    const hooks: any = await createTmuxPaneBindPlugin({ directory: "/tmp" })
    expect(hooks).toHaveProperty("chat.message")
    expect(typeof hooks["chat.message"]).toBe("function")
  })

  it("does not write binding on initialization (only on chat.message)", async () => {
    const testDir = join(tmpdir(), "tmux-pane-bind-test")
    process.env.TMUX_PANE = "%1"
    process.env.tmux_session_name = "init-test"
    process.env.tmux_window_index = "2"
    process.env.tmux_pane_index = "3"
    process.env.pane_current_path = "/home/user"
    process.env.XDG_DATA_HOME = testDir
    process.env.HOME = testDir

    await createTmuxPaneBindPlugin({ directory: "/tmp" })

    const storePath = join(testDir, "opencode", "pane-bindings.json")
    expect(existsSync(storePath)).toBe(false)
  })

  it("writes binding on chat.message with sessionID", async () => {
    const testDir = join(tmpdir(), "tmux-pane-bind-test")
    process.env.TMUX_PANE = "%1"
    process.env.tmux_session_name = "test-session"
    process.env.tmux_window_index = "1"
    process.env.tmux_pane_index = "1"
    process.env.pane_current_path = "/home/user/project"
    process.env.XDG_DATA_HOME = testDir
    process.env.HOME = testDir

    const hooks: any = await createTmuxPaneBindPlugin({ directory: "/tmp" })
    await hooks["chat.message"]({ sessionID: "ses_new_route" })

    const storePath = join(testDir, "opencode", "pane-bindings.json")
    const content = JSON.parse(readFileSync(storePath, "utf-8"))
    expect(content["test-session:1.1|/home/user/project"].sessionID).toBe("ses_new_route")
  })

  it("does not write binding when chat.message is called without sessionID", async () => {
    const testDir = join(tmpdir(), "tmux-pane-bind-test")
    process.env.TMUX_PANE = "%1"
    process.env.tmux_session_name = "guard-test"
    process.env.tmux_window_index = "1"
    process.env.tmux_pane_index = "1"
    process.env.pane_current_path = "/tmp"
    process.env.XDG_DATA_HOME = testDir
    process.env.HOME = testDir

    const hooks: any = await createTmuxPaneBindPlugin({ directory: "/tmp" })
    await hooks["chat.message"]({})

    const storePath = join(testDir, "opencode", "pane-bindings.json")
    expect(existsSync(storePath)).toBe(false)
  })

  it("handles corrupt store gracefully on chat.message", async () => {
    const testDir = join(tmpdir(), "tmux-pane-bind-test")
    const storePath = join(testDir, "opencode", "pane-bindings.json")
    mkdirSync(join(testDir, "opencode"), { recursive: true })
    writeFileSync(storePath, "not valid json{{{", "utf-8")

    process.env.TMUX_PANE = "%1"
    process.env.tmux_session_name = "crash-test"
    process.env.tmux_window_index = "1"
    process.env.tmux_pane_index = "1"
    process.env.pane_current_path = "/tmp"
    process.env.XDG_DATA_HOME = testDir
    process.env.HOME = testDir

    const hooks: any = await createTmuxPaneBindPlugin({ directory: "/tmp" })
    await hooks["chat.message"]({ sessionID: "ses_recovery" })

    const content = JSON.parse(readFileSync(storePath, "utf-8"))
    expect(content["crash-test:1.1|/tmp"].sessionID).toBe("ses_recovery")
  })
})


describe("rootSessionFromEvent", () => {
  it("captures a newly created root session", () => {
    const event = {
      type: "session.created",
      properties: { info: { id: "ses_new", directory: "/repo" } },
    }
    expect(rootSessionFromEvent(event, "/repo")).toBe("ses_new")
  })

  it("captures an updated root session", () => {
    const event = {
      type: "session.updated",
      properties: { info: { id: "ses_existing", directory: "/repo" } },
    }
    expect(rootSessionFromEvent(event, "/repo")).toBe("ses_existing")
  })

  it("ignores child sessions", () => {
    const event = {
      type: "session.created",
      properties: { info: { id: "ses_child", parentID: "ses_root", directory: "/repo" } },
    }
    expect(rootSessionFromEvent(event, "/repo")).toBeNull()
  })

  it("ignores sessions from another directory", () => {
    const event = {
      type: "session.updated",
      properties: { info: { id: "ses_other", directory: "/other" } },
    }
    expect(rootSessionFromEvent(event, "/repo")).toBeNull()
  })
})
