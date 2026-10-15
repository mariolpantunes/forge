---
name: bp-rust
description: "Best practices for Rust work: cargo, lints in CI, install scope. Use when writing, building or reviewing Rust code."
---

# bp-rust

Install scope: build and run with `cargo` inside the project. Dependencies go in `Cargo.toml`. `cargo install` (a binary into `~/.cargo/bin`) and any system package need the user's approval: ask first.

1. Format: `cargo fmt --check` (check only).
   Adopt it in one formatting-only commit (`cargo fmt`, tests green) and list that commit in `.git-blame-ignore-revs`.
   Settings go in `rustfmt.toml` at the crate root, never in the hook.
2. Lint: `cargo clippy --release -- -D warnings`. Use release: debug and release enable different lints, and release matches CI.
3. Test: `cargo test`; keep unit tests next to the code, integration tests in `tests/`.
4. Pre-commit hook trigger: files `'(\.rs$|^Cargo\.toml$)'`, with `pass_filenames: false` because cargo always checks the whole crate. Template for a mixed Python and Rust repo: `~/.agents/skills/bp-rust/templates/precommit/python-rust.yaml`.
5. CI pipeline: `.github/workflows/` runs the same three commands (fmt, clippy release, test); hooks mirror it (rules for the hook file are in `bp-git`).
6. Mixed repos: find which directory holds the crate and which the Python package before wiring hooks.
7. Scratch builds and benchmarks write to the OS temp folder (`CARGO_TARGET_DIR=/tmp/<project>/target`) when they should not touch the project; agent notes in `./.agents/` (gitignored).

Notes:
- Pin crate versions from the registry's latest release, not from memory.
- A skill that ships Rust keeps a Cargo project inside its folder and builds it with `cargo`.
