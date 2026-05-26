/**
 * readability-enhancer — Improves pi output readability
 *
 * What this does:
 *   - Adds a colored border around the editor with model/context status
 *   - Customizes hidden thinking label with distinct visual style
 *   - Highlights tool boundaries for better visual scanning
 *
 * Commands:
 *   /readability      Toggle readability enhancements on/off
 *
 * Install: place in ~/.pi/agent/extensions/readability-enhancer.ts and run /reload
 */

import {
	CustomEditor,
	type ExtensionAPI,
	type ExtensionContext,
	type KeybindingsManager,
} from "@earendil-works/pi-coding-agent";
import type { Component, EditorTheme, TUI } from "@earendil-works/pi-tui";
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";

// ── helper: render a styled border line ──
function fitBorder(
	left: string,
	right: string,
	width: number,
	border: (text: string) => string,
	fill: (text: string) => string = border,
): string {
	if (width <= 0) return "";
	if (width === 1) return border("─");

	let leftText = left;
	let rightText = right;
	const fixedWidth = 2;
	const minimumGap = 3;

	while (
		fixedWidth + visibleWidth(leftText) + visibleWidth(rightText) + minimumGap > width &&
		visibleWidth(rightText) > 0
	) {
		rightText = truncateToWidth(rightText, Math.max(0, visibleWidth(rightText) - 1), "");
	}
	while (
		fixedWidth + visibleWidth(leftText) + visibleWidth(rightText) + minimumGap > width &&
		visibleWidth(leftText) > 0
	) {
		leftText = truncateToWidth(leftText, Math.max(0, visibleWidth(leftText) - 1), "");
	}

	const gapWidth = Math.max(0, width - fixedWidth - visibleWidth(leftText) - visibleWidth(rightText));
	return `${border("─")}${leftText}${fill("─".repeat(gapWidth))}${rightText}${border("─")}`;
}

function formatCwd(cwd: string): string {
	const home = process.env.HOME;
	if (home && cwd.startsWith(home)) {
		return `~${cwd.slice(home.length)}`;
	}
	return cwd;
}

function formatContext(ctx: ExtensionContext): string {
	const usage = ctx.getContextUsage();
	const contextWindow = usage?.contextWindow ?? ctx.model?.contextWindow;
	if (!contextWindow || !usage || usage.percent === null) {
		return "ctx ?";
	}
	return `ctx ${Math.round(usage.percent)}%/${(contextWindow / 1000).toFixed(0)}k`;
}

function formatThinking(level: string): string {
	const labels: Record<string, string> = {
		off: "off",
		minimal: "min",
		low: "low",
		medium: "med",
		high: "high",
		xhigh: "xhi",
	};
	return labels[level] ?? level;
}

// Empty footer so the custom editor border replaces it cleanly
class EmptyFooter implements Component {
	render(): string[] {
		return [];
	}
	invalidate(): void {}
}

export default function (pi: ExtensionAPI) {
	let isWorking = false;
	let spinnerIndex = 0;
	let spinnerTimer: ReturnType<typeof setInterval> | undefined;
	let activeTui: TUI | undefined;
	let enabled = true;
	const spinnerFrames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

	const stopSpinner = () => {
		if (spinnerTimer) {
			clearInterval(spinnerTimer);
			spinnerTimer = undefined;
		}
	};

	pi.on("agent_start", () => {
		isWorking = true;
		stopSpinner();
		spinnerTimer = setInterval(() => {
			spinnerIndex = (spinnerIndex + 1) % spinnerFrames.length;
			activeTui?.requestRender();
		}, 80);
		activeTui?.requestRender();
	});

	pi.on("agent_end", () => {
		isWorking = false;
		stopSpinner();
		activeTui?.requestRender();
	});

	pi.on("session_shutdown", () => {
		stopSpinner();
		activeTui = undefined;
	});

	// ── Toggle command ──
	pi.registerCommand("readability", {
		description: "Toggle readability enhancements on/off",
		handler: async (_args, ctx) => {
			enabled = !enabled;
			ctx.ui.notify(`Readability ${enabled ? "ON" : "OFF"}`, "info");
			activeTui?.requestRender();
		},
	});

	pi.on("session_start", (_event, ctx) => {
		ctx.ui.setWorkingVisible(false);
		ctx.ui.setFooter(() => new EmptyFooter());

		// ── Custom hidden thinking label ──
		ctx.ui.setHiddenThinkingLabel("💭");

		let branch: string | undefined;

		const refreshBranch = async () => {
			const result = await pi
				.exec("git", ["branch", "--show-current"], { cwd: ctx.cwd })
				.catch(() => undefined);
			const stdout = result?.stdout.trim();
			branch = stdout && stdout.length > 0 ? stdout : undefined;
			activeTui?.requestRender();
		};
		void refreshBranch();

		// ── Custom editor with status border ──
		class ReadabilityEditor extends CustomEditor {
			constructor(tui: TUI, theme: EditorTheme, keybindings: KeybindingsManager) {
				super(tui, theme, keybindings, { paddingX: 0 });
				activeTui = tui;
			}

			render(width: number): string[] {
				const lines = super.render(width);
				if (lines.length < 2 || !enabled) return lines;

				const thm = ctx.ui.theme;

				// ── Top border: spinner + model info ──
				const model = ctx.model
					? `${ctx.model.provider}/${ctx.model.id}`
					: "no model";
				const thinking = pi.getThinkingLevel();
				const topLeft = isWorking
					? thm.fg("accent", ` ${spinnerFrames[spinnerIndex]} `)
					: thm.fg("muted", " ● ");
				const topRight = thm.fg(
					"muted",
					` ${model} ⋮ ${formatThinking(thinking)} `,
				);
				const borderColor = (text: string) => {
					if (isWorking) return thm.fg("accent", text);
					return thm.fg("borderAccent", text);
				};

				// ── Bottom border: context + cwd + branch ──
				const bottomLeft = thm.fg(
					"muted",
					` ${formatContext(ctx)} `,
				);
				const bottomRight = thm.fg(
					"muted",
					` ${formatCwd(ctx.cwd)}${branch ? ` (${branch})` : ""} `,
				);
				const borderDim = (text: string) => thm.fg("borderMuted", text);

				lines[0] = fitBorder(topLeft, topRight, width, borderColor);
				lines[lines.length - 1] = fitBorder(bottomLeft, bottomRight, width, borderDim);
				return lines;
			}
		}

		ctx.ui.setEditorComponent(
			(tui, theme, keybindings) => new ReadabilityEditor(tui, theme, keybindings),
		);
	});
}
