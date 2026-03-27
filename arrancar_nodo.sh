#!/bin/bash
# Activa el entorno virtual y corre el nodo
cd "$(dirname "$0")"
source venv/bin/activate
python3 main.py "$@"
