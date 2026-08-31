---
name: handoff-to-new-session
description: Transfer selected context into a new OpenCode session in the current tmux pane
disable-model-invocation: true
---

The user wants to transfer selected context from this session into a new session created in the same tmux pane.

# Steps

1. Gather the context requested by the user with `/handoff` or the method they specified. Complete this step only when the context exists and you can name its exact path or literal contents.
2. Read `$TMUX_PANE` and confirm that it resolves to the pane running OpenCode. Use that pane ID as the target; if a human-readable target is needed, tmux formats it as `[TMUX_SESSION_NAME]:[TMUX_WINDOW_NUMBER].[TMUX_PANE_NUMBER]`, for example `bluum:2.1`. Complete this step only when tmux resolves the target successfully.
3. Construct the exact prompt the user wants submitted, for example `Use this {CONTEXT/HANDOFF_PATH} to do X`. Preserve the prompt in a temporary file so spaces, newlines, and shell characters remain literal. Complete this step only when the stored prompt exactly matches the requested text.
4. Send `/new` and the `Enter` key to the pane from step 2. Capture the pane before and after the command, and wait until the new session view is visible and ready for input. Stop if readiness cannot be confirmed within a bounded timeout.
5. Load the prompt file from step 3 into a named tmux buffer, paste that buffer into the pane from step 2, and send the `Enter` key. Capture the pane again and complete this step only when the new session shows that it received the prompt.


# Failure Points and defensive checks

- Run this only when the current pane is running OpenCode inside tmux.
- If any prerequisite, command, readiness check, or final verification fails, stop immediately and report the failed condition. Do not submit a partial or reconstructed prompt.

# What success looks like?

A new running OpenCode session in the original tmux pane that visibly received the exact context and prompt requested by the user.
