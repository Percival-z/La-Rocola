@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Bot DS - Detener

set "FORCE="
if /i "%~1"=="force" set "FORCE=1"

rem --- Bot (python -m bot.main) ---
set "BOT_PID="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'bot\.main' } | ForEach-Object { $_.ProcessId }"`) do set "BOT_PID=%%P"

if not defined BOT_PID goto :sin_bot
if defined FORCE goto :forzar_bot

echo [stop] El bot está corriendo (PID %BOT_PID%).
echo         Opción elegante: ve a la ventana del bot y presiona Ctrl+C
echo         (eso desconecta la voz de Discord al instante).
choice /C SN /M "Forzar la detención ahora"
if errorlevel 2 goto :esperar_bot

:forzar_bot
echo [stop] Deteniendo el bot a la fuerza...
echo         Nota: Discord puede tardar hasta ~1 minuto en sacarlo del canal
echo         de voz; por eso lo recomendado es Ctrl+C en su ventana.
taskkill /PID %BOT_PID% /F >nul 2>&1
ping -n 2 127.0.0.1 >nul
echo [stop] Bot detenido.
goto :servicios

:esperar_bot
echo [stop] Esperando a que cierres el bot con Ctrl+C...
echo         (cierra esta ventana para cancelar; el bot no se toca)
:esperar_loop
tasklist /FI "PID eq %BOT_PID%" 2>nul | findstr /i "python" >nul
if errorlevel 1 (
  echo [stop] Bot detenido.
  goto :servicios
)
ping -n 2 127.0.0.1 >nul
goto :esperar_loop

:sin_bot
echo [stop] Bot no estaba corriendo.

:servicios
rem --- Lavalink ---
set "LAVA_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /c:":2333 " ^| findstr "LISTENING"') do set "LAVA_PID=%%P"
if not defined LAVA_PID (
  echo [stop] Lavalink no estaba corriendo.
) else (
  taskkill /PID %LAVA_PID% /F >nul 2>&1
  echo [stop] Lavalink detenido.
)

rem --- Tokener de Spotify ---
set "TOK_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /c:":2334 " ^| findstr "LISTENING"') do set "TOK_PID=%%P"
if not defined TOK_PID (
  echo [stop] Tokener de Spotify no estaba corriendo.
) else (
  taskkill /PID %TOK_PID% /F >nul 2>&1
  echo [stop] Tokener detenido.
)

echo.
echo [stop] Todo detenido.
pause
exit /b 0
