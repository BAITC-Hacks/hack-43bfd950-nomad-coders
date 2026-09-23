$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"
Set-NodeRuntime
Invoke-Checked (Get-ProjectPython) @((Join-Path $ProjectRoot 'backend/scripts/export_contract.py'))
Invoke-Checked (Get-ProjectPython) @((Join-Path $ProjectRoot 'backend/scripts/export_fixtures.py'))
Invoke-Npm -NpmArguments @('run', 'contracts')
