param([switch]$Browser)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"
Set-NodeRuntime
Push-Location (Join-Path $ProjectRoot 'backend')
try { Invoke-Checked (Get-ProjectPython) @('-m', 'pytest', '-q') } finally { Pop-Location }
Invoke-Npm -NpmArguments @('run', 'build')
if ($Browser) { Invoke-Npm -NpmArguments @('run', 'test:e2e') }
