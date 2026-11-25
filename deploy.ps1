# Quick Deployment to DigitalOcean
# Run this after setting up your DO account and doctl

Write-Host "🚀 AniMiKyoku Deployment Script" -ForegroundColor Cyan
Write-Host ""

# Check if doctl is installed
if (-not (Get-Command doctl -ErrorAction SilentlyContinue)) {
    Write-Host "❌ doctl not found. Installing..." -ForegroundColor Yellow
    winget install doctl
    Write-Host "✅ doctl installed. Please restart PowerShell and run this script again." -ForegroundColor Green
    exit
}

# Check authentication
Write-Host "🔐 Checking authentication..." -ForegroundColor Yellow
$authCheck = doctl auth list 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Not authenticated. Run: doctl auth init" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Authenticated" -ForegroundColor Green
Write-Host ""

# Pre-flight checks
Write-Host "📋 Pre-flight Checks..." -ForegroundColor Yellow

# Check if .do/app.yaml exists
if (-not (Test-Path ".do\app.yaml")) {
    Write-Host "❌ .do/app.yaml not found!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Configuration file found" -ForegroundColor Green

# Check if Dockerfile exists
if (-not (Test-Path "Dockerfile")) {
    Write-Host "❌ Dockerfile not found!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Dockerfile found" -ForegroundColor Green

# Check environment variables
if (-not $env:GEMINI_API_KEY) {
    Write-Host "⚠️  GEMINI_API_KEY not set in environment" -ForegroundColor Yellow
    $geminiKey = Read-Host "Enter your GEMINI_API_KEY (or press Enter to skip)"
    if ($geminiKey) {
        $env:GEMINI_API_KEY = $geminiKey
    }
}

Write-Host ""
Write-Host "🏗️  Building and Testing Locally First..." -ForegroundColor Cyan

# Build Docker image
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t animikyoku-test .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker build successful" -ForegroundColor Green

# Ask if user wants to test locally
$testLocal = Read-Host "Test locally before deploying? (y/N)"
if ($testLocal -eq 'y' -or $testLocal -eq 'Y') {
    Write-Host "🧪 Starting local test server on port 8000..." -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop when done testing" -ForegroundColor Yellow
    Write-Host "Test at: http://localhost:8000/health" -ForegroundColor Cyan
    Write-Host ""
    
    docker run -p 8000:8000 -e GEMINI_API_KEY="$env:GEMINI_API_KEY" animikyoku-test
    
    Write-Host ""
    Write-Host "Local test completed." -ForegroundColor Green
}

Write-Host ""
$deploy = Read-Host "Ready to deploy to DigitalOcean? (y/N)"

if ($deploy -ne 'y' -and $deploy -ne 'Y') {
    Write-Host "Deployment cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "🚀 Deploying to DigitalOcean..." -ForegroundColor Cyan

# Update app.yaml with GitHub repo (prompt user)
$repoName = Read-Host "Enter your GitHub username/repo (e.g., username/AniMiKyoku)"
if ($repoName) {
    (Get-Content ".do\app.yaml") -replace "YOUR_USERNAME/AniMiKyoku", $repoName | Set-Content ".do\app.yaml"
    Write-Host "✅ Updated app.yaml with repo: $repoName" -ForegroundColor Green
}

# Create app
Write-Host "Creating app on DigitalOcean..." -ForegroundColor Yellow
$createOutput = doctl apps create --spec .do\app.yaml --wait 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ App creation failed!" -ForegroundColor Red
    Write-Host $createOutput
    exit 1
}

# Extract app ID from output
$appId = ($createOutput | Select-String -Pattern "ID:\s+(\S+)").Matches.Groups[1].Value

if (-not $appId) {
    Write-Host "⚠️  Could not extract app ID. Getting list..." -ForegroundColor Yellow
    doctl apps list
    $appId = Read-Host "Enter the app ID from the list above"
}

Write-Host "✅ App created: $appId" -ForegroundColor Green
Write-Host ""

# Set secret environment variable
if ($env:GEMINI_API_KEY) {
    Write-Host "🔐 Setting GEMINI_API_KEY..." -ForegroundColor Yellow
    doctl apps update $appId --spec .do\app.yaml
    # Note: Secrets must be set via UI or doctl apps create-deployment
    Write-Host "⚠️  Please set GEMINI_API_KEY in DigitalOcean dashboard:" -ForegroundColor Yellow
    Write-Host "   https://cloud.digitalocean.com/apps/$appId/settings" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "📊 Getting app details..." -ForegroundColor Yellow
doctl apps get $appId

Write-Host ""
Write-Host "📝 Following deployment logs..." -ForegroundColor Yellow
Write-Host "(Press Ctrl+C to stop following, app will continue deploying)" -ForegroundColor Gray
Write-Host ""

doctl apps logs $appId --follow

Write-Host ""
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Visit: https://cloud.digitalocean.com/apps/$appId" -ForegroundColor White
Write-Host "2. Set GEMINI_API_KEY in Settings → Environment Variables" -ForegroundColor White
Write-Host "3. Wait for build to complete (~5-10 minutes)" -ForegroundColor White
Write-Host "4. Test your API at the provided URL" -ForegroundColor White
Write-Host ""
Write-Host "Monitor deployment:" -ForegroundColor Cyan
Write-Host "   doctl apps logs $appId --follow" -ForegroundColor White
Write-Host ""
Write-Host "View app details:" -ForegroundColor Cyan
Write-Host "   doctl apps get $appId" -ForegroundColor White
Write-Host ""
Write-Host "🎉 Happy deploying!" -ForegroundColor Green
