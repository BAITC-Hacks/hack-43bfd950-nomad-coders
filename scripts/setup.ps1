param([string]$Python = $env:NOMAD_PYTHON, [switch]$SkipBrowser)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"
Set-NodeRuntime
if (-not $Python) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        # Windows PowerShell can throw on native stderr even with redirection.
        # A missing optional launcher runtime must not prevent the bundled fallback.
        try {
            $found = & $launcher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $found) { $Python = ([string]$found).Trim() }
        } catch {
            $Python = $null
        }
    }
}
if (-not $Python) {
    $bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundled) { $Python = $bundled }
}
if (-not $Python) { throw 'Установите Python 3.12 или передайте -Python с путём к python.exe' }
$version = & $Python -c 'import sys; print(sys.version.split()[0])'
if ($LASTEXITCODE -ne 0 -or $version -notlike '3.12.*') { throw 'Нужен Python 3.12' }
if (-not (Test-Path (Join-Path $ProjectRoot '.venv/Scripts/python.exe'))) {
    Invoke-Checked $Python @('-m', 'venv', (Join-Path $ProjectRoot '.venv'))
}
$pythonExe = Get-ProjectPython
$venvVersion = & $pythonExe -c 'import sys; print(sys.version.split()[0])'
if ($LASTEXITCODE -ne 0 -or $venvVersion -notlike '3.12.*') {
    throw 'Существующая .venv использует другой Python. Сохраните её отдельно и создайте окружение Python 3.12.'
}
Invoke-Checked $pythonExe @('-m', 'pip', 'install', '-r', (Join-Path $ProjectRoot 'backend/requirements.lock'))
Invoke-Npm -NpmArguments @('ci')
if (-not $SkipBrowser) { Invoke-Npm -NpmArguments @('exec', '--', 'playwright', 'install', 'chromium') }
Write-Host 'Окружение готово. Инструкции запуска — в README.md.'
