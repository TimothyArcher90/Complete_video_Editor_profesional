@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Procesando los videos nuevos de INPUT_AQUI ...
python -m mw_editor entrada
echo.
echo Si todo salio bien, dile a Claude: "ya deje el video". Seguira con plan, mapas, miniaturas y copy.
pause
