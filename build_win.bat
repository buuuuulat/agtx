REM активируй окружение
.\.venv\Scripts\activate
pip install -U pyinstaller mss pillow pynput

REM создадим чистые папки
set DIST=build\win
set WORK=build\_work
set SPEC=build\_spec
if exist "%DIST%" rmdir /s /q "%DIST%"
if exist "%WORK%" rmdir /s /q "%WORK%"
if exist "%SPEC%" rmdir /s /q "%SPEC%"
mkdir "%DIST%" & mkdir "%WORK%" & mkdir "%SPEC%"

REM 1) recorder (консольный) — с hidden-import/collect
pyinstaller --clean --noconfirm ^
  --console ^
  --name datagrabber_69 ^
  --distpath "%DIST%" --workpath "%WORK%" --specpath "%SPEC%" ^
  --hidden-import pynput ^
  --hidden-import pynput.keyboard ^
  --hidden-import pynput.mouse ^
  --collect-submodules pynput ^
  --collect-submodules PIL ^
  --collect-submodules mss ^
  datagrabber_69.py

REM 2) GUI (окно, без консоли) — ему обычно не нужны эти пакеты
pyinstaller --clean --noconfirm ^
  --windowed ^
  --name TkDatasetRecorder ^
  --distpath "%DIST%" --workpath "%WORK%" --specpath "%SPEC%" ^
  tk_dataset_recorder.py

REM 3) Положим helper рядом с GUI
copy /Y "%DIST%\datagrabber_69\datagrabber_69.exe" "%DIST%\TkDatasetRecorder\" >nul

echo DONE
echo Запуск: "%DIST%\TkDatasetRecorder\TkDatasetRecorder.exe"
