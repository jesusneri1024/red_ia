"""
Capa de red P2P — conexiones TCP entre nodos.
Cada mensaje es una línea JSON terminada en newline.
"""
import asyncio
import json
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class Peer:
    """Representa una conexión activa con otro nodo."""

    def __init__(self, node_id: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.node_id = node_id
        self.reader = reader
        self.writer = writer
        addr = writer.get_extra_info("peername")
        self.address = f"{addr[0]}:{addr[1]}" if addr else "desconocido"

    async def enviar(self, msg: dict):
        data = (json.dumps(msg) + "\n").encode()
        self.writer.write(data)
        await self.writer.drain()

    def cerrar(self):
        self.writer.close()


class Servidor:
    """
    Servidor TCP que acepta conexiones de otros nodos.
    Por cada conexión llama a on_message(peer, mensaje).
    """

    def __init__(self, host: str, port: int, on_message: Callable):
        self.host = host
        self.port = port
        self.on_message = on_message
        self._server = None

    async def iniciar(self):
        self._server = await asyncio.start_server(
            self._manejar_conexion, self.host, self.port
        )
        logger.info(f"Servidor escuchando en {self.host}:{self.port}")

    async def _manejar_conexion(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = Peer("desconocido", reader, writer)
        logger.info(f"Nueva conexión desde {peer.address}")
        try:
            while True:
                linea = await reader.readline()
                if not linea:
                    break
                msg = json.loads(linea.decode().strip())
                # El node_id se actualiza cuando llega el HELLO
                if msg.get("type") == "HELLO":
                    peer.node_id = msg.get("node_id", peer.node_id)
                await self.on_message(peer, msg)
        except (asyncio.IncompleteReadError, ConnectionResetError, json.JSONDecodeError):
            pass
        finally:
            logger.info(f"Conexión cerrada: {peer.address}")
            peer.cerrar()

    async def detener(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()


async def conectar(host: str, port: int, on_message: Callable) -> Peer | None:
    """Conecta a un nodo remoto. Retorna Peer o None si falla."""
    try:
        reader, writer = await asyncio.open_connection(host, port)
        peer = Peer("desconocido", reader, writer)

        async def escuchar():
            try:
                while True:
                    linea = await reader.readline()
                    if not linea:
                        break
                    msg = json.loads(linea.decode().strip())
                    if msg.get("type") == "HELLO":
                        peer.node_id = msg.get("node_id", peer.node_id)
                    await on_message(peer, msg)
            except (asyncio.IncompleteReadError, ConnectionResetError, json.JSONDecodeError):
                pass

        asyncio.create_task(escuchar())
        return peer
    except OSError as e:
        logger.warning(f"No se pudo conectar a {host}:{port} — {e}")
        return None
