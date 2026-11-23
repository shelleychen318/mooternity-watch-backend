---
name: open-pr
description: Open a GitHub pull request for the current work — create a branch off main if needed, commit, push, draft a PR title and description, get the user's approval, then open the PR and return the link. Use when the user asks to open/create/raise a PR or pull request, or to ship/submit finished work for review.
---

# Open a pull request

Take committed or in-progress work and turn it into a GitHub PR against `main`,
stopping for the user's approval at two points. Mirror the conventions already
used in this repo's PRs (see existing PRs via `gh pr list` / `gh pr view <n>`).

Requires the `gh` CLI (authenticated) and `git`.

## Flow overview

Branch (if needed) → stage specific paths → **gate 1: confirm the commit** →
commit → push → draft title + description → **gate 2: approve the PR body** →
`gh pr create` → return the link.

## Steps

### 1. Assess state
- Run `git status` and `git branch --show-current` to see the current branch and
  what's changed. Run `git diff` / `git diff --staged` to understand the work.

### 2. Branch (smart — only if needed)
- **If already on a feature branch** (not `main`) with the relevant work, use it.
- **If on `main`, or the work isn't on a feature branch yet:** create one off the
  latest main:
  ```
  git checkout main && git pull --ff-only && git checkout -b <type>/<slug>
  ```
  Then bring the work onto it. Branch names follow the repo pattern, e.g.
  `feature/<slug>`, `docs/<slug>`, `fix/<slug>`, `chore`.
- Never commit directly to `main`.

### 3. Stage specific paths
- Stage the files that belong to this change **by name/path** (e.g.
  `git add app/schemas tests/schemas`). Do **not** use `git add .` / `git add -A`
  — that risks pulling in unrelated or gitignored-adjacent files. Confirm with
  `git status` that only intended files are staged.

### 4. Run the local gate
- Run the project gate before committing and fix anything red:
  `ruff check . && ruff format --check . && pytest` (add `alembic check` if models
  changed). Re-run `ruff format --check .` as the very last thing — a format-only
  diff introduced late will fail CI. See `CLAUDE.md` for the authoritative gate.

### 5. Gate 1 — confirm the commit
- Show the user the staged file list and the proposed commit message, and **wait
  for their confirmation** before committing.
- Commit message style: a concise imperative summary of the change; optionally a
  short body. Example: `git commit -m "<subject>" -m "<optional body>"`. Do not
  reference internal task/milestone IDs — commits are public and those IDs mean
  nothing to outside readers.

### 6. Push
- `git push -u origin <branch>` (first push) or `git push`.

### 7. Draft the PR title + description
- **Title:** prefix with the branch type, then a sentence-case summary:
  `<type>: <summary>`, where `<type>` matches the branch pattern (`feat`, `fix`,
  `docs`, `chore`). Concise, no milestone IDs. (e.g.
  `docs: remove milestone/task ID references from source and config`, or
  `feat: event payload contract with versioned schema and classification`.)
- **Description:** use these sections, omitting any that don't apply:
  `## Summary`, `## What's added`, `## Notable design points`, `## Testing`,
  `## How to verify`. Keep prose focused on behavior; no milestone IDs in the
  body.
- **Line wrapping (important):** write paragraphs and bullets as **single
  unwrapped lines** — do not hard-wrap mid-sentence. GitHub soft-wraps to the
  full width; hard wrapping renders cramped. Code fences keep their own breaks.

### 8. Gate 2 — approve the PR body
- Show the user the drafted title and full description and **wait for their
  approval** (or edits) before opening the PR.

### 9. Open the PR and return the link
- Write the approved body to a temp file under gitignored `scratch/` (e.g.
  `scratch/.pr-body.local.md`) to preserve formatting, then:
  ```
  gh pr create --base main --head <branch> --title "<title>" --body-file scratch/.pr-body.local.md
  ```
- Delete the temp body file afterward.
- Send the user the PR URL. Optionally watch CI with `gh pr checks <n> --watch`
  and report the result; if a check fails, pull logs with
  `gh run view <run-id> --log-failed` and fix the root cause.

## Guardrails

- Two approval gates: before committing (step 5) and before opening the PR
  (step 8). Do not skip them.
- PRs always target `main`.
- Stage by explicit path; never `git add .`.
- Never force-push, never modify git config, never commit to `main` directly.
- Keep gitignored/personal files (e.g. `scratch/`, `*.local.md`) out of the
  commit and the PR.
- Don't attach screenshots (the tooling can't); leave image placeholders out
  unless the user adds them.
