# Agent instructions

<!-- preserve-project-context:start -->
## Persistent project context

- Before substantive work, read `docs/project/README.md`, `brief.md`, `current-state.md`, and `open-questions.md`.
- Read `architecture.md` and relevant ADRs when work affects design, interfaces, dependencies, or system boundaries.
- Treat repository context as canonical; do not rely on chat history or memory as the only source of project facts.
- After material work, refresh `current-state.md`, append one concise `work-log.md` handoff, and update affected questions or ADRs.
- Do not update project context for read-only exploration or inconsequential edits.
<!-- preserve-project-context:end -->

## Repository safety

- This is a GitHub/Git and uv project, not an Arcadia repository.
- Preserve existing uncommitted implementation work.
- Never write to live GnuCash books; use disposable synthetic copies for imports.
- Keep private financial reports, mappings, books and exports out of tracked files.
- For Arcadia code search, use remote code search rather than grep/rg. Local grep/rg is allowed only in directories known to have a limited number of files.
