# Ship a committed feature branch: local tests + lint -> dev (wait for CI) -> main (wait for the deploy
# and its health check) -> show the service state. Stops at the first failure; never pushes red code.
#   pwsh scripts/ship.ps1 <branch>
# See .claude/skills/ship/SKILL.md.
param([Parameter(Mandatory = $true)][string]$Branch)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$api = "https://api.github.com/repos/Dood345/Doods-Discord-Bot/actions/runs"

function Wait-Run($ref, $sha) {
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep 15
        $r = (Invoke-RestMethod "$api`?branch=$ref&per_page=1").workflow_runs[0]
        if ($r.head_sha -eq $sha -and $r.status -eq "completed") { return $r }
    }
    throw "timed out waiting for the $ref run"
}

if ($Branch -in @("main", "dev")) { "ship a feature branch, not $Branch"; exit 1 }
git checkout -q $Branch
if (git status --porcelain) { "uncommitted changes on $Branch; commit first"; exit 1 }

# Never push a red branch: the local suite and lint must pass on exactly what's committed
python -m uv run pytest -q 2>&1 | Select-Object -Last 1
if ($LASTEXITCODE -ne 0) { "local tests failed; not shipping"; exit 1 }
python -m uv run ruff check . | Select-Object -Last 1
if ($LASTEXITCODE -ne 0) { "lint failed; not shipping"; exit 1 }

git push -q -u origin $Branch 2>$null
git checkout -q dev; git pull -q --ff-only origin dev; git merge -q --no-edit $Branch; git push -q origin dev 2>$null
$sha = (git rev-parse HEAD).Trim()
$r = Wait-Run "dev" $sha
"dev CI: $($r.conclusion) ($($sha.Substring(0,7)))"
if ($r.conclusion -ne "success") { "dev CI failed: $($r.html_url)"; exit 1 }

git checkout -q main; git pull -q --ff-only origin main; git merge -q --no-edit dev; git push -q origin main 2>$null
$r = Wait-Run "main" $sha
"deploy: $($r.conclusion)"
if ($r.conclusion -ne "success") { "deploy failed (it rolls back on a failed health check): $($r.html_url)"; exit 1 }
ssh doodlab "systemctl is-active discordBot.service; tail -n 1 /home/dood345/discordBot/data/logs/bot.log | cut -c1-140"
