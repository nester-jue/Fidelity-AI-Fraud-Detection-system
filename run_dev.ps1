# PowerShell Script to Launch NEXA AI Fraud Detection Platform

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  FIDELITY LIFE ASSURANCE - NEXA AI FRAUD DETECTION PLATFORM" -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Cyan

$env:PYTHONPATH = "."

# 1. Initialize DB and Seed Demo Data
Write-Host "[1/3] Initializing Database & Populating Demonstration Data..." -ForegroundColor Green
python data\seed_db.py

# 2. Run Automated Verification Tests
Write-Host "`n[2/3] Running Automated Quality Assurance Test Suite..." -ForegroundColor Green
pytest tests\test_system.py -q

# 3. Start Servers
Write-Host "`n[3/3] Service Endpoints:" -ForegroundColor Green
Write-Host "  • Frontend Dashboard UI: http://localhost:5174" -ForegroundColor Yellow
Write-Host "  • Backend Service UI:    http://localhost:8010" -ForegroundColor Yellow
Write-Host "  • OpenAPI Swagger Specs: http://localhost:8010/docs" -ForegroundColor Yellow
Write-Host "`nDefault Demonstration Accounts:" -ForegroundColor Gray
Write-Host "  • System Admin:         admin / AdminPass123!" -ForegroundColor White
Write-Host "  • Claims Officer:       claims.officer / OfficerPass123!" -ForegroundColor White
Write-Host "  • Claims Manager:       claims.manager / ManagerPass123!" -ForegroundColor White
Write-Host "  • Fraud Investigator:   investigator / Investigate123!" -ForegroundColor White
Write-Host "  • Compliance Officer:   compliance / Compliance123!" -ForegroundColor White
Write-Host "  • Executive Management: executive / Executive123!`n" -ForegroundColor White

# Start the API first, wait until it answers, then start the frontend proxy.
# Starting both at once made the first sign-in attempt race the backend startup
# and produced a misleading "Failed to fetch" error in the browser.
$env:PYTHONPATH = "."
$api = Start-Process python -ArgumentList "-m uvicorn backend.app.main:app --host 0.0.0.0 --port 8010 --reload" -PassThru
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:8010/health" -UseBasicParsing -TimeoutSec 2
    if ($health.StatusCode -eq 200) { $ready = $true; break }
  } catch { }
}
if (-not $ready) {
  Write-Host "ERROR: Backend did not become ready on http://127.0.0.1:8010/health" -ForegroundColor Red
  Write-Host "Check the API terminal for startup errors. The frontend was not started." -ForegroundColor Red
  exit 1
}
Write-Host "Backend ready. Starting frontend proxy..." -ForegroundColor Green
Start-Process node -ArgumentList "frontend/server.js" -NoNewWindow
try {
  while (-not $api.HasExited) { Start-Sleep -Seconds 2 }
} finally {
  if (-not $api.HasExited) { Stop-Process -Id $api.Id -Force }
}
