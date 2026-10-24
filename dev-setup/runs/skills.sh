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

# Symlink personal skills from itse4elhaam/skills (instead of npx skills add,
# which would produce non-fatal "does not support global skill installation"
# warnings for project-only agents like Eve and PromptScript)
SKILLS_DIR="$HOME/workspace/coding/skills"
if [ ! -d "$SKILLS_DIR/.git" ]; then
  mkdir -p "$(dirname "$SKILLS_DIR")"
  git clone git@github.com:itse4elhaam/skills.git "$SKILLS_DIR"
fi
mkdir -p "$HOME/.agents/skills"
for skill in "$SKILLS_DIR"/*/; do
  skill_name="$(basename "$skill")"
  [ -f "$skill/SKILL.md" ] || continue  # skip non-skill dirs like assets/
  ln -sfn "${skill%/}" "$HOME/.agents/skills/$skill_name"
done
