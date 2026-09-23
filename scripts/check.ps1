param([switch]$Browser)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"
Set-NodeRuntime
$testTemp = Join-Path ([IO.Path]::GetTempPath()) ('nomad-pytest-' + [guid]::NewGuid().ToString('N'))
Push-Location (Join-Path $ProjectRoot 'backend')
try { Invoke-Checked (Get-ProjectPython) @('-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--basetemp', $testTemp) } finally { Pop-Location }
Invoke-Npm -NpmArguments @('run', 'build')
if ($Browser) { Invoke-Npm -NpmArguments @('run', 'test:e2e') }
