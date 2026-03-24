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
