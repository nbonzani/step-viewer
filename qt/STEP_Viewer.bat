@echo off
rem Lance le viewer PyQt6 + OCP avec l'environnement virtuel du projet (sans console).
set "ROOT=%~dp0.."
start "" "%ROOT%\.venv\Scripts\pythonw.exe" "%~dp0step_viewer_qt.py" %*
