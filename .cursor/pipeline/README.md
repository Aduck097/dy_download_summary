# Cursor Pipeline

Repository-local queue for Cursor subagent work.

## Enqueue a job

```powershell
python scripts/cursor_pipeline.py enqueue `
  --agent cursor-implementer `
  --title "Implement task" `
  --task "Describe the task"
```

## Process a job in Cursor

Run the project command:

`/process-next-pipeline-job`

## Inspect results

```powershell
python scripts/cursor_pipeline.py list
python scripts/cursor_pipeline.py result <job-id>
```
