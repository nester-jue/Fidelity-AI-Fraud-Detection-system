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

# Launch frontend in background job or parallel process, then launch backend on port 8010
Start-Process node -ArgumentList "frontend/server.js" -NoNewWindow
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8010 --reload
