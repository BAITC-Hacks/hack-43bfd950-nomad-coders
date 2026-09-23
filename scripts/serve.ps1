param([switch]$Demo)
. "$PSScriptRoot/common.ps1"
if (-not (Test-Path "$ProjectRoot/frontend/dist/index.html")) { throw 'Run scripts/build.ps1 first.' }
$env:NOMAD_DEMO = if ($Demo) { '1' } else { '0' }
Push-Location "$ProjectRoot/backend"
try { Invoke-Checked (Get-ProjectPython) @('-m', 'uvicorn', 'app.main:create_app', '--factory', '--host', '127.0.0.1', '--port', '8000') }
finally { Pop-Location }
