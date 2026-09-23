param(
    [Parameter(Mandatory=$true)][ValidateSet('systeme','iek')][string]$Supplier,
    [Parameter(Mandatory=$true)][string]$Archive,
    [string]$AsOf
)
. "$PSScriptRoot/common.ps1"
$archivePath = (Resolve-Path -LiteralPath $Archive).Path
$pythonArgs = @('-m', 'app.import_local', '--supplier', $Supplier, '--archive', $archivePath)
if ($AsOf) { $pythonArgs += @('--as-of', $AsOf) }
Push-Location "$ProjectRoot/backend"
try { Invoke-Checked (Get-ProjectPython) $pythonArgs }
finally { Pop-Location }
