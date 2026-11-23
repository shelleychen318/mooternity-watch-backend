---
name: review-pr
description: Review a GitHub pull request locally — read the diff, analyze it, and write a structured review report to scratch/ (findings by severity, with file:line and suggested changes). Does NOT post anything to GitHub. Use when the user asks to review a PR, get feedback on a PR, or check a pull request before merging.
---

# Review a pull request (local report)

Read a GitHub PR, analyze the changes, and produce a review the user reads
in-editor. On this solo repo the `gh` account is the user's own, so posting
comments would just be the user talking to themselves — this skill therefore
**never writes to GitHub**. It only reads the PR and writes a local report.

Requires the `gh` CLI (authenticated, for reading) and `git`.

## Flow overview

Check `gh` → read the PR diff → analyze → write a structured report to
`scratch/pr-<n>-review.local.md` → surface the summary inline in chat.

## Steps

### 1. Verify prerequisites
- Run `gh --version` and `gh auth status`. If `gh` is missing, stop and tell the
  user to install it (`brew install gh`) and run `gh auth login`. Only read
  commands are used below — nothing posts.

### 2. Read the PR
- Identify the PR number (ask if ambiguous), then:
  ```
  gh pr view <PR_NUMBER>            # title, body, state
  gh pr diff <PR_NUMBER>            # the diff to review
  ```
- Read the diff carefully. Note file paths and the line numbers of changed lines.
  Pull the full file with `read_file` when a finding needs context the diff
  doesn't show. Cross-check against this repo's conventions in `CLAUDE.md`.

### 3. Analyze
- Look for: correctness bugs, security issues (secrets, injection, authz),
  data-loss or migration risks, missing or wrong tests, error handling, and
  deviations from repo conventions. Prefer specific, behavior-focused findings
  over style nits.
- Classify each finding by severity:
  - **Blocking** — bugs, security, data loss, broken/failing behavior.
  - **Should-fix** — correctness-adjacent or maintainability issues worth doing.
  - **Nit** — optional style/polish.

### 4. Write the report locally
- Write to `scratch/pr-<n>-review.local.md` (gitignored — never committed, never
  leaves the machine). Structure:
  ```
  # PR #<n> review — <title>

  ## Verdict
  <one line: ready to merge / changes recommended / blocked>

  ## Summary
  <2–4 sentences on what the PR does and overall assessment>

  ## Blocking
  - **app/foo.py:42** — <problem>. Suggested: <concrete change / code>

  ## Should-fix
  - **app/bar.py:17** — <problem>. Suggested: <concrete change>

  ## Nits
  - **tests/test_baz.py:9** — <minor point>
  ```
- Omit any severity section that has no findings. For each finding give a
  concrete suggested change (a code snippet when useful), not just a complaint.

### 5. Surface the result
- Print the verdict and the findings summary inline in chat, and tell the user the
  report path (`scratch/pr-<n>-review.local.md`) for the full detail.

## Guardrails

- **Never post to GitHub.** No `gh api ... /reviews`, no `gh pr review`, no
  `gh pr comment`. Read-only `gh pr view` / `gh pr diff` only. If the user later
  wants comments posted, that's a separate, explicit request.
- Write the report only under `scratch/` (or a `*.local.*` path) so it stays
  gitignored and off the PR.
- Keep findings specific and about behavior; don't reference internal task or
  milestone IDs.
- Don't modify the PR branch or any source files — this skill reviews, it doesn't
  fix. Offer to make changes separately if the user wants them.

---
Adapted and rephrased for licensing compliance from the github-pr-review skill:
https://github.com/aidankinzett/claude-git-pr-skill/blob/main/github-pr-review/skills/github-pr-review/SKILL.md
