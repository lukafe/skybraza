# CertiK VASP — aplicação web para clientes (IN 701)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

Write-Host "A instalar dependências (se necessário)..." -ForegroundColor Cyan
python -m pip install -r requirements.txt -q

Write-Host "A iniciar servidor e a abrir o navegador..." -ForegroundColor Green
python serve_web.py
