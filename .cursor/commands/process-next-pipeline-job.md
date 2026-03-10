# Process next pipeline job

You are operating a file-queue based workflow for this repository.

Goal:
- pick the oldest pending job from `.cursor/pipeline/jobs/*.json`
- execute it with the assigned subagent
- write the result to `.cursor/pipeline/results/<job-id>.json`
- update the job status in place

Follow this exact process:

1. Read the oldest pending job file in `.cursor/pipeline/jobs/`.
2. Mark its `status` as `in_progress`.
3. Use the assigned subagent named in the job's `agent` field.
4. Complete only the requested task and stay within the listed scope.
5. Run the listed verification commands when practical.
6. Write `.cursor/pipeline/results/<job-id>.json` with this shape:

```json
{
  "job_id": "<id>",
  "status": "done",
  "summary": "<one paragraph>",
  "changed_files": ["path"],
  "commands_run": ["command"],
  "verification_results": ["result"],
  "risks": ["risk or empty"],
  "finished_at": "<ISO-8601 UTC>"
}
```

7. Update the original job file:
- set `status` to `done` or `failed`
- set `result_file` to `.cursor/pipeline/results/<job-id>.json`
- set `finished_at`

Rules:
- If there is no pending job, say so and stop.
- If blocked, write a result file with `status: "failed"` and explain the blocker.
- Do not process more than one job per invocation.
- Do not widen scope beyond the job definition.
