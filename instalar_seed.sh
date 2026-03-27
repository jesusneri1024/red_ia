#!/bin/bash
# ============================================================
#  Instalador del seed node para VPS
#  Corre esto en tu VPS (Ubuntu/Debian):
#    bash instalar_seed.sh
# ============================================================

set -e

VERDE='\033[0;32m'
AZUL='\033[0;34m'
NC='\033[0m'

echo -e "${AZUL}"
echo "╔══════════════════════════════════════════════╗"
echo "║     Red IA — Instalador Seed Node (VPS)      ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# Python
echo "→ Verificando Python..."
python3 --version || { apt-get update && apt-get install -y python3 python3-pip python3-venv; }

# Clonar/actualizar código
if [ -d "red_ia" ]; then
  echo "→ Actualizando código..."
  cd red_ia && git pull
else
  echo "→ Clonando repositorio..."
  git clone https://github.com/jesusneri1024/red_ia.git
  cd red_ia
fi

# Solo necesitamos seed.py — sin Ollama, sin modelo
echo "→ Configurando entorno..."
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip

# Crear servicio systemd para que corra siempre
echo "→ Configurando servicio del sistema..."
WORKING_DIR="$(pwd)"

cat > /tmp/red-ia-seed.service << EOF
[Unit]
Description=Red IA Seed Node
After=network.target

[Service]
Type=simple
WorkingDirectory=$WORKING_DIR
ExecStart=$WORKING_DIR/venv/bin/python3 seed.py --port 7000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/red-ia-seed.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable red-ia-seed
sudo systemctl start red-ia-seed

# Abrir puerto en firewall si ufw está activo
if command -v ufw &>/dev/null; then
  sudo ufw allow 7000/tcp
  echo -e "${VERDE}→ Puerto 7000 abierto en firewall${NC}"
fi

IP_PUBLICA=$(curl -s ifconfig.me 2>/dev/null || echo "IP_DE_TU_VPS")

echo ""
echo -e "${VERDE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${VERDE}║   ✓ Seed node instalado y corriendo          ║${NC}"
echo -e "${VERDE}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  IP pública: ${AZUL}$IP_PUBLICA${NC}"
echo -e "  Puerto:     ${AZUL}7000${NC}"
echo ""
echo -e "  Agrega esto al config.json de todos los nodos:"
echo -e "  ${AZUL}\"bootstrap_nodes\": [\"$IP_PUBLICA:7000\"]${NC}"
echo ""
echo -e "  Ver estado: sudo systemctl status red-ia-seed"
echo -e "  Ver logs:   sudo journalctl -u red-ia-seed -f"
echo ""
