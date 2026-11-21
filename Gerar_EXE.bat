@echo off
chcp 65001 >nul
title Gerar o Visualizador STL (.exe)
cd /d "%~dp0"

echo ==================================================
echo    Gerando o Visualizador STL (.exe)
echo ==================================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERRO] Nao encontrei o Python neste PC.
    echo Instale pelo site python.org e marque a opcao "Add python.exe to PATH".
    echo Depois rode este arquivo de novo.
    pause
    exit /b
)

echo [1/3] Instalando as bibliotecas (pode demorar na primeira vez)...
%PY% -m pip install --upgrade pyside6 PyOpenGL numpy pyinstaller
if errorlevel 1 goto erro

echo.
echo [2/3] Montando o programa...
%PY% -m PyInstaller --noconfirm --clean --windowed ^
    --name "Visualizador STL" ^
    --icon "icone.ico" ^
    --add-data "icone.ico;." ^
    "Visualizador_STL.py"
if errorlevel 1 goto erro

echo.
echo [3/3] Limpando arquivos temporarios...
rmdir /s /q build >nul 2>nul
del /q "Visualizador STL.spec" >nul 2>nul

echo.
echo ==================================================
echo  PRONTO!
echo  O programa ficou na pasta:  dist\Visualizador STL
echo  Abra o arquivo "Visualizador STL.exe" que esta la.
echo ==================================================
explorer "dist\Visualizador STL"
pause
exit /b

:erro
echo.
echo [ERRO] Algo deu errado. Tire um print desta janela e me mande.
pause
