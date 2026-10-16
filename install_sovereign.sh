#!/usr/bin/env bash
# ==============================================================================
# KargoPilot v4.5 - 1-Click Sovereign Self-Hosted Installer
# ==============================================================================
set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "=================================================================="
echo "         KargoPilot v4.5 Sovereign Self-Hosted Edition           "
echo "        100% On-Premise | Sıfır Telemetriya | Tam Məxfilik        "
echo "=================================================================="
echo -e "${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR] Docker quraşdırılmayıb. Zəhmət olmasa əvvəlcə Docker quraşdırın.${NC}"
    exit 1
fi

# Create data directories
DATA_DIR="/data/kargopilot"
echo -e "${CYAN}[1/4] Məlumat qovluqları yaradılır: ${DATA_DIR}...${NC}"
mkdir -p "${DATA_DIR}/invoices" "${DATA_DIR}/logs" "${DATA_DIR}/wa_sessions"

# Generate Cryptographic Keys if .env.sovereign doesn't exist
if [ ! -f .env.sovereign ]; then
    echo -e "${CYAN}[2/4] .env.sovereign üçün kriptoqrafik açarlar generasiya edilir...${NC}"
    JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))')
    REFRESH_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))')
    VAULT_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))')
    
    cp .env.sovereign.example .env.sovereign
    sed -i "s/change_me_with_openssl_rand_hex_32_jwt_key/${JWT_SECRET}/" .env.sovereign
    sed -i "s/change_me_with_openssl_rand_hex_32_refresh_key/${REFRESH_SECRET}/" .env.sovereign
    sed -i "s/change_me_with_openssl_rand_hex_32_aes256_key/${VAULT_KEY}/" .env.sovereign
    echo -e "${GREEN}[OK] .env.sovereign 256-bit AES və Argon2id açarları ilə hazırlandı.${NC}"
else
    echo -e "${AMBER}[INFO] Mövcud .env.sovereign faylı aşkarlandı, toxunulmadı.${NC}"
fi

# Build and start Docker containers
echo -e "${CYAN}[3/4] Konteynerlər başladılır (docker-compose.sovereign.yml)...${NC}"
docker compose -f docker-compose.sovereign.yml build --pull
docker compose -f docker-compose.sovereign.yml up -d

# Health Check verification
echo -e "${CYAN}[4/4] Sistem sağlamlığı yoxlanılır (http://127.0.0.1:48481/healthz)...${NC}"
for i in {1..15}; do
    if curl -s http://127.0.0.1:48481/healthz | grep -q "healthy"; then
        echo -e "${GREEN}=================================================================="
        echo " ✓ KargoPilot v4.5 Sovereign Uğurla Quraşdırıldı və İcra Olunur!"
        echo " URL: http://127.0.0.1:48481/admin"
        echo " FİN Şəbəkəsi & DGK SmartCustoms yerli serverinizdə qorunur."
        echo " Heç bir məlumat KargoPilot mərkəzi serverlərinə ötürülmür."
        echo -e "==================================================================${NC}"
        exit 0
    fi
    sleep 2
done

echo -e "${AMBER}[XƏBƏRDARLIQ] Sistem 30 saniyə ərzində cavab vermədi. Loqları yoxlayın:${NC}"
echo "docker compose -f docker-compose.sovereign.yml logs"
