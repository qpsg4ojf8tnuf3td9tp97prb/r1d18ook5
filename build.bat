@echo off
setlocal

set "WORKSPACE=%~dp0"

if "%~1"=="" (
    set "OUTPUT_DIR=%WORKSPACE%build"
) else (
    set "OUTPUT_DIR=%~1"
)

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

call %WORKSPACE%.venv\Scripts\activate.bat

pushd "%WORKSPACE%src"

call nuitka --standalone --onefile --follow-imports --clang --lto=yes --remove-output --assume-yes-for-downloads --python-flag=nosite --python-flag=noasserts --windows-console-mode=hide --include-package=websockets --include-data-dir=inject=inject --output-dir="%OUTPUT_DIR%" inject.py

call nuitka --standalone --onefile --follow-imports --clang --lto=yes --remove-output --assume-yes-for-downloads --python-flag=nosite --python-flag=noasserts --windows-console-mode=disable --windows-uac-admin --enable-plugin=tk-inter --output-dir="%OUTPUT_DIR%" patch.py

popd
endlocal