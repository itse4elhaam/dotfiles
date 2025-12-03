#!/bin/bash
set -euo pipefail

# Cursor CLI Plugin Installation Script for OpenCode
# This script sets up the Cursor CLI plugin for OpenCode with symlink support

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_source="${script_dir}/cursor-cli.ts"
global_plugin_dir="${HOME}/.config/opencode/plugin"
global_plugin_link="${global_plugin_dir}/cursor-cli.ts"

echo "🚀 Cursor CLI Plugin Installation for OpenCode"
echo "================================================"
echo ""

# Check if cursor-agent is installed
if ! command -v cursor-agent &> /dev/null; then
    echo "❌ cursor-agent CLI not found"
    echo ""
    echo "Install Cursor CLI with:"
    echo "  curl https://cursor.com/install -fsS | bash"
    echo ""
    exit 1
fi

echo "✓ cursor-agent found: $(which cursor-agent)"
echo "✓ Version: $(cursor-agent --version 2>&1 || echo 'unknown')"
echo ""

# Check authentication
if [ -n "${CURSOR_API_KEY:-}" ]; then
    echo "✓ CURSOR_API_KEY is set"
else
    echo "⚠️  CURSOR_API_KEY not set"
    echo ""
    echo "To authenticate:"
    echo "  1. Run 'cursor-agent' for interactive login, OR"
    echo "  2. Get API key from https://cursor.com/settings"
    echo "  3. Set in your shell profile:"
    echo "     export CURSOR_API_KEY=your_key_here"
    echo ""
    echo "Continuing installation..."
fi

echo ""
echo "📦 Installing plugin..."

# Check if plugin source exists
if [ ! -f "$plugin_source" ]; then
    echo "❌ Plugin source not found: $plugin_source"
    exit 1
fi

# Create global plugin directory
mkdir -p "$global_plugin_dir"

# Create symlink
if [ -L "$global_plugin_link" ]; then
    echo "⚠️  Symlink already exists: $global_plugin_link"
    echo "   Removing old symlink..."
    rm "$global_plugin_link"
fi

if [ -f "$global_plugin_link" ]; then
    echo "❌ File exists at symlink location: $global_plugin_link"
    echo "   Please remove it manually and run this script again"
    exit 1
fi

ln -s "$plugin_source" "$global_plugin_link"

echo "✓ Created symlink: $global_plugin_link → $plugin_source"
echo ""

echo "📋 Installation Summary"
echo "======================="
echo "Plugin location:    $plugin_source"
echo "Global symlink:     $global_plugin_link"
echo "Error log location: .opencode/cursor-errors.log"
echo ""

echo "✅ Installation complete!"
echo ""
echo "🎯 Available Tools in OpenCode:"
echo "  • cursor_chat       - Chat with Cursor AI (streaming)"
echo "  • cursor_models     - List available models"
echo "  • cursor_agent      - Run agent tasks with file modifications"
echo ""
echo "💡 Usage Examples:"
echo "  - In OpenCode TUI, use: 'Use cursor_chat to explain this code'"
echo "  - Check models: 'Use cursor_models to list available models'"
echo "  - Refactor code: 'Use cursor_agent to refactor this file'"
echo ""
echo "📖 See README-cursor-plugin.md for complete documentation"
