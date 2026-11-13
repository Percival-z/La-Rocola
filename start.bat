@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title La Rocola - Bot de Discord (Windows)

echo ============================================================
echo  Bot DS - arranque en Windows (tokener + Lavalink + bot)
echo ============================================================
echo.

if not exist ".env" (
  echo [start] ERROR: falta el archivo .env con el token de Discord.
  goto :fail
)

rem --- ¿El bot ya está corriendo? (con un mismo token solo puede haber uno) ---
set "BOT_PID="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'bot\.main' } | ForEach-Object { $_.ProcessId }"`) do set "BOT_PID=%%P"
if not defined BOT_PID goto :bot_libre
echo [start] El bot ya está corriendo (PID %BOT_PID%).
echo         Cierra esa ventana antes de arrancar de nuevo.
goto :fail

:bot_libre
rem --- Entorno virtual: se crea solo en el primer arranque ---
if exist ".venv\Scripts\python.exe" goto :deps
if exist ".venv" (
  echo [start] El .venv actual es de Linux; lo recreo para Windows...
  rmdir /s /q ".venv"
)
echo [start] Creando el entorno virtual (.venv)...
py -3.11 -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto :deps
py -3 -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto :deps
python -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto :deps
echo [start] ERROR: no pude crear el .venv.
echo         Instala Python 3.11+ desde https://www.python.org/downloads/
echo         (marca "Add python.exe to PATH") y vuelve a ejecutar start.bat.
goto :fail

:deps
if not exist logs mkdir logs
set "PY=%CD%\.venv\Scripts\python.exe"
echo [start] Verificando dependencias (pip)...
"%PY%" -m pip install -r requirements.txt --disable-pip-version-check >"logs\pip.log" 2>&1
if errorlevel 1 (
  echo [start] ERROR: falló la instalación de dependencias. Revisa logs\pip.log
  goto :fail
)

rem --- Java 21 para Lavalink (local -> JAVA_HOME -> PATH) ---
set "JAVA_CHECK="
set "JAVA_START="
if exist "%CD%\jdk\bin\java.exe" (
  set "JAVA_CHECK=%CD%\jdk\bin\java.exe"
  set "JAVA_START=..\jdk\bin\java.exe"
)
if defined JAVA_CHECK goto :java_ver
if defined JAVA_HOME if exist "%JAVA_HOME%\bin\java.exe" (
  set "JAVA_CHECK=%JAVA_HOME%\bin\java.exe"
  set "JAVA_START=%JAVA_HOME%\bin\java.exe"
)
if defined JAVA_CHECK goto :java_ver
where java >nul 2>nul
if errorlevel 1 goto :no_java
set "JAVA_CHECK=java"
set "JAVA_START=java"

:java_ver
"%JAVA_CHECK%" -version 2>&1 | findstr /r /c:"[2-9][0-9]\." >nul
if errorlevel 1 goto :java_viejo

rem --- Tokener de Spotify (puerto 2334) ---
netstat -ano | findstr /c:":2334 " | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo [start] Tokener de Spotify ya está corriendo.
) else (
  echo [start] Arrancando tokener de Spotify...
  start "Tokener Spotify" /min /d tools cmd /c ""..\.venv\Scripts\python.exe" spotify_tokener.py >tokener.log 2>&1"
  ping -n 3 127.0.0.1 >nul
)

rem --- Credenciales de Spotify para Lavalink (application.yml usa ${SPOTIFY_CLIENT_ID:}) ---
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
  if /i "%%A"=="SPOTIFY_CLIENT_ID" set "SPOTIFY_CLIENT_ID=%%B"
  if /i "%%A"=="SPOTIFY_CLIENT_SECRET" set "SPOTIFY_CLIENT_SECRET=%%B"
  if /i "%%A"=="LAVA_LINK_PASSWORD" set "LAVA_LINK_PASSWORD=%%B"
)

rem --- Lavalink (puerto 2333) ---
netstat -ano | findstr /c:":2333 " | findstr "LISTENING" >nul
if not errorlevel 1 goto :lavalink_ok
echo [start] Arrancando Lavalink...
start "Lavalink" /min /d lavalink cmd /c ""%JAVA_START%" -Xmx512M -jar Lavalink.jar >lavalink.log 2>&1"
set /a _W=0

:wait_lava
netstat -ano | findstr /c:":2333 " | findstr "LISTENING" >nul
if not errorlevel 1 goto :lavalink_ok
set /a _W+=1
if %_W% geq 60 goto :lavalink_fail
ping -n 2 127.0.0.1 >nul
goto :wait_lava

:lavalink_fail
echo [start] ERROR: Lavalink no abrió el puerto 2333.
echo         Revisa lavalink\lavalink.log (¿el Java no es 21+? ¿falta el .jar?)
goto :fail

:lavalink_ok
echo [start] Lavalink escuchando en 127.0.0.1:2333

rem --- Bot: en primer plano, en esta misma ventana ---
echo.
echo [start] Arrancando el bot...
echo         Para detenerlo con cierre elegante: presiona Ctrl+C aquí.
echo         (si Windows pregunta "¿Terminar el lote de trabajo?", responde N)
echo.
"%PY%" -m bot.main
echo.
echo [start] Bot detenido. Lavalink y el tokener siguen corriendo:
echo         ejecuta stop.bat para detenerlos también.
pause
exit /b 0

:no_java
echo [start] ERROR: no encontré un Java 21 para Windows.
echo         Opción A: descarga el .zip de Temurin 21 en
echo           https://adoptium.net/temurin/releases/
echo         y extráelo aquí dentro para que exista .\jdk\bin\java.exe
echo         (la carpeta jdk\ incluida es de Linux: no sirve en Windows).
echo         Opción B: instala un JDK 21 y déjalo en el PATH o en JAVA_HOME.
goto :fail

:java_viejo
echo [start] ERROR: el Java que encontré no parece ser 21+ (o no funciona).
echo         Lavalink 4 necesita Java 21 o superior.
echo         Instala Temurin 21 (ver arriba) o arregla .\jdk o JAVA_HOME.
goto :fail

:fail
echo.
pause
exit /b 1
