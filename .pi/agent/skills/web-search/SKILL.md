---
name: web-search
description: Web search and page content extraction via DuckDuckGo. No API key required. Use for searching documentation, facts, or any web content.
---

# Web Search

Search the web and extract page content using DuckDuckGo. No API key required.

## Setup

Install dependencies (run once):

```bash
cd {baseDir}
npm install
```

## Search

```bash
{baseDir}/search.js "query"               # Basic search (5 results)
{baseDir}/search.js "query" --count 10    # More results
```

## Extract Page Content

```bash
{baseDir}/fetch.js https://example.com    # Fetch and extract readable content
```
