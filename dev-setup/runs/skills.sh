#!/bin/bash

# Install AI agent skills collections globally via npx skills
# Skills install to ~/.agents/skills/ and are used by OpenCode and 40+ other AI agents

if ! command -v npx &>/dev/null; then
  echo "npx is required but not installed. Install Node.js first."
  exit 1
fi

npx skills add mattpocock/skills --global --all --yes
npx skills add charon-fan/agent-playbook --global --all --yes
npx skills add obra/superpowers --global --all --yes

# Symlink dotfiles' own skills (instead of npx skills add, which would
# produce non-fatal "does not support global skill installation" warnings
# for project-only agents like Eve and PromptScript)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for skill in "$SCRIPT_DIR"/.agents/skills/*/; do
  skill_name="$(basename "$skill")"
  [ "$skill_name" = "README.md" ] && continue  # skip the README
  ln -sfn "$skill" "$HOME/.agents/skills/$skill_name"
done
