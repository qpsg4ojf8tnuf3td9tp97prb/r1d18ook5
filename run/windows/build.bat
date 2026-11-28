@echo off
setlocal

set "WORKSPACE=%cd%\"

if "%~1"=="" (
    set "OUTPUT_DIR=%WORKSPACE%build"
) else (
    set "OUTPUT_DIR=%~1"
)

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

call %WORKSPACE%.venv\Scripts\activate.bat

pushd "%WORKSPACE%src"

call nuitka --standalone --onefile --follow-imports --clang --lto=yes --remove-output --assume-yes-for-downloads --python-flag=nosite --python-flag=noasserts --windows-console-mode=disable --include-package=websockets --include-data-dir=scripts=scripts --output-dir="%OUTPUT_DIR%" inject.py

popd
endlocal