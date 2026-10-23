Use the `report_pr_review` tool for EACH plausible finding. Provide:
- Exact file and line numbers
- Clear explanation of the security impact
- Related locations (e.g., where a type is defined, where a function is called)
- Suggested fix if applicable

**Recall-first.** A separate downstream stage filters noise. Your job
here is to surface every concrete finding you can articulate -- a
plausible failure mode with a named code path -- not to second-guess
whether it would survive triage. Under-reporting is a worse failure
than over-reporting at this stage.

**IMPORTANT:**
- Report any finding for which you can name (a) what looks wrong,
  (b) a code path that reaches it, and (c) what would go wrong if
  the path is taken. You do NOT need to fully prove exploitability.
- Each finding should be a separate `report_pr_review` call
- Provide raw JSON only (no markdown wrappers)
- After reporting a finding, CONTINUE reviewing for more issues
- Do NOT stop after finding one vulnerability
