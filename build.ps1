# Gera o executável (PyInstaller) e o instalador (Inno Setup) do PDFx.
#
#   .\build.ps1                 -> dist\PDFx\PDFx.exe  e  dist\installer\PDFx-Setup-<versão>.exe
#   .\build.ps1 -SkipInstaller  -> só o executável
param([switch]$SkipInstaller)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Step([string]$Title, [scriptblock]$Block) {
    Write-Host "==> $Title" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "Falhou: $Title (código $LASTEXITCODE)" }
}

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Invoke-Step "Criando ambiente virtual (.venv)" { python -m venv .venv }
}

Invoke-Step "Instalando dependências" {
    & $py -m pip install --disable-pip-version-check -q -r requirements.txt -r requirements-dev.txt
}
Invoke-Step "Gerando ícones" { & $py tools\make_icon.py }

$version = (& $py -c "import pdfx; print(pdfx.__version__)").Trim()
Invoke-Step "Empacotando PDFx $version com PyInstaller" { & $py -m PyInstaller pdfx.spec --noconfirm --clean --log-level WARN }

if ($SkipInstaller) {
    Write-Host "Executável pronto: dist\PDFx\PDFx.exe" -ForegroundColor Green
    return
}

$candidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($cmd) { $iscc = $cmd.Source }
}
if (-not $iscc) {
    Write-Warning "Inno Setup 6 não encontrado. Instale com:  winget install JRSoftware.InnoSetup"
    exit 1
}

Invoke-Step "Gerando instalador" { & $iscc "/Qp" "/DAppVersion=$version" "installer\pdfx.iss" }
Write-Host "Instalador pronto: dist\installer\PDFx-Setup-$version.exe" -ForegroundColor Green
