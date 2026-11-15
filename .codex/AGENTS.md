
## Screen readers and accessibility settings

Never enable screen readers, Orca, speech-dispatcher, accessibility speech, or desktop accessibility settings. Never set `ScreenReaderEnabled`, `screen-reader-enabled`, or `toolkit-accessibility` to true, even temporarily for testing. Never unmask speech services or remove the speech safeguards. This applies to every task, including Neovim textbox integration. Only a new, explicit user request to enable speech can override this rule.

**Heavy compute on this laptop:** prefer boxes.dev; before running anything CPU- or RAM-heavy locally, follow `~/.agents/skills/laptop-compute-caps/SKILL.md` (whole machine at or under 50% CPU and 70% RAM).
