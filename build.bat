@echo off
echo Instalando dependencias de Python...
pip install -r requirements.txt

echo Limpiando compilaciones previas...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist sysnode.spec del sysnode.spec

echo Compilando SysNode Desktop con PyInstaller para Windows...
:: --onefile: Crear un solo ejecutable (.exe)
:: --noconsole: No mostrar terminal negra de fondo
:: --add-data: Usamos punto y coma (;) en Windows en lugar de (:)
python -m PyInstaller --onefile --noconsole ^
    --name sysnode ^
    --hidden-import PIL._tkinter_finder ^
    --icon "sysnode\ui\assets\icons\home.png" ^
    --add-data "sysnode\ui\assets\icons;sysnode\ui\assets\icons" ^
    --add-data "sysnode\web;sysnode\web" ^
    main.py

echo.
echo ¡Compilación exitosa! El ejecutable sysnode.exe está en la carpeta 'dist\'.
pause
