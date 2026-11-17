# Instalador de Alcalde Digital para Windows.
# Copia el juego a %LOCALAPPDATA%\AlcaldeDigital, descarga uv (con comprobación SHA-256), instala con él un Python 3.13 PRIVADO
# del juego y las bibliotecas (Ursina, psutil), y crea los accesos directos. No toca el Python del sistema ni el PATH.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$UvVersion = '0.13.9'
$origen = Split-Path -Parent $MyInvocation.MyCommand.Path
$destino = Join-Path $env:LOCALAPPDATA 'AlcaldeDigital'

function Paso($texto) { Write-Host ''; Write-Host "==> $texto" -ForegroundColor Yellow }

try {
    Paso 'Copiando el juego'
    New-Item -ItemType Directory -Force -Path $destino | Out-Null
    foreach ($nombre in 'main.py', 'lanzar.py', 'requirements-juego.txt', 'assets', 'backend', 'frontend') {
        $fuente = Join-Path $origen $nombre
        if (-not (Test-Path $fuente)) { throw "Falta '$nombre'. ¿Descomprimiste TODO el .zip antes de instalar? (clic derecho, Extraer todo)" }
        Copy-Item $fuente $destino -Recurse -Force
    }

    Paso 'Descargando el instalador de Python (uv)'
    $arq = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'aarch64' } else { 'x86_64' }
    $herr = Join-Path $destino 'herramientas'
    New-Item -ItemType Directory -Force -Path $herr | Out-Null
    $nombreZip = "uv-$arq-pc-windows-msvc.zip"
    $base = "https://github.com/astral-sh/uv/releases/download/$UvVersion"
    $rutaZip = Join-Path $herr $nombreZip
    Invoke-WebRequest "$base/$nombreZip" -OutFile $rutaZip -UseBasicParsing
    Invoke-WebRequest "$base/$nombreZip.sha256" -OutFile "$rutaZip.sha256" -UseBasicParsing
    $esperado = ((Get-Content "$rutaZip.sha256" -Raw).Trim() -split '\s+')[0].ToLower()
    $real = (Get-FileHash $rutaZip -Algorithm SHA256).Hash.ToLower()
    if ($esperado -ne $real) { throw 'La descarga de uv no coincide con su huella SHA-256. Vuelve a intentarlo o revisa tu conexión.' }
    Expand-Archive $rutaZip -DestinationPath $herr -Force
    $uv = Get-ChildItem $herr -Recurse -Filter uv.exe | Select-Object -First 1 -ExpandProperty FullName
    if (-not $uv) { throw 'No se encontró uv.exe tras descomprimir.' }

    $env:UV_PYTHON_INSTALL_DIR = Join-Path $herr 'python'
    $env:UV_CACHE_DIR = Join-Path $herr 'cache'
    $env:UV_PYTHON_PREFERENCE = 'only-managed'

    Paso 'Instalando Python 3.13 (privado de este juego)'
    & $uv python install 3.13
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar Python.' }

    Paso 'Creando el entorno del juego'
    $entorno = Join-Path $destino 'entorno'
    & $uv venv --python 3.13 --clear $entorno
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno.' }

    Paso 'Instalando las bibliotecas del juego (Ursina y compañía)'
    $pythonExe = Join-Path $entorno 'Scripts\python.exe'
    & $uv pip install --python $pythonExe -r (Join-Path $destino 'requirements-juego.txt')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las bibliotecas.' }

    Paso 'Creando los accesos directos'
    $pythonw = Join-Path $entorno 'Scripts\pythonw.exe'
    $ws = New-Object -ComObject WScript.Shell
    $carpetas = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))
    foreach ($carpeta in $carpetas) {
        $acceso = $ws.CreateShortcut((Join-Path $carpeta 'Alcalde Digital.lnk'))
        $acceso.TargetPath = $pythonw
        $acceso.Arguments = 'lanzar.py'
        $acceso.WorkingDirectory = $destino
        $acceso.Description = 'Alcalde Digital'
        $acceso.Save()
    }

    # Desinstalador
    $desinstalador = @'
$ErrorActionPreference = 'SilentlyContinue'
$destino = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($c in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    Remove-Item (Join-Path $c 'Alcalde Digital.lnk') -Force
}
Write-Host 'Se quitaron los accesos directos. Borrando el juego...'
Start-Process cmd -ArgumentList "/c ping -n 3 127.0.0.1 >nul & rmdir /s /q `"$destino`"" -WindowStyle Hidden
Write-Host 'Listo. Tu partida guardada sigue en la carpeta .alcalde_digital de tu usuario (puedes borrarla desde Ajustes del juego o a mano).'
'@
    Set-Content -Path (Join-Path $destino 'desinstalar.ps1') -Value $desinstalador -Encoding UTF8
    Set-Content -Path (Join-Path $destino 'Desinstalar.bat') -Value "@echo off`r`npowershell -NoProfile -ExecutionPolicy Bypass -File `"%~dp0desinstalar.ps1`"`r`npause" -Encoding ASCII

    Write-Host ''
    Write-Host '=============================================' -ForegroundColor Green
    Write-Host ' Alcalde Digital está instalado.' -ForegroundColor Green
    Write-Host ' Ábrelo desde el icono «Alcalde Digital» del escritorio' -ForegroundColor Green
    Write-Host ' o del menú Inicio.' -ForegroundColor Green
    Write-Host '=============================================' -ForegroundColor Green
    $respuesta = Read-Host '¿Quieres jugar ahora? (S/N)'
    if ($respuesta -match '^[sSyY]') { Start-Process $pythonw -ArgumentList 'lanzar.py' -WorkingDirectory $destino }
}
catch {
    Write-Host ''
    Write-Host "No se pudo completar la instalación: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Revisa tu conexión a internet y vuelve a ejecutar Instalar.bat.' -ForegroundColor Red
    exit 1
}
