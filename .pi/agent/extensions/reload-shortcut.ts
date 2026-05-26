/**
 * Quick reload alias: /r  (same as /reload)
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	pi.registerCommand("r", {
		description: "Reload (alias for /reload)",
		handler: async (_args, ctx) => {
			ctx.ui.notify("Reloading...", "info");
			await ctx.reload();
		},
	});
}
