# ==============================================================================
# KargoPilot v4.5 - 1-Click Sovereign Self-Hosted PowerShell Installer (Windows)
# ==============================================================================

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "         KargoPilot v4.5 Sovereign Self-Hosted Edition           " -ForegroundColor Cyan
Write-Host "        100% On-Premise | Sıfır Telemetriya | Tam Məxfilik        " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# Check Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Docker Desktop tapılmadı. Zəhmət olmasa Docker quraşdırın." -ForegroundColor Red
    exit 1
}

$DataDir = "$env:USERPROFILE\.kargopilot\data"
Write-Host "[1/4] Məlumat qovluqları yaradılır: $DataDir..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "$DataDir\invoices", "$DataDir\logs", "$DataDir\wa_sessions" | Out-Null

if (-not (Test-Path ".env.sovereign")) {
    Write-Host "[2/4] .env.sovereign üçün 256-bit açarlar generasiya edilir..." -ForegroundColor Cyan
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    
    $rng.GetBytes($bytes)
    $jwtKey = [System.BitConverter]::ToString($bytes).Replace("-","").ToLower()
    $rng.GetBytes($bytes)
    $refreshKey = [System.BitConverter]::ToString($bytes).Replace("-","").ToLower()
    $rng.GetBytes($bytes)
    $vaultKey = [System.BitConverter]::ToString($bytes).Replace("-","").ToLower()

    $content = Get-Content ".env.sovereign.example" -Raw
    $content = $content.Replace("change_me_with_openssl_rand_hex_32_jwt_key", $jwtKey)
    $content = $content.Replace("change_me_with_openssl_rand_hex_32_refresh_key", $refreshKey)
    $content = $content.Replace("change_me_with_openssl_rand_hex_32_aes256_key", $vaultKey)
    Set-Content -Path ".env.sovereign" -Value $content -Encoding utf8
    Write-Host "[OK] .env.sovereign uğurla hazırlandı." -ForegroundColor Green
}

Write-Host "[3/4] Konteynerlər başladılır..." -ForegroundColor Cyan
docker compose -f docker-compose.sovereign.yml up -d --build

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " ✓ KargoPilot v4.5 Sovereign Quraşdırıldı!" -ForegroundColor Green
Write-Host " İdarəetmə Paneli: http://127.0.0.1:48481/admin" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
