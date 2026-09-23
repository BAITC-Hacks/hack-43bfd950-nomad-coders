$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"
Set-NodeRuntime
Invoke-Npm -NpmArguments @('run', 'build')
