Read when: creating or changing `.pre-commit-config.yaml`. Language-neutral rules; checks and templates live in the language skills.

- Every repo has a pre-commit config and a CI workflow that run the same checks.
- Derive hooks from `.github/workflows`. If CI changes, the hooks change in the same commit.
- Start from the closest template in the language skill. Adapt lint dirs, package name and coverage floor. Keep the header comments.
- Repo 1: `pre-commit/pre-commit-hooks` at a pinned rev, hygiene only. Repo 2: `repo: local`.
- `language: system`, never a pinned mirror. Tools read the repo's own config.
- Tools are installed once per machine (pipx, uv tool, rustup). Hooks never install them or add them to a project environment.
- `pass_filenames: false` for whole-project tools.
- `files:` not `types:`, and include the governing config file (`pyproject.toml`, `Cargo.toml`).
- Lint where the code lives. Check the layout, do not copy from another repo.
- Comment each non-obvious choice with the failure it prevents.
- A formatter is its own check-only hook (`--check`, `-d`, `fmt --check`), never one that rewrites files: a rewrite mid-commit leaves the staged and working trees different.
- Adopting a formatter is one formatting-only commit; list it in `.git-blame-ignore-revs` and run `git config blame.ignoreRevsFile .git-blame-ignore-revs`.
- Pin the linter's rule set in the project config: a default set moves with each release and breaks the gate with no commit to blame.
- Coverage is its own hook with `--fail-under=N`. The floor only ratchets up: never lower it to pass a commit.
- Only add hooks for languages present in the repo.
- System tool versions must match CI; pin them in CI.
