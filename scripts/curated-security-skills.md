# Curated security skills

A hand-picked subset of the [Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills)
collection (817 skills upstream), narrowed to ~29 that fit a homelab + infra/DevOps +
appsec workflow. Import them with [`Import-SecuritySkills.ps1`](./Import-SecuritySkills.ps1).

Why a subset and not all 817: every skill's description counts against Claude Code's
skill-listing budget (`SLASH_COMMAND_TOOL_CHAR_BUDGET`). Importing all of them would
blow that budget and inject tens of thousands of tokens of context on every turn. The
imported skills are always usable **by explicit name**; the budget only limits automatic
description-based matching.

| Skill | Fits |
|---|---|
| configuring-network-segmentation-with-vlans | UniFi VLAN isolation |
| implementing-network-intrusion-prevention-with-suricata | OPNsense Suricata IPS |
| performing-network-traffic-analysis-with-zeek | Passive network monitoring |
| detecting-exfiltration-over-dns-with-zeek | DNS-tunneling detection |
| detecting-port-scanning-with-fail2ban | Edge/SSH brute-force defense |
| deploying-honeytokens-and-canarytokens | Breach tripwires |
| deploying-tailscale-for-zero-trust-vpn | Self-hosted Headscale mesh |
| implementing-zero-trust-dns-with-nextdns | Encrypted DoH/DoT resolver |
| hardening-docker-containers-for-production | Proxmox/Docker media stack |
| detecting-container-escape-with-falco-rules | Container runtime detection |
| scanning-docker-images-with-trivy | Image vuln scanning |
| implementing-immutable-backup-with-restic | Object-lock backups (MinIO) |
| implementing-ransomware-backup-strategy | 3-2-1-1-0 for TrueNAS/Unraid/PBS |
| validating-backup-integrity-for-recovery | Restore-testing discipline |
| implementing-file-integrity-monitoring-with-aide | Host FIM on Linux nodes |
| deploying-ransomware-canary-files | NAS-share ransomware tripwires |
| hardening-linux-endpoint-with-cis-benchmark | LXC/VM hardening |
| hardening-windows-endpoint-with-cis-benchmark | Windows PC / trading VM |
| auditing-terraform-infrastructure-for-security | Pairs with terraform-generator |
| implementing-infrastructure-as-code-security-scanning | Checkov/tfsec/KICS |
| securing-github-actions-workflows | Pairs with github-actions-generator |
| implementing-secrets-scanning-in-ci-cd | gitleaks/trufflehog gates |
| testing-for-xss-vulnerabilities | Appsec / bug bounty |
| performing-ssrf-vulnerability-exploitation | Appsec / bug bounty |
| exploiting-idor-vulnerabilities | Appsec / bug bounty |
| testing-api-security-with-owasp-top-10 | API assessment |
| performing-subdomain-enumeration-with-subfinder | Recon |
| building-incident-response-playbook | Self-hoster DFIR |
| conducting-memory-forensics-with-volatility | Self-hoster DFIR |

Edit the `$Skills` array in the importer to add or drop entries, then re-run. The script
is idempotent — an existing same-named folder is backed up to `<name>.bak.<timestamp>`
before being replaced.

> These are dual-use security skills and each may carry bundled scripts. Skim a skill's
> `scripts/` before running it against a real target.
