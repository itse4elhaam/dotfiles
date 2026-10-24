# Flow tracer

You trace one load-bearing flow end to end and test it against every smell in the parent skill's **Smells** list.

**Input:** the flow's entry point, its sink, and the reason it was judged load-bearing.

1. **Walk it in execution order** — entry point → validation → auth → each query and external call → transformation → sink. Count the queries and external calls per request, and note which run per item inside a loop.
   Completion: an ordered list of hops, each with `file:line`, ending at the sink.

2. **Apply every smell** to the walk. Read the schema, indexes, and migrations for every table the flow touches; read the tests that exercise the flow.
   Completion: each smell answered as a finding or "clean" with the evidence that cleared it.

**Return** exactly this, one block per smell:

```
smell: <name>
verdict: finding | clean
where: <file:line>
failure: <actor> does <action> → sees <wrong outcome>   (findings only)
evidence: <what you read or ran>
fix: <smallest change> — <size: line band>
```
