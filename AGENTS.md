# Hexage: agent instructions

Product requirements are in [HEXAGE_PROMPT.md](HEXAGE_PROMPT.md). Before making
changes, read the documents relevant to the task and check the current state of
the working copy. Preserve other people's changes; keep the diff within the
scope of the task. Reflect changes to the format, the threat model, and the
recovery scenarios in the documentation and in the compatibility checks.

<!-- codebase-memory-mcp:start -->
For structural code exploration, use the installed `codebase-memory` skill. If
the project is not in the graph, run `index_repository` first. After changes
that affect the code structure, re-index the project and check the changed
relationships against the fresh graph. Check index coverage for the files you
rely on; when coverage is incomplete, compare the missing ranges against the
sources. If the indexer is unavailable, state that in the report and verify the
affected places against the sources.
<!-- codebase-memory-mcp:end -->

- A function or method must be at most 40 lines, counted from `def` or
  `async def` to the last line of the body inclusive, including line breaks,
  blank lines, and comments. If work touches a longer function, split it by
  responsibility. Do not work around the limit by compressing code, nesting
  functions, or mechanical fragmentation. State a clear reason in a comment
  wherever the decision is not obvious.
- Name entities by purpose, use type annotations at module boundaries, and keep
  dependencies explicit. Do not put cryptography and file logic into widget
  handlers. Do not add abstractions or dependencies without a concrete task.
- Use supported crypto libraries. Do not output passwords, keys, OAuth tokens,
  note titles or texts to logs, UI traces, or test artifacts. Use only synthetic
  secrets in fixtures. Do not commit containers with real data, backups, tokens,
  or local settings.
- Use `pyproject.toml` for project configuration and checks. Prefer pytest for
  tests and Ruff for linting and formatting. Document the run commands. Maintain
  CI on Windows and Linux; ordinary tests must not require a network, real
  accounts, or a graphical session.
- Verify behavior and errors at the boundaries: saving, authentication, import
  without losing local edits, and format compatibility. Before finishing, run
  the applicable checks and state their results and limitations. Preserve
  compatibility of user data; do not perform an irreversible conversion without
  an explicit user choice and a verified backup.
