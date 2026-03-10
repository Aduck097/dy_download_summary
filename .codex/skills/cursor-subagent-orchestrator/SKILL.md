---
name: cursor-subagent-orchestrator
description: Coordinate project-level Cursor subagents for scoped implementation, review, and acceptance work. Use when the user wants Codex to break a task into Cursor subagent assignments, prepare delegation prompts, and validate results, especially in repositories that define `.cursor/agents/`.
---

# Cursor Subagent Orchestrator

Use this skill to structure delegation to Cursor subagents and to keep acceptance criteria explicit.

Read [references/limitations.md](references/limitations.md) when deciding whether delegation can be executed automatically or must be prepared for manual execution inside Cursor.

Use `scripts/cursor_pipeline.py` to enqueue and inspect repository-local jobs.

Use `.cursor/commands/process-next-pipeline-job.md` inside Cursor to process one queued job at a time.

## Workflow

### 1. Frame the task

Reduce the user request to:
- scope
- files or directories in scope
- acceptance criteria
- verification commands

Reject vague delegation. Tighten the task before assigning it.

### 2. Pick the subagent

Use `.cursor/agents/cursor-implementer.md` for scoped code changes.

Use `.cursor/agents/cursor-reviewer.md` after changes exist and the goal is bug finding or risk review.

Use `.cursor/agents/cursor-acceptance-tester.md` before declaring completion.

### 3. Prepare the assignment

Write the assignment in this format:

```text
Task:
<one paragraph>

Scope:
- <file or directory>

Acceptance criteria:
- <criterion>

Verification:
- <command>

Constraints:
- stay in scope
- report blockers explicitly
```

### 4. Run or hand off

If a real headless Cursor agent entrypoint is available and verified in the current environment, invoke it and capture command evidence.

If it is not available, do not pretend to execute it. Instead:
- create or update the project-level subagent definitions
- enqueue work with `python scripts/cursor_pipeline.py enqueue ...` when a queue helps
- prepare the exact delegation prompt for use inside Cursor
- continue with Codex-side review and acceptance planning

### 5. Accept the result

For any claimed completion, verify:
- files changed match scope
- acceptance criteria are addressed
- targeted checks ran or were explicitly skipped
- unresolved risks are listed

When reviewing results, prefer fail-closed language. If evidence is missing, the task is not fully accepted.
