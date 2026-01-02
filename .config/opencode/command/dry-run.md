---
description: Exhaustively test code with positive, negative, and edge cases (mental dry-run)
agent: dry-run-tester
subtask: true
---

Perform exhaustive dry-run testing of the code in scope. Generate comprehensive test scenarios including positive paths, negative cases, edge conditions, and security tests. Mentally execute the code with each scenario and report all issues found.

Scope: $ARGUMENTS

Your analysis should include:
1. **Scope Understanding**: Functions analyzed, parameters, data flow, dependencies
2. **Test Case Generation**: 
   - Positive cases (happy path)
   - Negative cases (invalid inputs)
   - Edge cases (boundaries, empty inputs, special characters)
   - Security cases (injection, XSS, DoS)
3. **Dry-Run Execution**: Trace through code step-by-step for each test case
4. **Issue Reporting**: Detailed reports with severity, reproduction steps, and fixes
5. **Summary**: Test coverage metrics and recommendations

For each issue found, provide:
- Severity level (Critical/High/Medium/Low)
- Specific test case that triggers it
- Expected vs actual behavior
- Root cause analysis
- Fix recommendation with code
- Test case to prevent regression

Use the following MCP tools:
- **context7**: Look up testing best practices and security guidelines (OWASP)
- **gh_grep**: Find real-world test examples and edge case handling patterns

Report ALL issues found with specific, actionable recommendations.
