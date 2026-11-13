param([string]$PythonExe = '')
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot

if ($PythonExe) {
    $pythonCommand = $PythonExe
    $pythonArguments = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = 'py'
    $pythonArguments = @('-3')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = 'python'
    $pythonArguments = @()
} else {
    throw 'Instala Python 3.10 o superior y vuelve a ejecutar preparar.ps1.'
}
& $pythonCommand @pythonArguments -c "import sys; assert sys.version_info >= (3, 10), 'Se requiere Python 3.10 o superior'; print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw 'No fue posible ejecutar Python. Usa -PythonExe con la ruta de python.exe.' }

foreach ($component in @('02_backend_api', '01_frontend_web', '03_analitica_dashboard')) {
    $componentPath = Join-Path $projectRoot $component
    $environmentPath = Join-Path $componentPath '.venv'
    $componentPython = Join-Path $environmentPath 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $componentPython)) {
        Write-Host "Creando entorno de $component..."
        & $pythonCommand @pythonArguments -m venv $environmentPath
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno de $component." }
    }
    & $componentPython -m pip install --disable-pip-version-check -r (Join-Path $componentPath 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias de $component." }
}

$backendPython = Join-Path $projectRoot '02_backend_api\.venv\Scripts\python.exe'
& $backendPython -B (Join-Path $projectRoot '02_backend_api\init_db.py')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo inicializar SQLite.' }
& $backendPython -B (Join-Path $projectRoot '02_backend_api\seed_demo.py')
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar los datos de demostracion.' }
Write-Host 'Preparacion terminada. Ejecuta iniciar.ps1 para abrir las tres aplicaciones.'
