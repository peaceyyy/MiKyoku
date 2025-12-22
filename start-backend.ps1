# Quick Start Script for Backend

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  AniMiKyoku Backend Startup" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the correct directory
if (-Not (Test-Path ".\backend\main.py")) {
    Write-Host "❌ Error: Please run this script from the project root directory" -ForegroundColor Red
    Write-Host "   Expected to find: .\backend\main.py" -ForegroundColor Yellow
    exit 1
}

# Check if .env exists
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

# Check if requirements are installed
Write-Host "📦 Checking dependencies..." -ForegroundColor Cyan
try {
    $pipList = pip list 2>$null
    
    $requiredPackages = @(
        "fastapi",
        "uvicorn",
        "httpx",
        "google-genai",
        "python-dotenv"
    )
    
    $missingPackages = @()
    foreach ($package in $requiredPackages) {
        if (-Not ($pipList -match $package)) {
            $missingPackages += $package
        }
    }
    
    if ($missingPackages.Count -gt 0) {
        Write-Host "   ⚠️  Missing packages: $($missingPackages -join ', ')" -ForegroundColor Yellow
        Write-Host ""
        $response = Read-Host "   Install missing packages? (y/n)"
        
        if ($response -eq 'y' -or $response -eq 'Y') {
            Write-Host "   Installing dependencies..." -ForegroundColor Cyan
            pip install -r .\backend\requirements.txt
            Write-Host "   ✅ Dependencies installed" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  Backend may not work without dependencies" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   ✅ All dependencies installed" -ForegroundColor Green
    }
} catch {
    Write-Host "   ⚠️  Could not check dependencies" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Starting Backend Server" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Server will start at: http://localhost:8000" -ForegroundColor Green
Write-Host "📚 API Docs available at: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Change to backend directory and run server
Set-Location -Path ".\backend"
python main.py
