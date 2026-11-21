@echo off
chcp 65001 >nul
title Testar o MeshDeck (sem gerar .exe)
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERRO] Nao encontrei o Python neste PC.
    echo Instale pelo site python.org e marque "Add python.exe to PATH".
    pause
    exit /b
)

%PY% -c "import PySide6, OpenGL, numpy" >nul 2>nul
if errorlevel 1 (
    echo Instalando as bibliotecas - so na primeira vez...
    %PY% -m pip install pyside6 PyOpenGL numpy
    if errorlevel 1 goto erro
)

echo Abrindo o MeshDeck...
%PY% "MeshDeck.py" "exemplo_rosquinha.stl"
if errorlevel 1 goto erro
exit /b

:erro
echo.
echo [ERRO] Algo deu errado. Tire um print desta janela e me mande.
pause
