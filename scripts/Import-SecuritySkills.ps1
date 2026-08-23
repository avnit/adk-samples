<#
.SYNOPSIS
    Imports a curated subset of the Anthropic-Cybersecurity-Skills collection into
    ~/.claude/skills, chosen to match a homelab + infra/DevOps + appsec workflow.

.DESCRIPTION
    The upstream repo (github.com/mukul975/Anthropic-Cybersecurity-Skills) ships 817
    skills. Installing all of them would bloat the skill-description listing budget and
    inject tens of thousands of tokens of context every turn. This script instead copies
    only the ~29 hand-picked skills in $Skills below into the user's personal skills dir.

    Each skill is a self-contained folder (SKILL.md plus any references/ and scripts/),
    so the whole folder is copied. An existing folder of the same name is backed up to
    <name>.bak.<timestamp> before being replaced, so re-running is safe and idempotent.

    Nothing here changes SLASH_COMMAND_TOOL_CHAR_BUDGET. These skills are always usable
    by explicit name (e.g. "use the hardening-docker-containers-for-production skill");
    the budget only governs automatic description-based matching.

.NOTES
    Requires git on PATH. Clones shallowly to a temp dir and cleans up afterward.
    Edit the $Skills list to add or drop skills, then re-run.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\Import-SecuritySkills.ps1
    # or, if you've set RemoteSigned for your user:
    .\scripts\Import-SecuritySkills.ps1
#>

[CmdletBinding()]
param(
    [string]$Repo       = 'https://github.com/mukul975/Anthropic-Cybersecurity-Skills.git',
    [string]$SkillsRoot = (Join-Path $env:USERPROFILE '.claude\skills'),
    [switch]$WhatIfCopy   # list what would be imported without writing anything
)

$ErrorActionPreference = 'Stop'

# --- Curated set: homelab defense, containers, backups/NAS, DevSecOps, appsec, DFIR ---
$Skills = @(
    # Network defense (UniFi VLANs, OPNsense Suricata, Zeek, fail2ban, canaries)
    'configuring-network-segmentation-with-vlans'
    'implementing-network-intrusion-prevention-with-suricata'
    'performing-network-traffic-analysis-with-zeek'
    'detecting-exfiltration-over-dns-with-zeek'
    'detecting-port-scanning-with-fail2ban'
    'deploying-honeytokens-and-canarytokens'
    # Zero-trust remote access (Headscale/Tailscale, encrypted DNS)
    'deploying-tailscale-for-zero-trust-vpn'
    'implementing-zero-trust-dns-with-nextdns'
    # Containers (Proxmox/Docker media stack)
    'hardening-docker-containers-for-production'
    'detecting-container-escape-with-falco-rules'
    'scanning-docker-images-with-trivy'
    # Backups / NAS / ransomware resilience (TrueNAS, Unraid, PBS)
    'implementing-immutable-backup-with-restic'
    'implementing-ransomware-backup-strategy'
    'validating-backup-integrity-for-recovery'
    'implementing-file-integrity-monitoring-with-aide'
    'deploying-ransomware-canary-files'
    # Endpoint hardening (Windows PC, trading VM, Linux hosts)
    'hardening-linux-endpoint-with-cis-benchmark'
    'hardening-windows-endpoint-with-cis-benchmark'
    # DevSecOps / IaC (terraform, github-actions, secrets)
    'auditing-terraform-infrastructure-for-security'
    'implementing-infrastructure-as-code-security-scanning'
    'securing-github-actions-workflows'
    'implementing-secrets-scanning-in-ci-cd'
    # Appsec / bug-bounty
    'testing-for-xss-vulnerabilities'
    'performing-ssrf-vulnerability-exploitation'
    'exploiting-idor-vulnerabilities'
    'testing-api-security-with-owasp-top-10'
    'performing-subdomain-enumeration-with-subfinder'
    # DFIR-lite for a self-hoster
    'building-incident-response-playbook'
    'conducting-memory-forensics-with-volatility'
)

Write-Host "Curated security-skills import" -ForegroundColor Cyan
Write-Host ("  source : {0}" -f $Repo)
Write-Host ("  target : {0}" -f $SkillsRoot)
Write-Host ("  skills : {0}" -f $Skills.Count)

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git was not found on PATH. Install Git for Windows, then re-run."
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$tmp   = Join-Path $env:TEMP ("acs-skills-{0}" -f $stamp)

try {
    Write-Host "`nCloning (shallow)..." -ForegroundColor DarkGray
    git clone --depth 1 --quiet $Repo $tmp
    if ($LASTEXITCODE -ne 0) { throw "git clone failed (exit $LASTEXITCODE)." }

    $srcRoot = Join-Path $tmp 'skills'
    if (-not (Test-Path $srcRoot)) { throw "No 'skills/' folder in the cloned repo." }

    if (-not $WhatIfCopy) {
        New-Item -ItemType Directory -Force -Path $SkillsRoot | Out-Null
    }

    $imported = 0; $backed = 0; $missing = @()
    foreach ($name in $Skills) {
        $src = Join-Path $srcRoot $name
        if (-not (Test-Path (Join-Path $src 'SKILL.md'))) {
            $missing += $name
            Write-Host ("  SKIP  {0}  (not found upstream)" -f $name) -ForegroundColor Yellow
            continue
        }
        $dst = Join-Path $SkillsRoot $name

        if ($WhatIfCopy) {
            Write-Host ("  WOULD IMPORT  {0}" -f $name) -ForegroundColor Gray
            $imported++
            continue
        }

        if (Test-Path $dst) {
            $bak = "$dst.bak.$stamp"
            Move-Item -Path $dst -Destination $bak
            $backed++
            Write-Host ("  BACKUP existing -> {0}" -f (Split-Path $bak -Leaf)) -ForegroundColor DarkYellow
        }
        Copy-Item -Path $src -Destination $dst -Recurse
        $imported++
        Write-Host ("  OK    {0}" -f $name) -ForegroundColor Green
    }

    Write-Host ""
    if ($WhatIfCopy) {
        Write-Host ("Dry run: {0} skills would be imported." -f $imported) -ForegroundColor Cyan
    } else {
        Write-Host ("Imported {0} skills into {1}" -f $imported, $SkillsRoot) -ForegroundColor Cyan
        if ($backed)  { Write-Host ("  ({0} existing folder(s) backed up as *.bak.{1})" -f $backed, $stamp) }
        $total = (Get-ChildItem -Path $SkillsRoot -Directory -ErrorAction SilentlyContinue |
                  Where-Object { -not $_.Name.Contains('.bak.') }).Count
        Write-Host ("  total skills now present: {0}" -f $total)
        Write-Host "`nRestart Claude Code, then check /skills. Invoke any by name, e.g.:" -ForegroundColor DarkGray
        Write-Host "  'use the hardening-docker-containers-for-production skill'" -ForegroundColor DarkGray
    }
    if ($missing.Count) {
        Write-Host ("`nNote: {0} skill name(s) not found upstream (repo may have renamed them):" -f $missing.Count) -ForegroundColor Yellow
        $missing | ForEach-Object { Write-Host ("  - {0}" -f $_) -ForegroundColor Yellow }
    }
}
finally {
    if (Test-Path $tmp) {
        Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
