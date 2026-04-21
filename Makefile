SHELL := powershell.exe
.SHELLFLAGS := -NoProfile -Command

PYTHON := .\.venv\Scripts\python.exe
APP_NAME := gbf-macro
SPEC_FILE := $(APP_NAME).spec
PYINSTALLER := $(PYTHON) -m PyInstaller

.PHONY: bootstrap-build exe clean

bootstrap-build:
	@if (-not (Test-Path '$(PYTHON)')) { throw 'Missing virtualenv python at $(PYTHON)' }
	$(PYTHON) -m ensurepip --upgrade
	$(PYTHON) -m pip install --upgrade pyinstaller

exe:
	@if (-not (Test-Path '$(PYTHON)')) { throw 'Missing virtualenv python at $(PYTHON)' }
	$(PYINSTALLER) --noconfirm --clean --windowed --onedir --name $(APP_NAME) --add-data "templates;templates" main.py

clean:
	@if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
	@if (Test-Path 'dist') { Remove-Item -Recurse -Force 'dist' }
	@if (Test-Path '$(SPEC_FILE)') { Remove-Item -Force '$(SPEC_FILE)' }
