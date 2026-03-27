#!/bin/bash
# ============================================================
#  Instalador de nodo — Red IA Descentralizada
#  Uso: bash install.sh
# ============================================================

set -e

ROJO='\033[0;31m'
VERDE='\033[0;32m'
AMARILLO='\033[1;33m'
AZUL='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${VERDE}  ✓ $1${NC}"; }
info() { echo -e "${AZUL}  → $1${NC}"; }
warn() { echo -e "${AMARILLO}  ⚠ $1${NC}"; }
fail() { echo -e "${ROJO}  ✗ $1${NC}"; exit 1; }

echo ""
echo -e "${AZUL}╔══════════════════════════════════════════════╗${NC}"
echo -e "${AZUL}║       Red IA Descentralizada                 ║${NC}"
echo -e "${AZUL}║       Instalador de nodo v0.1.0              ║${NC}"
echo -e "${AZUL}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ----------------------------------------------------------
# 1. Detectar sistema operativo
# ----------------------------------------------------------
info "Detectando sistema..."
OS="$(uname -s)"
case "$OS" in
  Darwin) ok "macOS detectado" ;;
  Linux)  ok "Linux detectado" ;;
  *)      fail "Sistema no soportado: $OS (se necesita macOS o Linux)" ;;
esac

# ----------------------------------------------------------
# 2. Python 3.10+
# ----------------------------------------------------------
info "Verificando Python..."
if command -v python3 &>/dev/null; then
  PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
  PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
  if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
    ok "Python $PYTHON_VERSION"
  else
    fail "Se necesita Python 3.10+. Tienes Python $PYTHON_VERSION. Instala desde python.org"
  fi
else
  fail "Python 3 no encontrado. Instala desde python.org"
fi

# ----------------------------------------------------------
# 3. Ollama
# ----------------------------------------------------------
info "Verificando Ollama..."
if command -v ollama &>/dev/null; then
  ok "Ollama ya instalado"
else
  info "Instalando Ollama..."
  if [ "$OS" = "Darwin" ]; then
    if command -v brew &>/dev/null; then
      brew install ollama
      ok "Ollama instalado via Homebrew"
    else
      curl -fsSL https://ollama.com/install.sh | sh
      ok "Ollama instalado"
    fi
  else
    curl -fsSL https://ollama.com/install.sh | sh
    ok "Ollama instalado"
  fi
fi

# Iniciar Ollama si no está corriendo
if ! ollama list &>/dev/null 2>&1; then
  info "Iniciando Ollama..."
  if [ "$OS" = "Darwin" ] && command -v brew &>/dev/null; then
    brew services start ollama
  else
    ollama serve &>/dev/null &
  fi
  sleep 3
fi
ok "Ollama corriendo"

# ----------------------------------------------------------
# 4. Descargar modelo Llama 3.2
# ----------------------------------------------------------
info "Verificando modelo Llama 3.2..."
if ollama list 2>/dev/null | grep -q "llama3.2"; then
  ok "Llama 3.2 ya descargado"
else
  info "Descargando Llama 3.2 (2GB — puede tardar unos minutos)..."
  ollama pull llama3.2
  ok "Llama 3.2 descargado"
fi

# ----------------------------------------------------------
# 5. Entorno virtual Python
# ----------------------------------------------------------
info "Configurando entorno Python..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Dependencias instaladas"

# ----------------------------------------------------------
# 6. Generar identidad del nodo
# ----------------------------------------------------------
info "Generando identidad del nodo..."
NODE_ID=$(python3 -c "
import identity
id_data = identity.cargar_o_crear(7000)
print(id_data['node_id'])
" 2>/dev/null)
ok "Node ID: $NODE_ID"

# ----------------------------------------------------------
# 7. Resumen final
# ----------------------------------------------------------
echo ""
echo -e "${VERDE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${VERDE}║   ✓ Instalación completada                   ║${NC}"
echo -e "${VERDE}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Node ID : ${AZUL}$NODE_ID${NC}"
echo -e "  Datos   : ${AZUL}~/.red_ia/7000/${NC}"
echo ""
echo -e "  ${AMARILLO}Para arrancar el nodo:${NC}"
echo -e "  ${VERDE}./start.sh${NC}"
echo ""
echo -e "  ${AMARILLO}Para ver tu estado:${NC}"
echo -e "  ${VERDE}./start.sh --status${NC}"
echo ""
