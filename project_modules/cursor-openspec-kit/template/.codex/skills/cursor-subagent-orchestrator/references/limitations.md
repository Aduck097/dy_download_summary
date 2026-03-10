# Limitations

- This environment does not currently expose a stable headless `cursor-agent` executable that Codex can invoke directly.
- The installed `cursor` CLI opens the desktop application, but `cursor agent -p ...` does not behave like the documented headless agent entrypoint in the current setup.
- Project-level Cursor subagents still work through `.cursor/agents/*.md` and can be invoked from within Cursor.
- Use this skill to prepare delegation, scope the work, and define acceptance checks. Do not claim that Codex has programmatically executed a Cursor subagent unless there is direct command evidence.
