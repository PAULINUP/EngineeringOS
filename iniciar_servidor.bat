@echo off
chcp 65001 >nul
title EngineeringOS - Servidor
color 0B

echo ==================================================
echo    EngineeringOS - Servidor de desenvolvimento
echo ==================================================
echo.

:: Configuracoes de desenvolvimento (SQLite local, sem Docker)
set EOS_ENV=development
set EOS_RUN_MIGRATIONS=0
set DATABASE_URL=sqlite+aiosqlite:///./engineeringos.db
set EOS_AUTO_IMPORT=1
set EOS_CORS_ORIGINS=*

:: Entra na pasta do backend
cd /d "%~dp0impl"

:: Descobre o IP da rede local (para o APK apontar para este PC)
set LANIP=
for /f "delims=" %%i in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -notmatch '^127\.|^169\.254' } ^| Select-Object -First 1 -ExpandProperty IPAddress)" 2^>nul') do set LANIP=%%i

echo Endereco local (emulador usa 10.0.2.2) : http://127.0.0.1:8000/api
if not "%LANIP%"=="" echo Endereco na rede (celular)         : http://%LANIP%:8000/api
echo.
echo No APK, configure o servidor com UM desses enderecos.
echo Pressione Ctrl+C para parar o servidor.
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000

echo.
echo Servidor encerrado.
pause
