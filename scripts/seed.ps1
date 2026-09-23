. "$PSScriptRoot/common.ps1"
$env:NOMAD_DEMO = '1'
Push-Location "$ProjectRoot/backend"
try { Invoke-Checked (Get-ProjectPython) @('-m', 'app.seed') }
finally { Pop-Location }
