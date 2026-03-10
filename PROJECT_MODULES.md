# Project Modules

This repository now treats the Cursor/OpenSpec workflow as a reusable project module.

## Source of truth

The source of truth is:

- [cursor-openspec-kit](D:/codex/project_modules/cursor-openspec-kit)

Installed copies in this repository are generated from that module:

- [.cursor](D:/codex/.cursor)
- [.codex/skills/cursor-subagent-orchestrator](D:/codex/.codex/skills/cursor-subagent-orchestrator)
- parts of [openspec](D:/codex/openspec)

## OpenSpec boundary

Only these OpenSpec paths are module-managed:

- [openspec/README.md](D:/codex/openspec/README.md)
- [openspec/templates](D:/codex/openspec/templates)
- base folder placeholders under [openspec/changes](D:/codex/openspec/changes) and [openspec/specs](D:/codex/openspec/specs)

These paths are project-owned business content and are not the module's source of truth:

- concrete change directories under [openspec/changes](D:/codex/openspec/changes)
- concrete spec content under [openspec/specs](D:/codex/openspec/specs)

Do not move real project changes back into the module. The module only defines the scaffold and templates.

## Update workflow

1. Edit the files under [cursor-openspec-kit](D:/codex/project_modules/cursor-openspec-kit).
2. Sync the module back into this repository:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync_cursor_openspec_kit.ps1
```

3. Re-test the affected workflow.

When syncing, treat OpenSpec templates and scaffold files as safe to overwrite, but review any unexpected diffs under project-owned change directories before committing.

## Install into another repository

```powershell
python D:\codex\scripts\install_project_module.py cursor-openspec-kit --target "D:\path\to\repo"
```

Use `--force` to overwrite existing files in the target repository.
