#!/bin/bash
# ============================================================
#  Inicio de nodo — Red IA Descentralizada
#
#  Uso:
#    ./start.sh              → arrancar nodo (se une a la red)
#    ./start.sh --api        → arrancar nodo + API HTTP
#    ./start.sh --status     → ver identidad y puntos
#    ./start.sh --prompt "X" → mandar un prompt a la red
# ============================================================

AZUL='\033[0;34m'
VERDE='\033[0;32m'
AMARILLO='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activar entorno virtual
source venv/bin/activate 2>/dev/null || {
  echo "Entorno no encontrado. Corre ./install.sh primero."
  exit 1
}

# Leer configuración
CONFIG="config.json"
PORT=$(python3 -c "import json; c=json.load(open('$CONFIG')); print(c['nodo']['port'])" 2>/dev/null || echo "7000")
API_PORT=$(python3 -c "import json; c=json.load(open('$CONFIG')); print(c['nodo']['api_port'])" 2>/dev/null || echo "8080")
BOOTSTRAP=$(python3 -c "
import json
c = json.load(open('$CONFIG'))
nodes = c['red']['bootstrap_nodes']
print(','.join(nodes))
" 2>/dev/null || echo "")

# Asegurarse de que Ollama está corriendo
if ! ollama list &>/dev/null 2>&1; then
  echo -e "${AMARILLO}Iniciando Ollama...${NC}"
  if [[ "$OSTYPE" == "darwin"* ]] && command -v brew &>/dev/null; then
    brew services start ollama &>/dev/null
  else
    ollama serve &>/dev/null &
  fi
  sleep 3
fi

# ----------------------------------------------------------
# Modo status
# ----------------------------------------------------------
if [[ "$1" == "--status" ]]; then
  python3 main.py --port "$PORT" --status
  exit 0
fi

# ----------------------------------------------------------
# Modo prompt
# ----------------------------------------------------------
if [[ "$1" == "--prompt" ]]; then
  if [[ -z "$2" ]]; then
    echo "Uso: ./start.sh --prompt \"tu pregunta\""
    exit 1
  fi
  # Usar un puerto temporal para el cliente
  CLIENT_PORT=$((PORT + 500))
  python3 main.py --port "$CLIENT_PORT" \
    --peers "$BOOTSTRAP" \
    --prompt "$2"
  exit 0
fi

# ----------------------------------------------------------
# Modo API
# ----------------------------------------------------------
if [[ "$1" == "--api" ]]; then
  API_NODE_PORT=$((PORT + 99))
  echo -e "${AZUL}"
  echo "╔══════════════════════════════════════════════╗"
  echo "║     Red IA — Nodo + API Gateway              ║"
  echo "╚══════════════════════════════════════════════╝"
  echo -e "${NC}"
  echo -e "  API disponible en: ${VERDE}http://localhost:$API_PORT/v1${NC}"
  echo -e "  Docs:              ${VERDE}http://localhost:$API_PORT/docs${NC}"
  echo ""
  python3 api.py \
    --api-port "$API_PORT" \
    --node-port "$API_NODE_PORT" \
    --peers "$BOOTSTRAP"
  exit 0
fi

# ----------------------------------------------------------
# Modo nodo (default)
# ----------------------------------------------------------
python3 main.py --port "$PORT" --peers "$BOOTSTRAP"
