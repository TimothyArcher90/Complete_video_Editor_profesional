@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="" (
  echo Arrastra un video encima de este archivo para editarlo.
  pause
  exit /b 1
)
for /f %%d in ('powershell -nop -c "Get-Date -f dd-MM-yyyy"') do set FECHA=%%d
set "RAIZ=E:\CARPETA OUTPUTS IA 2026\Video con Ia editor\outputs organizados"
if not exist "E:\CARPETA OUTPUTS IA 2026" set "RAIZ=%USERPROFILE%\Downloads\MacroWise_Editados"
set "OUT=%RAIZ%\%FECHA%\%~n1"
echo Editando: %~nx1
echo Salida:   %OUT%
echo (vertical + horizontal; puede tardar unos minutos)
python -m mw_editor editar "%~f1" --out "%OUT%" --nombre "%~n1" --formato ambos --preview
if errorlevel 1 (
  echo.
  echo Algo fallo. Copia el texto de arriba y pasaselo a Claude.
) else (
  echo.
  echo LISTO. Abriendo la carpeta de resultados...
  start "" "%OUT%\06_EXPORT"
)
pause
