param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$SkillRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "AlgeoMath skill setup is starting..."
& $Python "$SkillRoot\scripts\setup_algeomath.py"
Write-Host "AlgeoMath skill setup is complete."
