param(
    [ValidateSet("bootstrap-build", "exe", "clean")]
    [string]$Task = "exe"
)

$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"
$appName = "gbf-macro"
$specFile = "$appName.spec"

function Assert-Python {
    if (-not (Test-Path $python)) {
        throw "Missing virtualenv python at $python"
    }
}

function Invoke-BootstrapBuild {
    Assert-Python
    & $python -m ensurepip --upgrade
    & $python -m pip install --upgrade pyinstaller
}

function Invoke-ExeBuild {
    Assert-Python
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --onedir `
        --name $appName `
        --add-data "templates;templates" `
        main.py
}

function Invoke-Clean {
    if (Test-Path "build") {
        Remove-Item -Recurse -Force "build"
    }
    if (Test-Path "dist") {
        Remove-Item -Recurse -Force "dist"
    }
    if (Test-Path $specFile) {
        Remove-Item -Force $specFile
    }
}

switch ($Task) {
    "bootstrap-build" { Invoke-BootstrapBuild }
    "exe" { Invoke-ExeBuild }
    "clean" { Invoke-Clean }
}
