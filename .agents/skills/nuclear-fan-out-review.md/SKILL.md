---
name: pr-review-dossier
description: A fan-out review using the @oracle subagent along all frontiers supported by the workspace and the codebase
---

If you are in an existing session with context about the codebase and current features, ignore the following advice otherwise, launch maximum @explore subagents and gain context.

###### (1)
After this launch an @oracle agent with the mission of finding the codebase standards, this find should NOT stop at generic AGENTS.md files. It should explore patterns across core modules, look for documentation on coding standards/styles and look for linting rules. The result should be a a set of rules (in skill format), and if no supporting skill/command exists already - suggest the consumer to create one. This will be named as `codebase-review`

Once you have the context, launch atleast 3 @oracle agents but the exact number depends on the codebase, let me explain.

- One @oracle agent for ~/.agents/skills/code-review
- One @oracle agent for ~/.agents/skills/elhaam-review
- One @oracle agent for (1)

---


Final pass @oracle agent before releasing these changes in a document format to ensure the severity of a finding is not overstated, the issues are not just theoretical but real user-impacting and not overengineered.

After alignement with this, proceed to the next step:

---

In the end create a single ~/.agents/skills/readable-html-dossier file with the findings, ensure the document contains enough context for the user to make informed decisions and the document is written in an engaging and precise manner.
