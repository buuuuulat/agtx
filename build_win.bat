@echo on
setlocal ENABLEDELAYEDEXPANSION ENABLEEXTENSIONS

REM ===== basic console setup =====
REM (no non-ascii output; keep code page change only to avoid mojibake in paths)
chcp 65001 >nul

REM ===== paths relative to this .bat =====
set "ROOT=%~dp0"
pushd "%ROOT%"

set "DIST=build\win"
set "WORK=build\_work"
set "SPEC=build\_spec"

set "REC_SCRIPT=datagrabber_69.py"
set "REC_NAME=datagrabber_69"

set "GUI_SCRIPT=tk_dataset_recorder.py"
set "GUI_NAME=TkDatasetRecorder"

set "ICON=Monkey-Selfie.ico"

echo [info] ROOT: "%ROOT%"
echo [info] CWD : "%CD%"

REM ===== clean/create folders =====
if exist "%DIST%" rmdir /s /q "%DIST%"
if exist "%WORK%" rmdir /s /q "%WORK%"
if exist "%SPEC%" rmdir /s /q "%SPEC%"
mkdir "%DIST%" 2>nul
mkdir "%WORK%" 2>nul
mkdir "%SPEC%" 2>nul

REM ===== find python (prefer .venv\Scripts\python.exe if present) =====
set "PY=python"
where python >nul 2>&1
if errorlevel 1 (
  if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
  ) else (
    echo [FATAL] python not found in PATH and .venv\Scripts\python.exe does not exist.
    goto :fail
  )
)

"%PY%" --version || goto :fail
"%PY%" -m pip --version || goto :fail

REM ===== upgrade build deps (use module call to avoid PATH issues) =====
echo [0/3] Installing/upgrading build deps...
"%PY%" -m pip install -U pip || goto :fail
"%PY%" -m pip install -U pyinstaller mss pillow pynput || goto :fail
"%PY%" -m PyInstaller --version || goto :fail

REM ===== optional icon =====
set "ICONARG="
if exist "%ICON%" (
  set "ICONARG=--icon %ICON%"
) else (
  echo [info] Icon "%ICON%" not found; building without icon.
)

REM ===== 1) build recorder (console) =====
echo [1/3] Building recorder (%REC_NAME%)...
"%PY%" -m PyInstaller --clean --noconfirm ^
 --console ^
 --name "%REC_NAME%" ^
 --distpath "%DIST%" --workpath "%WORK%" --specpath "%SPEC%" ^
 --collect-all mss ^
 --collect-all PIL ^
 --hidden-import pynput.keyboard ^
 --hidden-import pynput.mouse ^
 "%REC_SCRIPT%"
if errorlevel 1 goto :fail

REM ===== 2) build GUI (windowed) =====
echo [2/3] Building GUI (%GUI_NAME%)...
"%PY%" -m PyInstaller --clean --noconfirm ^
 --windowed ^
 --name "%GUI_NAME%" ^
 --distpath "%DIST%" --workpath "%WORK%" --specpath "%SPEC%" ^
 %ICONARG% ^
 "%GUI_SCRIPT%"
if errorlevel 1 goto :fail

REM ===== 3) place recorder next to GUI =====
echo [3/3] Placing recorder next to GUI...
if not exist "%DIST%\%GUI_NAME%" (
  echo [FATAL] GUI dist folder not found: "%DIST%\%GUI_NAME%".
  goto :fail
)

if not exist "%DIST%\%REC_NAME%\%REC_NAME%.exe" (
  echo [FATAL] Recorder exe not found: "%DIST%\%REC_NAME%\%REC_NAME%.exe".
  goto :fail
)

copy /Y "%DIST%\%REC_NAME%\%REC_NAME%.exe" "%DIST%\%GUI_NAME%\" || goto :fail

echo.
echo DONE ✅
echo Launch: "%DIST%\%GUI_NAME%\%GUI_NAME%.exe"
goto :end

:fail
echo.
echo [BUILD FAILED] errorlevel=%errorlevel%
echo Tips:
echo  - Run this from cmd.exe, not PowerShell. In PS use: .\build_win.bat
echo  - Save file as UTF-8 (no BOM) or ANSI with CRLF.
echo  - Check that %REC_SCRIPT% and %GUI_SCRIPT% exist in the same folder as this .bat.
echo  - If you use a venv, ensure dependencies were installed into it.
pause
:end
popd
endlocal
