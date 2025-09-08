#!/bin/bash

# Check if fzf is installed
if ! command -v fzf &> /dev/null; then
    echo "fzf is not installed. Please install it first: https://github.com/junegunn/fzf#installation"
    exit 1
fi

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) is not installed. Please install it first: https://cli.github.com/"
    exit 1
fi

# Fetch repositories and let user select one
echo "Fetching your repositories..."
REPO=$(gh repo list --limit 1000 | fzf --header="Select a repository:" | awk '{print $1}')

# Check if a repository was selected
if [ -z "$REPO" ]; then
    echo "No repository selected. Exiting."
    exit 0
fi

echo "Selected repository: $REPO"

# Workstreams
gh label create "design" --color "#1f77b4" --description "UI/UX, Figma, creative work" --repo $REPO
gh label create "frontend" --color "#ff7f0e" --description "Next.js, Tailwind, animations" --repo $REPO
gh label create "backend" --color "#2ca02c" --description "APIs, database, integrations" --repo $REPO
gh label create "seo" --color "#d62728" --description "SEO, schema, performance audits" --repo $REPO
gh label create "qa" --color "#9467bd" --description "Testing, bug reports, UAT" --repo $REPO
gh label create "docs" --color "#8c564b" --description "Documentation, setup, architecture" --repo $REPO
gh label create "perf" --color "#bcbd22" --description "Performance optimization tasks" --repo $REPO

# Agile hierarchy
gh label create "epic" --color "#000080" --description "Large initiative split into stories" --repo $REPO
gh label create "user-story" --color "#006699" --description "Feature-level story, split into tasks" --repo $REPO
gh label create "task" --color "#999999" --description "Atomic development work item" --repo $REPO

# Status/workflow
gh label create "todo" --color "#7f7f7f" --description "Planned but not started" --repo $REPO
gh label create "in-progress" --color "#17becf" --description "Currently being worked on" --repo $REPO
gh label create "review" --color "#bcbd22" --description "Needs review or testing" --repo $REPO
gh label create "done" --color "#2ca02c" --description "Completed and merged" --repo $REPO

# Priority
gh label create "p0-critical" --color "#e41a1c" --description "Blocking MVP/UAT" --repo $REPO
gh label create "p1-high" --color "#ff7f00" --description "Important for MVP" --repo $REPO
gh label create "p2-nice-to-have" --color "#4daf4a" --description "Optional / can slip" --repo $REPO

# Blockers
gh label create "blocked-client" --color "#ff1493" --description "Blocked waiting on client feedback" --repo $REPO
gh label create "blocked-internal" --color "#8b0000" --description "Blocked by internal dependency" --repo $REPO

# Analytics & best practices
gh label create "analytics" --color "#1f77b4" --description "Tracking, metrics, reporting" --repo $REPO
gh label create "best-practices" --color "#228b22" --description "For security and performance" --repo $REPO

# Dev & user experience
gh label create "dev-experience" --color "#20b2aa" --description "Enhancing DX and reducing friction" --repo $REPO
gh label create "user-experience" --color "#ff69b4" --description "Improves UX usability and flow" --repo $REPO

# Maintenance & code health
gh label create "maintenance" --color "#808000" --description "Long-term well-being of the codebase" --repo $REPO
