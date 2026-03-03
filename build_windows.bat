@echo off
REM =============================================================================
REM MerlinClaudinator - Windows Build Script
REM =============================================================================
REM Double-cliquez sur ce fichier pour créer l'exécutable Windows.
REM L'exécutable sera créé dans src\dist\MerlinClaudinator.exe
REM =============================================================================

echo ============================================================
echo   MerlinClaudinator - Build Windows
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo X Python n'est pas installe.
    echo.
    echo Telechargez Python depuis: https://python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do echo + %%i

REM Install/upgrade dependencies
echo.
echo Installation des dependances...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller pygame --quiet

echo + Dependances installees
echo.

REM Run the build
echo Lancement du build...
echo.
python build_exe.py

REM Check if build succeeded
if exist "src\dist\MerlinClaudinator.exe" (
    echo.
    echo ============================================================
    echo + BUILD REUSSI!
    echo ============================================================
    echo.
    echo Executable: src\dist\MerlinClaudinator.exe
    echo.

    REM Open the dist folder in Explorer
    explorer src\dist

    echo Le dossier dist a ete ouvert dans l'Explorateur.
    echo.
) else (
    echo.
    echo ============================================================
    echo X BUILD ECHOUE
    echo ============================================================
    echo.
    echo Verifiez les erreurs ci-dessus.
    echo.
)

pause
