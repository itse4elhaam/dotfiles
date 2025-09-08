#!/bin/bash

# gemini-commit.sh - Generate a git commit message using Gemini API
# Usage: ./gemini-commit.sh [--stage] [--commit]

# Configuration
API_KEY="${GEMINI_API_KEY:-}"  # Set via env var: export GEMINI_API_KEY=your_key_here
if [ -z "$API_KEY" ]; then
  echo "Error: GEMINI_API_KEY environment variable is not set."
  echo "Run: export GEMINI_API_KEY=your_api_key_here"
  exit 1
fi

MODEL_NAME=gemini-2.5-flash-lite	

API_URL="https://generativelanguage.googleapis.com/v1beta/models/$MODEL_NAME:generateContent?key=$API_KEY"

# Flags
STAGE=0
AUTO_COMMIT=0

# Parse arguments
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --stage) STAGE=1; shift ;;
    --commit) AUTO_COMMIT=1; shift ;;
    *) echo "Unknown parameter passed: $1"; exit 1 ;;
  esac
done

# Stage changes if requested
if [ $STAGE -eq 1 ]; then
  echo "Staging changes..."
  git add .
fi

# Get the git diff
echo "Generating diff..."
DIFF=$(git diff --cached)
if [ -z "$DIFF" ]; then
  echo "No changes staged for commit."
  echo "Use --stage to stage unstaged changes, or make some changes first."
  exit 1
fi

# Create JSON payload for Gemini
PAYLOAD='{
  "contents": [{
    "parts": [{
      "text": "Analyze the following git diff and generate a short, conventional commit message (max 72 characters). Do not add quotes or formatting. Just the message.\n\nDiff:\n'"$DIFF"'\n\nCommit message:"
    }]
  }],
  "generationConfig": {
    "temperature": 0.2,
    "topP": 0.8,
    "topK": 20,
    "maxOutputTokens": 100
  }
}'

# Send request to Gemini
echo "Asking Gemini for a commit message..."
RESPONSE=$(curl -s -H 'Content-Type: application/json' \
  --data-binary "$PAYLOAD" \
  "$API_URL")

# Extract the generated text using jq
MESSAGE=$(echo "$RESPONSE" | jq -r '.candidates[0].content.parts[0].text' 2>/dev/null)

if [ $? -ne 0 ] || [ -z "$MESSAGE" ] || echo "$MESSAGE" | grep -q "error"; then
  echo "Failed to get a valid response from Gemini."
  echo "Response: $RESPONSE"
  exit 1
fi

# Trim whitespace
MESSAGE=$(echo "$MESSAGE" | xargs)

# Output the commit message
echo
echo "🎯 Suggested commit message:"
echo "$MESSAGE"
echo

# Optionally commit
if [ $AUTO_COMMIT -eq 1 ]; then
  echo "Committing with message: $MESSAGE"
  git commit -m "$MESSAGE"
fi

# Instructions for user
echo "To commit: git commit -m \"$MESSAGE\""
echo "Or run with --commit to auto-commit."
