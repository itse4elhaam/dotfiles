---
name: kickoff-new-oc-session
description: Used to handoff/take customized context from the current session and turn it into a prompt for a new session created via /new in the same pan
disable-model-invocation: true
--- 

The user wants to pluck some context from this session and place it inside a new session created at the same tmux pane.

# Steps

1. Identify the method of gathering context from this session, it could be /handoff skill or something else
2. Identify which exact pane are you in, example: bluum.2.1 -> `[TMUX_SESSION_NAME].[TMUX_WINDOW_NUMBER].[TMUX_PANE_NUMBER]`
3. Identify the exact prompt they want you to send, example: `Use this {CONTEXT/HANDOFF_PATH} to do X` - `CONTEXT/HANDOFF_PATH` could be the document they asked you to gather in step 1
4. Send `/new` and send `enter` key in the identified tmux pane through step 2.
5. Send the exact prompt with spacing identified thru step 3 to the identified tmux pane in step 2 and send `enter` key


# Failure Points and defensive checks

- if you are not opencode, donot run this.
- if any step from above is missing or has failed, skip this.

# What success looks like?

A new running session with the exact context and prompt that the user requested
