# UltraDown – Windows Installer

This folder contains scripts to package the app into a Windows installer.

## Prerequisites
- Windows 10/11
- Python 3.9+ (your virtualenv is fine)
- Inno Setup 6
  - Install via winget: `winget install Jrsoftware.InnoSetup`
  - Or via Chocolatey: `choco install innosetup`

## Build Steps (PowerShell)
```powershell
# from repo root: C:\Users\...\z
# (optional) activate your venv
& .\.venv\Scripts\Activate.ps1

# build
pwsh .\installer\build_installer.ps1

# clean build
pwsh .\installer\build_installer.ps1 -Clean
```

Artifacts:
- PyInstaller output: `dist/UltraDown/UltraDown.exe`
- Installer EXE: `installer/dist/installer/UltraDown-Setup.exe`

## What the installer does
- Installs to `%ProgramFiles%\UltraDown`
- Creates Start Menu and optional Desktop shortcuts
- Launches the app after installation

## App behavior after install
- Launches a local server on `http://localhost:5002`
- Automatically opens your default browser to the UI
- Downloads are stored in the app `downloads/` folder by default (configurable in the UI)

## Notes
- If you change templates, re-run the build so they’re bundled.
- If ports conflict, adjust `port=5002` inside `web_downloader.py`.
