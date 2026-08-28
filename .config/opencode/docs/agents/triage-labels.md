# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in the global issue tracker (`~/.scratch/`).

| Canonical role       | Label string used    | Meaning                                  |
| -------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`       | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`         | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`    | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`    | `ready-for-human`    | Requires human implementation            |
| `wontfix`            | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table, written as the `Status:` line in the issue file.

These are the default names; edit the right-hand column if you later adopt different vocabulary.
