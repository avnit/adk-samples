<#
.SYNOPSIS
    Diagnose and repair Claude Code skills that aren't loading / auto-matching.

.DESCRIPTION
    Runs the full skills-doctor workflow on THIS Windows machine:
      1. Baseline    - count skill folders on disk + capture Claude Code's debug load count
      2. Budget      - sum description sizes, flag entries over the real 1,536-char cap and a 300-char heuristic
      3. Validate    - frontmatter checks (case, name, description, multi-line YAML) -> CSV
      4. Fix         - SAFE auto-fixes only (dry-run by default; -Apply to write; backup first)
      5. Verify      - print the exact /doctor, /context and budget steps to confirm

    Corrects the original handover's mechanism to match the official docs
    (https://code.claude.com/docs/en/skills):
      * Skill NAMES always load; only DESCRIPTIONS get truncated/dropped when the
        listing overflows its budget. So the symptom of overflow is broken
        auto-matching, not skills vanishing. /skill-name still works.
      * Default budget = 1% of the model context window; raise with the
        skillListingBudgetFraction setting OR $env:SLASH_COMMAND_TOOL_CHAR_BUDGET.
      * Per-entry cap = 1,536 chars (description + when_to_use), not 300.
      * Missing `name:` does NOT disable the slash command (dir name drives it);
        it only removes the auto-match description. Malformed frontmatter -> body
        loads with empty metadata.

.PARAMETER SkillsRoot
    Path to the skills directory. Default: ~\.claude\skills

.PARAMETER Apply
    Actually write fixes. Without this, Step 4 is a dry-run (reports only).

.PARAMETER SetBudget
    If given (e.g. -SetBudget 80000), persists SLASH_COMMAND_TOOL_CHAR_BUDGET
    to the User environment. Restart the terminal afterwards.

.PARAMETER DebugTimeoutSec
    How long to let `claude --debug` run while capturing the load line. Default 25.

.EXAMPLE
    # Diagnose only (safe, no writes):
    .\Repair-ClaudeSkills.ps1

.EXAMPLE
    # Diagnose, apply the safe fixes, and raise the budget:
    .\Repair-ClaudeSkills.ps1 -Apply -SetBudget 80000
#>
[CmdletBinding()]
param(
    [string] $SkillsRoot = (Join-Path $HOME '.claude\skills'),
    [switch] $Apply,
    [int]    $SetBudget = 0,
    [int]    $DebugTimeoutSec = 25
)

$ErrorActionPreference = 'Stop'
function Section($t) { Write-Host "`n===== $t =====" -ForegroundColor Cyan }
function Note($t)    { Write-Host $t -ForegroundColor DarkGray }

if (-not (Test-Path $SkillsRoot)) {
    Write-Host "Skills root not found: $SkillsRoot" -ForegroundColor Red
    Write-Host "Pass -SkillsRoot <path> if your skills live elsewhere."
    exit 1
}
$SkillsRoot = (Resolve-Path $SkillsRoot).Path
Write-Host "Skills root: $SkillsRoot"

# Helper: pull the YAML frontmatter block (text between the first two --- fences)
function Get-Frontmatter([string]$content) {
    if ($content -match '(?s)^﻿?---\s*\r?\n(.*?)\r?\n---') { return $matches[1] }
    return $null
}
# Helper: extract a single-line scalar value for a top-level key from frontmatter
function Get-FmValue([string]$fm, [string]$key) {
    $m = [regex]::Match($fm, "(?m)^$key\s*:\s*(.+?)\s*$")
    if ($m.Success) { return $m.Groups[1].Value.Trim('"',"'",' ') }
    return $null
}
# Every SKILL.md, recursively (handles nested / namespaced skills)
$skillFiles = Get-ChildItem $SkillsRoot -Recurse -Filter 'SKILL.md' -File -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------------
Section 'STEP 1  -  Baseline: disk vs loaded'
$diskFolders = (Get-ChildItem $SkillsRoot -Directory -ErrorAction SilentlyContinue).Count
$skillMdCount = $skillFiles.Count
Write-Host ("Top-level skill folders on disk : {0}" -f $diskFolders)
Write-Host ("SKILL.md files found (recursive) : {0}" -f $skillMdCount)

$loadedLine = $null
$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) {
    Note "Capturing `claude --debug` load line (up to $DebugTimeoutSec s)..."
    try {
        $job = Start-Job {
            param($to)
            # --debug prints the load summary early; -p '' exits without an interactive session
            & claude --debug -p 'exit' 2>&1
        } -ArgumentList $DebugTimeoutSec
        if (Wait-Job $job -Timeout $DebugTimeoutSec) {
            $out = Receive-Job $job
        } else {
            Stop-Job $job | Out-Null
            $out = Receive-Job $job
        }
        Remove-Job $job -Force -ErrorAction SilentlyContinue
        $loadedLine = $out | Select-String -Pattern 'loaded.*skill|skill.*loaded|unique skills' |
                      Select-Object -First 3
    } catch {
        Note "Could not capture debug output: $($_.Exception.Message)"
    }
    if ($loadedLine) {
        Write-Host "Debug load line(s):" -ForegroundColor Green
        $loadedLine | ForEach-Object { Write-Host "  $_" }
    } else {
        Note "No load line captured. Best manual check: run  /doctor  and  /context  inside Claude Code."
    }
} else {
    Note "`claude` CLI not on PATH; skipping debug capture. Use /doctor + /context inside Claude Code instead."
}
Note "NOTE: per docs, ALL skill NAMES always load. Overflow only truncates DESCRIPTIONS,"
Note "      which breaks auto-matching (not /skill-name invocation). So the disk-vs-loaded"
Note "      delta to chase is really 'descriptions dropped', surfaced best by /doctor."

# ---------------------------------------------------------------------------
Section 'STEP 2  -  Description budget'
$PER_ENTRY_CAP = 1536   # official cap: description + when_to_use combined
$HEURISTIC     = 300    # handover heuristic for "too long, review"
$rows = foreach ($f in $skillFiles) {
    $content = Get-Content $f.FullName -Raw
    $fm = Get-Frontmatter $content
    if (-not $fm) { continue }
    $desc = Get-FmValue $fm 'description'
    $wtu  = Get-FmValue $fm 'when_to_use'
    $combined = (($desc + ' ' + $wtu).Trim()).Length
    [PSCustomObject]@{
        Skill        = Split-Path (Split-Path $f.FullName -Parent) -Leaf
        DescLen      = ($desc  | Measure-Object -Character).Characters
        CombinedLen  = $combined
        File         = $f.FullName
    }
}
$totalDesc = ($rows | Measure-Object DescLen -Sum).Sum
Write-Host ("Total description chars across all skills : {0}" -f $totalDesc)
Note "Default listing budget = 1% of the model context window (a few thousand chars)."
Note "With $skillMdCount skills you are almost certainly over it -> descriptions truncated."
Write-Host ""
Write-Host "Entries over the REAL 1,536-char per-entry cap (these are hard-truncated):" -ForegroundColor Yellow
$over1536 = $rows | Where-Object CombinedLen -gt $PER_ENTRY_CAP | Sort-Object CombinedLen -Descending
if ($over1536) { $over1536 | Select-Object Skill,CombinedLen -First 20 | Format-Table -AutoSize } else { Note "  (none)" }
Write-Host "Top 20 longest descriptions over $HEURISTIC chars (review candidates):" -ForegroundColor Yellow
$rows | Where-Object DescLen -gt $HEURISTIC | Sort-Object DescLen -Descending |
    Select-Object Skill,DescLen -First 20 | Format-Table -AutoSize

# ---------------------------------------------------------------------------
Section 'STEP 3  -  Frontmatter validation'
$report = New-Object System.Collections.Generic.List[object]
foreach ($folder in (Get-ChildItem $SkillsRoot -Directory)) {
    $name = $folder.Name
    $skillFile = Join-Path $folder.FullName 'SKILL.md'
    # case-insensitive match then compare exact bytes
    $any = Get-ChildItem $folder.FullName -Filter 'skill.md' -File -ErrorAction SilentlyContinue
    $wrongCase = $any | Where-Object { $_.Name -cne 'SKILL.md' }

    if ($wrongCase -and -not (Test-Path $skillFile -PathType Leaf)) {
        $report.Add([PSCustomObject]@{ Folder=$name; Issue="Wrong case: $($wrongCase.Name)"; Fixable='auto' }); continue
    }
    if (-not (Test-Path $skillFile)) {
        # maybe skill is nested one level deeper; only flag if no SKILL.md anywhere under it
        $nested = Get-ChildItem $folder.FullName -Recurse -Filter 'SKILL.md' -File -ErrorAction SilentlyContinue
        if (-not $nested) { $report.Add([PSCustomObject]@{ Folder=$name; Issue='Missing SKILL.md'; Fixable='manual' }) }
        continue
    }
    $content = Get-Content $skillFile -Raw
    $fm = Get-Frontmatter $content
    if (-not $fm) {
        $report.Add([PSCustomObject]@{ Folder=$name; Issue='No frontmatter'; Fixable='manual' }); continue
    }
    if ($fm -notmatch '(?m)^name:\s*\S') {
        $report.Add([PSCustomObject]@{ Folder=$name; Issue='Missing or empty name:'; Fixable='auto' })
    }
    if ($fm -notmatch '(?m)^description:\s*\S') {
        # distinguish truly-missing vs multi-line
        if ($fm -match '(?m)^description:\s*[|>]?\s*$') {
            $report.Add([PSCustomObject]@{ Folder=$name; Issue='Multi-line description (Prettier-reformatted)'; Fixable='auto' })
        } else {
            $report.Add([PSCustomObject]@{ Folder=$name; Issue='Missing or empty description:'; Fixable='manual' })
        }
    }
}
if ($report.Count) { $report | Format-Table -AutoSize } else { Write-Host "No frontmatter issues found." -ForegroundColor Green }
$csv = Join-Path $HOME 'claude-skills-issues.csv'
$report | Export-Csv $csv -NoTypeInformation -Encoding UTF8
Write-Host "CSV written: $csv" -ForegroundColor Green

# summary counts
$byIssue = $report | Group-Object { ($_.Issue -split ':')[0] } | Sort-Object Count -Descending
if ($byIssue) { Write-Host "`nIssue summary:"; $byIssue | ForEach-Object { "  {0,-45} {1}" -f $_.Name, $_.Count } }

# ---------------------------------------------------------------------------
Section 'STEP 4  -  Safe auto-fixes'
$autoFixable = $report | Where-Object Fixable -eq 'auto'
$manualOnly  = $report | Where-Object Fixable -eq 'manual'
Write-Host ("Auto-fixable : {0}   Manual-only (flagged, NOT touched): {1}" -f $autoFixable.Count, $manualOnly.Count)

if (-not $Apply) {
    Write-Host "DRY-RUN (no -Apply). The following WOULD be fixed:" -ForegroundColor Yellow
    $autoFixable | Format-Table Folder,Issue -AutoSize
    Note "Re-run with -Apply to write these changes. A timestamped backup is made first."
} elseif ($autoFixable.Count -eq 0) {
    Write-Host "Nothing to auto-fix." -ForegroundColor Green
} else {
    $backup = "$SkillsRoot.bak.$(Get-Date -Format yyyyMMdd-HHmm)"
    Write-Host "Backing up -> $backup" -ForegroundColor Green
    Copy-Item -Recurse $SkillsRoot $backup
    $fixCounts = @{ 'Wrong case'=0; 'Missing name'=0; 'Multi-line description'=0 }
    $shown = @{ 'Wrong case'=0; 'Missing name'=0; 'Multi-line description'=0 }

    foreach ($item in $autoFixable) {
        $folder = Join-Path $SkillsRoot $item.Folder
        switch -Wildcard ($item.Issue) {
            'Wrong case*' {
                $bad = Get-ChildItem $folder -Filter 'skill.md' -File | Where-Object Name -cne 'SKILL.md' | Select-Object -First 1
                if ($bad) {
                    # rename via temp to force case change on case-insensitive NTFS
                    $tmp = Join-Path $folder ('__tmp_' + [guid]::NewGuid().ToString('N') + '.md')
                    Rename-Item $bad.FullName $tmp
                    Rename-Item $tmp 'SKILL.md'
                    $fixCounts['Wrong case']++
                    if ($shown['Wrong case'] -lt 3) { Write-Host "  [case] $($item.Folder): $($bad.Name) -> SKILL.md"; $shown['Wrong case']++ }
                }
            }
            'Missing or empty name*' {
                $sf = Join-Path $folder 'SKILL.md'
                $c = Get-Content $sf -Raw
                # insert `name: <folder>` as the first line after the opening ---
                $new = [regex]::Replace($c, '(?s)^(﻿?---\s*\r?\n)', ('${1}name: ' + $item.Folder + "`n"), 1)
                if ($new -ne $c) {
                    if ($shown['Missing name'] -lt 3) {
                        Write-Host "  [name] $($item.Folder): + 'name: $($item.Folder)'"
                        Note   "    --- before ---"; ($c  -split "`n" | Select-Object -First 4) | ForEach-Object { Note "    $_" }
                        Note   "    --- after  ---"; ($new -split "`n" | Select-Object -First 4) | ForEach-Object { Note "    $_" }
                        $shown['Missing name']++
                    }
                    Set-Content $sf $new -NoNewline -Encoding UTF8
                    $fixCounts['Missing name']++
                }
            }
            'Multi-line description*' {
                $sf = Join-Path $folder 'SKILL.md'
                $c = Get-Content $sf -Raw
                # collapse `description:` + following indented lines into one quoted scalar
                $pattern = '(?ms)^description:\s*[|>]?[+-]?\s*\r?\n((?:[ \t]+.*\r?\n?)+)'
                $m = [regex]::Match($c, $pattern)
                if ($m.Success) {
                    $body = ($m.Groups[1].Value -split '\r?\n' | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join ' '
                    $body = $body -replace '"','\"'
                    $replacement = 'description: "' + $body + "`"`n"
                    $new = $c.Substring(0,$m.Index) + $replacement + $c.Substring($m.Index + $m.Length)
                    if ($shown['Multi-line description'] -lt 3) {
                        Write-Host "  [desc] $($item.Folder): collapsed multi-line description to single line"
                        $shown['Multi-line description']++
                    }
                    Set-Content $sf $new -NoNewline -Encoding UTF8
                    $fixCounts['Multi-line description']++
                }
            }
        }
    }
    Write-Host "`nApplied:" -ForegroundColor Green
    $fixCounts.GetEnumerator() | ForEach-Object { "  {0,-24} {1}" -f $_.Key, $_.Value }
    Note "Prettier note: YAML frontmatter has no reliable inline 'prettier-ignore'."
    Note "To stop Prettier re-breaking these, add this to .prettierignore:  **/SKILL.md"
}

if ($manualOnly.Count) {
    Write-Host "`nFLAGGED FOR MANUAL REVIEW (not modified):" -ForegroundColor Magenta
    $manualOnly | Format-Table Folder,Issue -AutoSize
}

# ---------------------------------------------------------------------------
Section 'STEP 5  -  Budget + verify'
if ($SetBudget -gt 0) {
    [Environment]::SetEnvironmentVariable('SLASH_COMMAND_TOOL_CHAR_BUDGET', "$SetBudget", 'User')
    Write-Host "Set SLASH_COMMAND_TOOL_CHAR_BUDGET=$SetBudget (User). RESTART your terminal for it to take effect." -ForegroundColor Green
} else {
    Note "To raise the description budget, either:"
    Note "  - env var : setx SLASH_COMMAND_TOOL_CHAR_BUDGET 80000   (then restart terminal)"
    Note "  - setting : add  \"skillListingBudgetFraction\": 0.03  to ~/.claude/settings.json"
    Note "  - or set low-priority skills to name-only via /skills (Space to cycle, Enter to save)"
}
Write-Host ""
Write-Host "Verify inside Claude Code:" -ForegroundColor Cyan
Write-Host "  /doctor    -> listing context cost + biggest description contributors"
Write-Host "  /context   -> 'Skills' row = post-budget listing size the model actually sees"
Write-Host "  /skills    -> should list every skill NAME; if totally empty but /doctor shows"
Write-Host "               skills, that's the known UI bug -> npm i -g @anthropic-ai/claude-code@latest"
Write-Host ""
Write-Host "Report artifacts:" -ForegroundColor Cyan
Write-Host "  CSV    : $csv"
if ($Apply -and (Test-Path variable:backup)) { Write-Host "  Backup : $backup" }
Write-Host "Done."
