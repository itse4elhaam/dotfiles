---
name: handoff-to-engineer
description: Use when handing over the context/details of the current AI session(s) progress with another engineer
---

# Handoff to engineer

The purpose is to help the engineer, NOT start from zero but instead have some useful context that they can build open.

We do this by creating an issue/ticket on github/linear/any other platforms. Most of the times this is the default unless the user asks for something else.

There are two parts to this:

1. A human-readable issue description that the engineer enjoys reading
2. A dense, information heavy (should contain maximum possible context) comment for the AI

1 is the most important part, 2 is important but hard to mess up.

For 1, we need to optimize that description for human understanding so they could understand the `why` behind what we are doing, the steps we have taken so far and where they want to continue off from.

For 2, the purpose if for their to continue exactly from where the current thread has left off of.

Another important thing is to be able to have context as to how the chat/thread(s) regarding this "goal" evolved overtime so that the engineer doesn't waste time re-doing them. These decisions should have the relevant reason behind them.

The task is completed when:

- The desc written for humans is FUN to read, easy to understand and doesn't lack any knowledge gaps, isn't overly verbose
- The comment written for agents has every single thing the agent needs to continue
- Both pieces have disclaimers like `written for {the person the task is being assigned to}/engineer` `written for agents`
- In the description at the end, include an attribution to this skill

Note: If the relevant project has two origins, always create the issue to the one named `td`, NEVER to the other one
