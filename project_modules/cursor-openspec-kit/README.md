# Cursor OpenSpec Kit

Reusable project module for:

- `.cursor/agents/` subagents
- `.cursor/commands/` pipeline command
- `.cursor/pipeline/` queue folders and config
- `.codex/skills/cursor-subagent-orchestrator/`
- `openspec/` base folders and change templates

OpenSpec scope in this module is intentionally limited to scaffold and templates:

- `openspec/README.md`
- `openspec/templates/`
- placeholder directories for `openspec/changes/` and `openspec/specs/`

It is not the source of truth for project-specific change content under `openspec/changes/<change-name>/`.

Install into another repository with:

```powershell
python D:\codex\scripts\install_project_module.py cursor-openspec-kit --target "D:\path\to\repo"
```

Use `--force` to overwrite existing files.
