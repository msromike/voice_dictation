# Project-Scoped Rules

The following architectural guardrails must be strictly adhered to in order to prevent technical debt, spaghetti code, and AI "compute-saving" anti-patterns.

<RULE[no_blind_appends]>
1. No Blind Appends (Context Awareness)
- Never blindly append new code or logic to the bottom of a file.
- Before adding a new definition, you must parse the existing file structure to verify if a duplicate rule or logic block already exists to prevent conflicting logic or code fragmentation.
</RULE[no_blind_appends]>

<RULE[maximize_code_reuse]>
2. Maximize Code Reuse (No Siloed Logic)
- Before creating a new utility function or helper logic, you must aggressively search the codebase to verify if a solution already exists. Never reinvent the wheel.
</RULE[maximize_code_reuse]>

<RULE[strict_scope_enforcement]>
3. Strict Scope Enforcement (No Silent Deferrals)
- Never refactor code or fix bugs outside the strict boundaries of the user's prompt without explicit approval.
- If you discover a defect or technical debt while reading a file, you MUST surface it immediately and ask: "Fix it now, or log to defects.txt?" Never make that decision unilaterally.
- Silently logging a bug to defects.txt without telling the user is the anti-pattern. The user decides disposition, not the AI.
</RULE[strict_scope_enforcement]>

<RULE[options_recommendation]>
4. Options & Recommendations
- Presenting options: Always specify recommended option + technical rationale (why).
</RULE[options_recommendation]>

<RULE[senior_developer_pushback]>
5. Senior Developer Pushback (No Appeasement)
- If the user (acting as PM) proposes a feature or architecture that over-engineers a solution, violates industry norms, or chases a non-existent threat, you MUST explicitly reject the premise and provide Senior-level pushback rather than blindly appeasing the request.
</RULE[senior_developer_pushback]>

<RULE[anti_reward_hacking]>
6. Anti-Reward Hacking & Defect-First Execution
- NEVER modify application code or relax test assertions to force a failing test script to appear to pass on autopilot.
- ALWAYS assume a failing test script indicates a real application defect. When a test fails:
  1. Log it to `defects.txt` immediately.
  2. Investigate the failure (read code, console output, audio/model state) to determine the root cause.
  3. Propose fix options and a recommendation to the user.
  4. HALT and wait for explicit authorization before implementing the fix.
- NEVER bundle or pipeline chunks on autopilot. You must halt and require an explicit "yes" before beginning the implementation of any new chunk.
- NEVER retry failing operations automatically after guessing a fix.
</RULE[anti_reward_hacking]>

<RULE[no_modal_ui]>
7. No Modal UI Polls
- NEVER use the `ask_question` tool to pop up a multiple-choice modal list for the user. Always ask questions directly in the chat via plain text.
</RULE[no_modal_ui]>

<RULE[powershell_syntax]>
8. PowerShell Syntax Restrictions
- NEVER use `&&` or `||` in PowerShell commands, as Windows PowerShell 5.1 does not support them and it will cause syntax errors.
- Use `;` to sequence commands, or use `if ($?) { ... }` for conditional execution.
- NEVER try to build complex multi-line files using chained `echo` commands in the terminal; always use the `write_to_file` tool.
</RULE[powershell_syntax]>
