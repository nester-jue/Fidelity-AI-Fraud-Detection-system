# init_environment.ps1
# PowerShell script to set up a Python virtual environment and install backend dependencies.

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $projectRoot

# Create virtual environment in .venv folder
python -m venv .venv

# Activate the environment
& .\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install backend requirements
python -m pip install -r backend/requirements.txt

Write-Host "Environment setup complete. Use '.\.venv\Scripts\Activate.ps1' to activate the venv."
