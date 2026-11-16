---
name: log-entry
description: Write a SYDE 461 capstone logbook entry in docs/logbook.local.md after a unit of work is done (e.g. a milestone, a PR, a feature). Use when the user asks to log, journal, or record work they just finished, or to add a logbook entry.
---

# Write a capstone logbook entry

Append a new dated entry to `docs/logbook.local.md` summarizing a unit of work
the user just completed. The logbook is a SYDE 461 **individual** academic
logbook: reflective, first-person prose for a reader who is not a software
engineer. Match the existing entries exactly — a new entry should read as if the
same person wrote it on the same day.

## Steps

1. **Read `docs/logbook.local.md` first.** Never overwrite it. Always append.
   Read it to confirm the house voice and see the last entry's date.
2. **Gather what the work was.** Prefer a concrete source the user points to: a
   PR, a `scratch/milestone-*-summary.md`, a commit, or a description. If the
   unit of work is unclear, ask which work to log before writing.
3. **Translate the technical work into plain language** (see Voice). Do not
   paste in code-level detail.
4. **Draft the entry** following the Structure below.
5. **Append** it to the end of the file. Leave a blank line between the previous
   entry and the new heading.
6. Tell the user it's a draft and offer to adjust it. Do **not** commit or stage
   the file — it is gitignored and personal.

## Structure

Start with a dated heading, then write flowing prose. There is no fixed
template — vary the shape from entry to entry so they don't read formulaically.

- **Heading:** `## <D Mon YYYY> — <short title>`, e.g.
  `## 11 Nov 2026 — Event payload contract`. Use the date the work was completed
  (usually today).
- **Body:** a few short paragraphs of prose (the existing entries run ~1–3
  paragraphs). Cover whichever of the four course criteria the work naturally
  calls for — you don't need all four in every entry, and in any order:
  1. thoughts related to the project
  2. your contribution to the project
  3. your learning
  4. your reflections
- Each paragraph is a single line in the source (the existing entries are not
  hard-wrapped).
- **Do not add a figure caption.** The user adds any `Figure N` lines and
  screenshots themselves, at their discretion.

## Voice

Study the existing entries and mirror them. Key traits:

- **First person, reflective, academic-casual.** "I implemented…", "Reflecting
  on it…", "The biggest thing I learned…".
- **Plain language for a non-engineer.** Explain mechanisms in everyday terms.
  Example from the logbook: idempotency was described as "the database rejects
  any repeat of that identifier outright, so a camera retrying a push after a
  connectivity error can't accidentally create a second record" — no jargon.
  Avoid or gloss terms like Pydantic, enum, schema, FK, migration.
- **Connect to the arc of the project.** Tie the work back to earlier entries
  and recurring themes (e.g. "defining the contracts on paper first keeps paying
  off", limited data as a first-order constraint, subsystem interfaces).
- **Honest reflection, not a status report.** Note what a decision traded away,
  what surprised you, or what you'd watch going forward.
- Avoid marketing tone, exclamation, and bullet lists inside the entry — the
  existing entries are flowing prose.

## Guardrails

- Target file is always `docs/logbook.local.md` in this repo.
- Append only; preserve everything already in the file.
- If the user hasn't said what to log, ask — don't guess at the unit of work.
- Keep it to one entry per invocation unless asked otherwise.
