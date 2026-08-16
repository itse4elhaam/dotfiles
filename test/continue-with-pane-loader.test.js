import { expect, test } from "bun:test"
import * as pluginModule from "../.config/opencode/plugins/continue-with-pane"

test("every exported plugin candidate initializes with OpenCode's loader input", async () => {
  delete process.env.OPENCODE_PANE_IDENTITY
  delete process.env.TMUX_PANE

  for (const candidate of Object.values(pluginModule)) {
    if (typeof candidate === "function") {
      await expect(candidate({})).resolves.toBeDefined()
    }
  }
})
