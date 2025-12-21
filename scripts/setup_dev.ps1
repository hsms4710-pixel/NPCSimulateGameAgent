# PowerShell development setup script for Windows

Write-Host "Setting up MRAG Enhanced Model development environment..." -ForegroundColor Green

# Check Python version
$pythonVersion = python --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python is not installed or not in PATH. Please install Python 3.9+ first." -ForegroundColor Red
    exit 1
}
Write-Host "Python version: $pythonVersion"

# Create virtual environment
Write-Host "Creating virtual environment..."
python -m venv venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create virtual environment" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..."
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

# Upgrade pip
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
Write-Host "Installing Python dependencies..."
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Create .env file if it doesn't exist
if (!(Test-Path .env)) {
    Write-Host "Creating .env file..."
    Copy-Item .env.example .env -ErrorAction SilentlyContinue
    Write-Host "Please edit .env file with your API keys" -ForegroundColor Yellow
}

# Initialize database
Write-Host "Initializing database..."
python -c "from backend.app.database import init_db; init_db()" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Database initialization skipped (implement when database module is ready)" -ForegroundColor Yellow
}

Write-Host "Development environment setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit .env file with your API keys"
Write-Host "2. Run '.\venv\Scripts\Activate.ps1' to activate the virtual environment"
Write-Host "3. Run 'python backend/app/main.py' to start the server"
Write-Host "4. Or run 'python backend/cli/interface.py' for CLI mode"
