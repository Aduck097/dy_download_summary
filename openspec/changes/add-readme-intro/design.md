## Context

The repository has OpenSpec initialized but no top-level onboarding document yet. The change is documentation-only, so the design can stay simple and focus on where the README content should live and what it should cover.

## Goals / Non-Goals

**Goals:**
- Add a short README introduction that explains what this repository is for.
- Give first-time users one or two clear next steps.
- Keep the README structure easy to extend later.

**Non-Goals:**
- Full project documentation
- API reference material
- Build or deployment guides

## Decisions

- Put the introduction at the top of `README.md` so it is visible immediately on repository open.
- Keep the initial content to three parts: purpose, structure summary, and quick-start next steps.
- Avoid tool-specific deep dives in the README; those belong in separate docs if needed later.

## Risks / Trade-offs

- [Risk] The intro may become stale as the repository evolves -> Mitigation: keep it brief and tied to stable concepts only.
- [Trade-off] A minimal README will not answer every onboarding question -> Mitigation: treat it as an entry point, not full documentation.
