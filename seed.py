"""
Seed node — nodo ligero de descubrimiento.

Su única función es mantener una lista de nodos activos
y presentarlos entre sí cuando llega un nodo nuevo.

No necesita Ollama ni el modelo de IA.
Corre en un VPS de $5/mes con 1GB RAM.

Uso:
  python seed.py --port 7000
"""
import asyncio
import json
import logging
import time
import argparse

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Nodo se considera offline si no hace ping en 5 minutos
TIMEOUT_PEER = 300


class SeedNode:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        # {node_id: {host, port, last_seen}}
        self.peers: dict[str, dict] = {}

    async def arrancar(self):
        server = await asyncio.start_server(
            self._manejar_conexion, self.host, self.port
        )
        logger.info(f"Seed node corriendo en {self.host}:{self.port}")
        logger.info("Esperando nodos...")

        # Limpiar peers inactivos cada minuto
        asyncio.create_task(self._limpiar_inactivos())

        async with server:
            await server.serve_forever()

    async def _manejar_conexion(self, reader, writer):
        addr = writer.get_extra_info("peername")
        try:
            while True:
                linea = await reader.readline()
                if not linea:
                    break
                msg = json.loads(linea.decode().strip())
                respuesta = await self._procesar(msg, addr)
                if respuesta:
                    writer.write((json.dumps(respuesta) + "\n").encode())
                    await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError, json.JSONDecodeError):
            pass
        finally:
            writer.close()

    async def _procesar(self, msg: dict, addr) -> dict | None:
        tipo = msg.get("type")

        if tipo == "HELLO":
            node_id = msg["node_id"]
            nodo_host = msg.get("host", addr[0])
            nodo_port = msg.get("port", 7000)

            # Si el nodo se anuncia como localhost/privado, usar la IP real de la conexión
            _privadas = ("localhost", "127.0.0.1", "::1", "0.0.0.0")
            if nodo_host in _privadas or nodo_host.startswith("192.168.") or nodo_host.startswith("10."):
                nodo_host = addr[0]

            # Registrar el nodo
            self.peers[node_id] = {
                "host":      nodo_host,
                "port":      nodo_port,
                "last_seen": time.time(),
            }
            logger.info(f"Nodo conectado: {node_id[:8]} ({nodo_host}:{nodo_port}) | Total: {len(self.peers)}")

            # Devolver lista de peers activos (excluyendo al que pregunta)
            peers_activos = [
                {"node_id": nid, **info}
                for nid, info in self.peers.items()
                if nid != node_id
            ]
            return {
                "type":  "PEER_LIST",
                "peers": peers_activos[:20],  # máximo 20 peers
            }

        elif tipo == "PING":
            node_id = msg.get("node_id")
            if node_id and node_id in self.peers:
                self.peers[node_id]["last_seen"] = time.time()
            return {"type": "PONG"}

        elif tipo == "STATUS":
            return {
                "type":        "STATUS",
                "peers_total": len(self.peers),
                "peers":       [
                    {"node_id": nid[:8], "host": info["host"], "port": info["port"]}
                    for nid, info in self.peers.items()
                ],
            }

        return None

    async def _limpiar_inactivos(self):
        while True:
            await asyncio.sleep(60)
            ahora = time.time()
            inactivos = [
                nid for nid, info in self.peers.items()
                if ahora - info["last_seen"] > TIMEOUT_PEER
            ]
            for nid in inactivos:
                del self.peers[nid]
                logger.info(f"Nodo removido por inactividad: {nid[:8]}")
            if inactivos:
                logger.info(f"Peers activos: {len(self.peers)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed node de descubrimiento")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7000)
    args = parser.parse_args()

    try:
        asyncio.run(SeedNode(args.host, args.port).arrancar())
    except KeyboardInterrupt:
        print("\nSeed node detenido.")
