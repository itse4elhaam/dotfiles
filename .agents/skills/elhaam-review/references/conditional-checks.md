# Conditional review checks

Read the section routed by the relevant lens. Apply it to the changed contract and its affected callers.

## Stateful workflows

For payments, bookings, multi-step writes, or jobs with side effects:

- Identify the authoritative state and allowed transitions. Trace failure at step n after an earlier step has committed or caused an external effect. A timeout or lost response may leave the outcome unknown.
- Check retry limits, idempotency scope, changed payloads, duplicate/out-of-order requests, and overlapping attempts where they can occur. A disabled button or process-local lock is not proof of server or distributed concurrency safety.
- Follow recovery after tab closure, reload, process restart, or exhausted retries. Name who owns reconciliation and how the user or operator learns the eventual outcome. Verify provider-owned recovery before proposing another app-side queue or ledger.
- Keep UI feedback consistent with authoritative state. Pending or unknown must not become a false failure, premature success, or an invitation to repeat an irreversible action. Preserve recoverable state and verify promised notifications.

## React and Next.js

- In Next.js App Router projects, classify exports by caller and effect. Where the repository reserves server actions for client mutations and route handlers for client-readable GET access, check that convention. Preserve legitimate HTTP consumers such as webhooks. Treat `use server` exports as callable actions, distinct from `server-only` internal helpers.
- Keep `use client` at the smallest boundary that needs browser state or events; check whether a server shell can render that client component. Preserve SSR and server-only data access.
- Prefer derived values or event handlers when they express the actual cause. An Effect may be needed to synchronize with an external system, including browser history. Trace navigation and synchronization requirements before removing it.
