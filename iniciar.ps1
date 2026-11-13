param([switch]$SinNavegador)
$ErrorActionPreference = 'Stop'
$projectPython = Join-Path $PSScriptRoot '02_backend_api\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Primero ejecuta preparar.ps1.'
}
$launcherArguments = @('-B', (Join-Path $PSScriptRoot 'iniciar.py'))
if ($SinNavegador) { $launcherArguments += '--sin-navegador' }
& $projectPython @launcherArguments
exit $LASTEXITCODE
