# scripts

Standalone helper utilities. Not part of the ADK samples themselves.

## Repair-ClaudeSkills.ps1

Windows PowerShell tool to diagnose and repair Claude Code skills that aren't
loading or auto-matching under `~/.claude/skills`. Runs a five-step workflow:
baseline disk-vs-loaded count, description-budget analysis, frontmatter
validation (CSV report), safe auto-fixes, and a verify checklist.

Safe by default — it is a dry-run and writes nothing until you pass `-Apply`,
which takes a timestamped backup of the skills directory first.

```powershell
# Diagnose only:
.\Repair-ClaudeSkills.ps1

# Apply safe fixes and raise the description-listing budget:
.\Repair-ClaudeSkills.ps1 -Apply -SetBudget 80000
```

Notes on the underlying mechanism (per https://code.claude.com/docs/en/skills):

- Skill **names** always load; only **descriptions** are truncated/dropped when
  the listing overflows its budget, which breaks auto-matching (not `/skill-name`
  invocation).
- The listing budget defaults to 1% of the model context window; raise it with
  the `skillListingBudgetFraction` setting or the
  `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable.
- Per-entry cap is 1,536 chars (`description` + `when_to_use`).
- Use `/doctor` and `/context` inside Claude Code to see the post-budget cost.
