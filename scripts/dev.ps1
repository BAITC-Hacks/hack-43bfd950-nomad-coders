param([ValidateSet('backend', 'frontend')][string]$Target = 'backend', [switch]$Demo)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"
if ($Target -eq 'frontend') {
    Set-NodeRuntime
    Invoke-Npm -NpmArguments @('run', 'dev')
} else {
    $env:NOMAD_DEMO = $(if ($Demo) { '1' } else { '0' })
    Push-Location (Join-Path $ProjectRoot 'backend')
    try { Invoke-Checked (Get-ProjectPython) @('-m', 'uvicorn', 'app.main:create_app', '--factory', '--host', '127.0.0.1', '--port', '8000', '--reload') }
    finally { Pop-Location }
}
