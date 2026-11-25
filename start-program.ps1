# Unified Quick Start Script for AniMiKyoku (Backend + Frontend)

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  AniMiKyoku Startup (uv-powered)" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# 1. Directory verification
if (-Not (Test-Path ".\backend\main.py")) {
    Write-Host "❌ Error: Please run this script from the project root directory" -ForegroundColor Red
    Write-Host "   Expected to find: .\backend\main.py" -ForegroundColor Yellow
    exit 1
}

# 2. Check and configure backend environment (.env)
if (-Not (Test-Path ".\backend\.env")) {
    Write-Host "⚠️  .env file not found" -ForegroundColor Yellow
    Write-Host "   Creating from .env.example..." -ForegroundColor Yellow
    Copy-Item ".\backend\.env.example" ".\backend\.env"
    Write-Host "   ✅ Created .env file" -ForegroundColor Green
    Write-Host ""
    Write-Host "   📝 IMPORTANT: Edit backend\.env and add your GEMINI_API_KEY" -ForegroundColor Yellow
    Write-Host "   Press any key to open .env in notepad..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    notepad ".\backend\.env"
    Write-Host ""
} else {
    Write-Host "✅ Found .env file at backend\.env" -ForegroundColor Green
}

# 3. Verify uv package manager is available
Write-Host "⚡ Checking uv..." -ForegroundColor Cyan
$uvCmd = Get-Command "uv" -ErrorAction SilentlyContinue

if (-not $uvCmd) {
    # Check default install location if not yet added to current session's PATH
    $defaultUvPath = Join-Path $HOME ".local\bin\uv.exe"
    if (Test-Path $defaultUvPath) {
        $env:PATH = "$HOME\.local\bin;" + $env:PATH
        $uvCmd = Get-Command "uv" -ErrorAction SilentlyContinue
    }
}

if (-not $uvCmd) {
    Write-Host "❌ Error: 'uv' was not found in PATH." -ForegroundColor Red
    Write-Host "   Install uv via PowerShell with:" -ForegroundColor Yellow
    Write-Host '   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' -ForegroundColor Gray
    exit 1
}

$uvVersion = & uv --version
Write-Host "   ✅ $uvVersion" -ForegroundColor Green

# 4. Synchronize virtual environment with pyproject.toml
Write-Host "📦 Synchronizing dependencies with uv sync..." -ForegroundColor Cyan
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error: uv sync failed. Please check dependencies." -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Environment synchronized" -ForegroundColor Green

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Launching Services" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Backend will start at: http://localhost:8000" -ForegroundColor Green
Write-Host "📚 API Docs available at: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""

# 5. Start frontend in a separate PowerShell window
$projectRoot = Get-Location
$frontendPath = Join-Path $projectRoot "frontend"

if (Test-Path $frontendPath) {
    Write-Host "🚀 Starting frontend in a new PowerShell window..." -ForegroundColor Cyan
    $cmd = "Set-Location -Path '$frontendPath'; npm run dev"
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $cmd -WorkingDirectory $frontendPath
} else {
    Write-Host "⚠️  Frontend folder not found at: $frontendPath" -ForegroundColor Yellow
}

# 6. Run backend server in the current window using uv run
Write-Host "🚀 Starting backend server with uv..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

Set-Location -Path ".\backend"
uv run python main.py
