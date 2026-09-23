$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Команда завершилась с ошибкой: $Executable $Arguments" }
}

function Get-NodeRuntime {
    $candidates = @($env:NOMAD_NODE)
    $systemNode = Get-Command node -ErrorAction SilentlyContinue
    if ($systemNode) { $candidates += $systemNode.Source }
    $candidates += Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $version = (& $candidate --version).TrimStart('v')
            if ([version]$version -ge [version]'22.12.0') { return $candidate }
        }
    }
    throw 'Нужен Node.js 22.12+ (команда использует Node 24). Установите его или задайте NOMAD_NODE.'
}

function Get-NpmCli {
    param([string]$Node)
    $candidates = @($env:NOMAD_NPM_CLI, (Join-Path (Split-Path $Node) 'node_modules/npm/bin/npm-cli.js'))
    $systemNpm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($systemNpm) { $candidates += Join-Path (Split-Path $systemNpm.Source) 'node_modules/npm/bin/npm-cli.js' }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    throw 'Не найден npm-cli.js. Переустановите Node.js с npm или задайте NOMAD_NPM_CLI.'
}

function Set-NodeRuntime {
    $script:NodeExe = Get-NodeRuntime
    $script:NpmCli = Get-NpmCli $script:NodeExe
    $env:Path = (Split-Path $script:NodeExe) + [IO.Path]::PathSeparator + $env:Path
}

function Invoke-Npm {
    param([string[]]$NpmArguments)
    Invoke-Checked $script:NodeExe (@($script:NpmCli, '--prefix', (Join-Path $ProjectRoot 'frontend')) + $NpmArguments)
}

function Get-ProjectPython {
    $path = Join-Path $ProjectRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $path)) { throw 'Сначала выполните scripts/setup.ps1' }
    return $path
}
