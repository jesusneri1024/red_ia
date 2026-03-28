"""
Gateway HTTP compatible con la API de OpenAI.

Cualquier developer puede apuntar el cliente de OpenAI a este servidor
y usar la red descentralizada sin cambiar su código.

Uso:
  python api.py --port 8000 --node-port 7000

Luego en el código del developer:
  from openai import OpenAI
  client = OpenAI(
      api_key="cualquier-cosa",        # se validará contra el ledger en fase 3
      base_url="http://localhost:8000/v1"
  )
  response = client.chat.completions.create(
      model="red-ia",
      messages=[{"role": "user", "content": "¿Qué es Bitcoin?"}]
  )
"""
import argparse
import asyncio
import collections
import time
import uuid
from pathlib import Path
import uvicorn
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from node import Nodo

# ------------------------------------------------------------------
# Rate limiting — ventana deslizante por IP
# ------------------------------------------------------------------

RATE_LIMIT_REQUESTS = 20   # máximo requests por ventana
RATE_LIMIT_WINDOW   = 60   # ventana en segundos

_rate_buckets: dict[str, collections.deque] = {}

def _check_rate_limit(ip: str) -> bool:
    """Retorna True si el request está permitido, False si excede el límite."""
    ahora = time.time()
    if ip not in _rate_buckets:
        _rate_buckets[ip] = collections.deque()
    bucket = _rate_buckets[ip]
    # Limpiar timestamps fuera de la ventana
    while bucket and bucket[0] < ahora - RATE_LIMIT_WINDOW:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_REQUESTS:
        return False
    bucket.append(ahora)
    return True

# ------------------------------------------------------------------
# Modelos de datos (formato OpenAI)
# ------------------------------------------------------------------

class Mensaje(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = "red-ia"
    messages: list[Mensaje]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

class Choice(BaseModel):
    index: int
    message: Mensaje
    finish_reason: str = "stop"

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage

# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

app  = FastAPI(title="Red IA — API compatible con OpenAI", version="0.1.0")
nodo: Nodo = None  # Se inicializa al arrancar

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir landing page
_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/static", StaticFiles(directory=_static), name="static")

@app.get("/")
async def landing():
    return FileResponse(_static / "index.html")

# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.get("/v1/models")
async def listar_modelos():
    """Lista los modelos disponibles en la red."""
    return {
        "object": "list",
        "data": [
            {
                "id": "red-ia",
                "object": "model",
                "created": 1700000000,
                "owned_by": "red-ia-descentralizada",
            }
        ]
    }


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Endpoint principal — compatible con OpenAI chat completions.
    Recibe mensajes, los manda a la red P2P, retorna la respuesta.
    """
    if nodo is None:
        raise HTTPException(status_code=503, detail="Nodo no inicializado")

    ip = http_request.client.host
    if not _check_rate_limit(ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit excedido: máximo {RATE_LIMIT_REQUESTS} requests por {RATE_LIMIT_WINDOW}s"
        )

    # Formatear mensajes como prompt para el modelo
    prompt = _formatear_mensajes(request.messages)

    # Enviar a la red y esperar respuesta
    respuesta = await nodo.coordinar_prompt(prompt)

    if not respuesta:
        raise HTTPException(
            status_code=503,
            detail="La red no pudo generar una respuesta. Intenta de nuevo."
        )

    # Contar tokens aproximados (1 token ≈ 4 caracteres)
    prompt_tokens     = len(prompt) // 4
    completion_tokens = len(respuesta) // 4

    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=request.model,
        choices=[
            Choice(
                index=0,
                message=Mensaje(role="assistant", content=respuesta),
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


@app.get("/v1/network/status")
async def estado_red():
    """Estado de la red — cuántos peers, puntos, pool de datos."""
    if nodo is None:
        raise HTTPException(status_code=503, detail="Nodo no inicializado")
    return nodo.estado()


@app.get("/health")
async def health():
    return {"status": "ok", "node_id": nodo.node_id if nodo else None}

# ------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------

def _formatear_mensajes(mensajes: list[Mensaje]) -> str:
    """
    Convierte la lista de mensajes en un prompt de texto.
    Mantiene el historial de conversación para contexto.
    """
    if not mensajes:
        return ""

    # Si es un solo mensaje de usuario, usarlo directamente
    if len(mensajes) == 1 and mensajes[0].role == "user":
        return mensajes[0].content

    # Conversación multi-turno — formatear con roles
    partes = []
    for msg in mensajes:
        if msg.role == "system":
            partes.append(f"[Sistema]: {msg.content}")
        elif msg.role == "user":
            partes.append(f"Usuario: {msg.content}")
        elif msg.role == "assistant":
            partes.append(f"Asistente: {msg.content}")

    partes.append("Asistente:")
    return "\n".join(partes)

# ------------------------------------------------------------------
# Arranque
# ------------------------------------------------------------------

async def arrancar_api(node_port: int, node_peers: list[tuple], api_port: int, coordinator_only: bool = False, public_host: str = None):
    global nodo

    # Auto-detectar IP pública si no se especifica
    if not public_host:
        import socket
        import urllib.request
        # Primero intentar con socket (funciona en VPS con IP directa en interfaz)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            public_host = s.getsockname()[0]
            s.close()
        except Exception:
            public_host = None
        # Si es IP privada, intentar servicios externos
        _privadas = ("127.", "10.", "192.168.", "172.")
        if not public_host or any(public_host.startswith(p) for p in _privadas):
            for url in ["http://api4.ipify.org", "http://ifconfig.me", "http://ipv4.icanhazip.com"]:
                try:
                    public_host = urllib.request.urlopen(url, timeout=3).read().decode().strip()
                    if public_host and not public_host.startswith("<"):
                        break
                except Exception:
                    continue
            else:
                public_host = "localhost"
        print(f"INFO: IP pública detectada: {public_host}")

    nodo = Nodo(host="0.0.0.0", port=node_port, peers_iniciales=node_peers, coordinator_only=coordinator_only, public_host=public_host)
    await nodo._servidor.iniciar()

    # Conectar a peers
    from network import conectar
    for h, p in node_peers:
        peer = await conectar(h, p, nodo._on_message)
        if peer:
            await nodo._saludar(peer)

    await asyncio.sleep(1)  # Handshake

    print(f"""
╔══════════════════════════════════════════════════╗
║     Red IA — API Gateway                         ║
╚══════════════════════════════════════════════════╝
  Node ID : {nodo.node_id}
  API     : http://localhost:{api_port}/v1
  Docs    : http://localhost:{api_port}/docs
  Peers   : {node_peers or 'ninguno'}

  Ejemplo de uso:
    from openai import OpenAI
    client = OpenAI(
        api_key="mi-token",
        base_url="http://localhost:{api_port}/v1"
    )
    r = client.chat.completions.create(
        model="red-ia",
        messages=[{{"role":"user","content":"Hola"}}]
    )
""")

    config = uvicorn.Config(app, host="0.0.0.0", port=api_port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


def parsear_peers(peers_str: str) -> list[tuple[str, int]]:
    if not peers_str:
        return []
    resultado = []
    for p in peers_str.split(","):
        host, port = p.strip().split(":")
        resultado.append((host, int(port)))
    return resultado


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API Gateway compatible con OpenAI")
    parser.add_argument("--api-port",         type=int, default=8000)
    parser.add_argument("--node-port",        type=int, default=7099)
    parser.add_argument("--peers",            default="")
    parser.add_argument("--coordinator-only", action="store_true")
    parser.add_argument("--public-host",      default="", help="IP pública del nodo (auto-detecta si no se especifica)")
    args = parser.parse_args()

    peers = parsear_peers(args.peers)

    try:
        asyncio.run(arrancar_api(args.node_port, peers, args.api_port, args.coordinator_only, args.public_host or None))
    except KeyboardInterrupt:
        print("\nAPI detenida.")
