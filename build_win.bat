@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ==== ПАПКИ ВЫХОДА ====
set DIST=build\win
set WORK=build\_work
set SPEC=build\_spec

REM ==== (опционально) иконка GUI ====
set ICON=Monkey-Selfie.ico

REM ==== ПОДГОТОВКА ====
if exist "%DIST%" rmdir /s /q "%DIST%"
if exist "%WORK%" rmdir /s /q "%WORK%"
if exist "%SPEC%" rmdir /s /q "%SPEC%"
mkdir "%DIST%" 2>nul
mkdir "%WORK%" 2>nul
mkdir "%SPEC%" 2>nul

REM ==== ПРОВЕРКА VENV И УСТАНОВКА ЗАВИСИМОСТЕЙ (можно закомментить) ====
where python >nul 2>&1
if errorlevel 1 (
  echo Python не найден в PATH. Активируй venv и запусти батник снова.
  exit /b 1
)

echo [0/3] Installing/Updating build deps (pyinstaller, mss, pillow, pynput)...
python -m pip install -U pyinstaller mss pillow pynput >nul

REM ==== ПАРАМЕТР ИКОНКИ (если файл существует) ====
set ICONARG=
if exist "%ICON%" (
  set ICONARG=--icon "%ICON%"
) else (
  echo [info] Иконка "%ICON%" не найдена, сборка без иконки.
)

REM ==== 1) RECORDER (консольный) ====
echo [1/3] Building recorder (datagrabber_69)...
pyinstaller --clean --noconfirm ^
  --console ^
  --name datagrabber_69 ^
  --distpath "%DIST%" --workpath "%WORK%" --specpath "%SPEC%" ^
  --collect-all mss ^
  --collect-all PIL ^
  --hidden-import pynput.keyboard ^
  --hidden-import pynput.mouse ^
  datagrabber_69.py

if errorlevel 1 (
  echo Ошибка сборки recorder. Прерывание.
  exit /b 1
)

REM ==== 2) GUI (без консоли) ====
echo [2/3] Building GUI (TkDatasetRecorder)...
pyinstaller --clean --noconfirm ^
  --windowed ^
  --name TkDatasetRecorder ^
  --distpath "%DIST%" --workpath "%WORK%" --specpath "%SPEC%" ^
  %ICONARG% ^
  tk_dataset_recorder.py

if errorlevel 1 (
  echo Ошибка сборки GUI. Прерывание.
  exit /b 1
)

REM ==== 3) Положить рекордер рядом с GUI ====
echo [3/3] Placing recorder next to GUI...
if not exist "%DIST%\TkDatasetRecorder" (
  echo Папка GUI не найдена. Что-то пошло не так.
  exit /b 1
)
copy /Y "%DIST%\datagrabber_69\datagrabber_69.exe" "%DIST%\TkDatasetRecorder\" >nul
if errorlevel 1 (
  echo Не удалось скопировать datagrabber_69.exe рядом с GUI.
  exit /b 1
)

echo.
echo DONE ✅
echo Launch: "%DIST%\TkDatasetRecorder\TkDatasetRecorder.exe"
endlocal
