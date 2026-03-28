"""
Nodo principal de la red.
"""
import asyncio
import json
import logging
import random
import uuid
from pathlib import Path

from network import Servidor, Peer, conectar
from ledger import Ledger
from vrf import calcular as calcular_vrf, elegir_coordinador
from data_pool import DataPool
import identity
import inference
import arbiter

logger = logging.getLogger(__name__)

PUNTOS_RESPUESTA_CORRECTA = 10
PUNTOS_PENALIZACION       = 5
PUNTOS_COORDINAR          = 2
PUNTOS_ARBITRO            = 1   # Por evaluar una conversación


class Ronda:
    """Estado de una ronda de inferencia en curso."""
    def __init__(self, prompt_id: str, prompt: str, workers: list):
        self.prompt_id  = prompt_id
        self.prompt     = prompt
        self.workers    = workers  # list[Peer]
        self.commitments: dict[str, str]  = {}
        self.reveals:     dict[str, dict] = {}
        self.future:      asyncio.Future  = asyncio.get_event_loop().create_future()


class Nodo:
    def __init__(self, host: str, port: int, peers_iniciales: list[tuple[str, int]] = None, coordinator_only: bool = False, public_host: str = None):
        self.host = host
        self.port = port
        self.public_host = public_host or host
        self.peers_iniciales = peers_iniciales or []

        # Identidad persistente
        id_data             = identity.cargar_o_crear(port)
        self.node_id        = id_data["node_id"]
        self._privkey       = id_data["privkey"]
        self._privkey_bytes = id_data["privkey_bytes"]
        self._es_nuevo      = id_data["es_nuevo"]

        # Red
        self.peers: dict[str, Peer] = {}
        self.ronda_actual = 0

        # Datos persistentes
        ruta_dir   = Path.home() / ".red_ia" / str(port)
        self.ledger    = Ledger(identity.ruta_ledger(port))
        self.data_pool = DataPool(ruta_dir)

        # Rondas concurrentes: {prompt_id: Ronda}
        self._rondas: dict[str, Ronda] = {}

        # Estado como TRABAJADOR (por prompt_id)
        self._trabajos: dict[str, dict] = {}  # {prompt_id: {respuesta, nonce, commitment}}

        # Semáforo — Ollama procesa un prompt a la vez
        self._inference_sem = asyncio.Semaphore(1)

        self._vrfs_recibidos: dict[str, str] = {}

        self.coordinator_only = coordinator_only
        self._servidor = Servidor(host, port, self._on_message)

    # ------------------------------------------------------------------
    # Arranque
    # ------------------------------------------------------------------

    async def arrancar(self):
        await self._servidor.iniciar()
        logger.info(f"Nodo {self.node_id} en {self.host}:{self.port}")

        for h, p in self.peers_iniciales:
            peers_descubiertos = await self._conectar_seed(h, p)
            if peers_descubiertos:
                for pd in peers_descubiertos:
                    peer = await conectar(pd["host"], pd["port"], self._on_message)
                    if peer:
                        await self._saludar(peer)
            else:
                peer = await conectar(h, p, self._on_message)
                if peer:
                    await self._saludar(peer)

        await self._loop()

    async def _conectar_seed(self, host: str, port: int) -> list[dict]:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5
            )
            msg = json.dumps({
                "type":    "HELLO",
                "node_id": self.node_id,
                "host":    self.public_host,
                "port":    self.port,
            }) + "\n"
            writer.write(msg.encode())
            await writer.drain()

            linea = await asyncio.wait_for(reader.readline(), timeout=5)
            respuesta = json.loads(linea.decode().strip())
            writer.close()

            if respuesta.get("type") == "PEER_LIST":
                peers = respuesta.get("peers", [])
                logger.info(f"Seed {host}:{port} → {len(peers)} peers descubiertos")
                return peers

            return []
        except Exception:
            return []

    async def _loop(self):
        ping_counter = 0
        while True:
            await asyncio.sleep(30)
            await self._reconectar_si_necesario()
            await self._iniciar_ronda()
            ping_counter += 1
            if ping_counter % 4 == 0:  # Cada ~2 minutos
                await self._ping_seeds()

    async def _ping_seeds(self):
        """Mantiene el nodo visible en el seed mandando PING periódico."""
        for h, p in self.peers_iniciales:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(h, p), timeout=5
                )
                msg = json.dumps({
                    "type":    "PING",
                    "node_id": self.node_id,
                }) + "\n"
                writer.write(msg.encode())
                await writer.drain()
                writer.close()
            except Exception:
                pass

    async def _reconectar_si_necesario(self):
        """Si no hay peers conectados, vuelve a consultar el seed."""
        desconectados = [nid for nid, p in self.peers.items() if p.writer.is_closing()]
        for nid in desconectados:
            del self.peers[nid]
            logger.info(f"Peer removido (desconectado): {nid[:8]}")

        if not self.peers and self.peers_iniciales:
            logger.info("Sin peers — reconectando al seed...")
            for h, p in self.peers_iniciales:
                peers_descubiertos = await self._conectar_seed(h, p)
                if peers_descubiertos:
                    for pd in peers_descubiertos:
                        peer = await conectar(pd["host"], pd["port"], self._on_message)
                        if peer:
                            await self._saludar(peer)
                else:
                    peer = await conectar(h, p, self._on_message)
                    if peer:
                        await self._saludar(peer)

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    async def _saludar(self, peer: Peer):
        await peer.enviar({
            "type":    "HELLO",
            "node_id": self.node_id,
            "host":    self.public_host,
            "port":    self.port,
        })

    # ------------------------------------------------------------------
    # VRF
    # ------------------------------------------------------------------

    async def _iniciar_ronda(self):
        self.ronda_actual += 1
        self._vrfs_recibidos = {}
        mi_vrf = calcular_vrf(self._privkey_bytes, self.ronda_actual)
        self._vrfs_recibidos[self.node_id] = mi_vrf
        await self._broadcast({
            "type":    "VRF_ANNOUNCE",
            "node_id": self.node_id,
            "ronda":   self.ronda_actual,
            "vrf":     mi_vrf,
        })
        logger.info(f"Ronda {self.ronda_actual} — VRF: {mi_vrf[:8]}...")

    # ------------------------------------------------------------------
    # Router de mensajes
    # ------------------------------------------------------------------

    async def _on_message(self, peer: Peer, msg: dict):
        tipo = msg.get("type")

        if tipo == "HELLO":
            peer.node_id = msg["node_id"]
            self.peers[peer.node_id] = peer
            await peer.enviar({
                "type":    "PONG",
                "node_id": self.node_id,
                "host":    self.host,
                "port":    self.port,
            })

        elif tipo == "PONG":
            peer.node_id = msg["node_id"]
            self.peers[peer.node_id] = peer
            logger.info(f"Peer confirmado: {peer.node_id}")

        elif tipo == "VRF_ANNOUNCE":
            self._vrfs_recibidos[msg["node_id"]] = msg["vrf"]

        elif tipo == "PROMPT_REQ":
            if not self.coordinator_only:
                asyncio.create_task(self._procesar_prompt(peer, msg))

        elif tipo == "REVEAL_REQUEST":
            asyncio.create_task(self._revelar_respuesta(peer, msg["prompt_id"]))

        elif tipo == "COMMITMENT":
            prompt_id = msg.get("prompt_id")
            if prompt_id and prompt_id in self._rondas:
                ronda = self._rondas[prompt_id]
                ronda.commitments[msg["node_id"]] = msg["commitment"]
                logger.info(f"Commitment {msg['node_id'][:8]} ronda {prompt_id[:8]} ({len(ronda.commitments)}/{len(ronda.workers)})")
                await self._revisar_commitments(ronda)

        elif tipo == "REVEAL":
            prompt_id = msg.get("prompt_id")
            if prompt_id and prompt_id in self._rondas:
                ronda = self._rondas[prompt_id]
                ronda.reveals[msg["node_id"]] = {
                    "respuesta":  msg["respuesta"],
                    "nonce":      msg["nonce"],
                    "commitment": msg["commitment"],
                    "node_id":    msg["node_id"],
                }
                logger.info(f"Reveal {msg['node_id'][:8]} ronda {prompt_id[:8]} ({len(ronda.reveals)}/{len(ronda.workers)})")
                await self._resolver_ronda(ronda)

        elif tipo == "POINTS_SYNC":
            self.ledger.merge(msg["puntos"])
            logger.info(f"Ledger: {self.ledger.snapshot()}")

        elif tipo == "CONV_RESULT":
            asyncio.create_task(self._procesar_conv_resultado(msg))

    # ------------------------------------------------------------------
    # Trabajador: inferencia
    # ------------------------------------------------------------------

    async def _procesar_prompt(self, coordinador: Peer, msg: dict):
        prompt_id = msg["prompt_id"]
        logger.info(f"Procesando prompt {prompt_id[:8]}...")

        async with self._inference_sem:
            loop = asyncio.get_event_loop()
            respuesta = await loop.run_in_executor(None, inference.correr_modelo, msg["prompt"])

        commitment, nonce = inference.hacer_commitment(respuesta)
        self._trabajos[prompt_id] = {
            "respuesta":  respuesta,
            "nonce":      nonce,
            "commitment": commitment,
        }

        await coordinador.enviar({
            "type":       "COMMITMENT",
            "node_id":    self.node_id,
            "prompt_id":  prompt_id,
            "commitment": commitment,
        })
        logger.info(f"Commitment enviado {prompt_id[:8]}")

    async def _revelar_respuesta(self, coordinador: Peer, prompt_id: str):
        trabajo = self._trabajos.get(prompt_id)
        if not trabajo:
            logger.warning(f"No hay trabajo para prompt {prompt_id[:8]}")
            return
        await coordinador.enviar({
            "type":       "REVEAL",
            "node_id":    self.node_id,
            "prompt_id":  prompt_id,
            "respuesta":  trabajo["respuesta"],
            "nonce":      trabajo["nonce"],
            "commitment": trabajo["commitment"],
        })
        logger.info(f"Reveal enviado {prompt_id[:8]}")
        # Limpiar trabajo completado
        self._trabajos.pop(prompt_id, None)

    # ------------------------------------------------------------------
    # Coordinador: gestionar rondas concurrentes
    # ------------------------------------------------------------------

    async def coordinar_prompt(self, prompt: str) -> str | None:
        if not self.peers:
            logger.warning("Sin peers conectados.")
            return None

        prompt_id = uuid.uuid4().hex
        n = min(3, len(self.peers))
        workers = random.sample(list(self.peers.values()), n)

        ronda = Ronda(prompt_id, prompt, workers)
        self._rondas[prompt_id] = ronda

        logger.info(f"Ronda {prompt_id[:8]} — Workers: {[p.node_id[:8] for p in workers]}")

        for peer in workers:
            await peer.enviar({
                "type":      "PROMPT_REQ",
                "node_id":   self.node_id,
                "prompt_id": prompt_id,
                "prompt":    prompt,
            })

        try:
            resultado = await asyncio.wait_for(ronda.future, timeout=120)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout ronda {prompt_id[:8]}")
            resultado = None
        finally:
            self._rondas.pop(prompt_id, None)

        return resultado

    async def _revisar_commitments(self, ronda: Ronda):
        if len(ronda.commitments) < len(ronda.workers):
            return
        logger.info(f"Commitments completos ronda {ronda.prompt_id[:8]} — pidiendo reveals...")
        for peer in ronda.workers:
            if peer.node_id in ronda.commitments:
                await peer.enviar({
                    "type":      "REVEAL_REQUEST",
                    "prompt_id": ronda.prompt_id,
                })

    async def _resolver_ronda(self, ronda: Ronda):
        if len(ronda.reveals) < len(ronda.workers):
            return

        reveals   = list(ronda.reveals.values())
        respuesta = inference.elegir_respuesta_final(reveals)

        if respuesta:
            node_ids_correctos = []
            for r in reveals:
                if r["respuesta"] == respuesta:
                    self.ledger.sumar(r["node_id"], PUNTOS_RESPUESTA_CORRECTA)
                    node_ids_correctos.append(r["node_id"])
                else:
                    self.ledger.restar(r["node_id"], PUNTOS_PENALIZACION)
            self.ledger.sumar(self.node_id, PUNTOS_COORDINAR)

            await self._broadcast({"type": "POINTS_SYNC", "puntos": self.ledger.snapshot()})
            await self._broadcast({
                "type":     "CONV_RESULT",
                "prompt":   ronda.prompt,
                "response": respuesta,
                "node_ids": node_ids_correctos,
            })
            logger.info(f"Ronda {ronda.prompt_id[:8]} resuelta — broadcast a {len(self.peers)} peers")
        else:
            logger.warning(f"Sin consenso ronda {ronda.prompt_id[:8]}")

        resultado_final = respuesta or "Sin consenso en la red."
        if not ronda.future.done():
            ronda.future.set_result(resultado_final)

    # ------------------------------------------------------------------
    # Pool de datos: cada nodo evalúa localmente
    # ------------------------------------------------------------------

    async def _procesar_conv_resultado(self, msg: dict):
        prompt   = msg["prompt"]
        response = msg["response"]

        conv_id = self.data_pool.guardar_pendiente(
            prompt=prompt,
            response=response,
            node_ids=msg.get("node_ids", []),
        )

        loop  = asyncio.get_event_loop()
        score = await loop.run_in_executor(None, arbiter.evaluar, prompt, response)
        self.ledger.sumar(self.node_id, PUNTOS_ARBITRO)

        self.data_pool.registrar_voto(conv_id, self.node_id, score)
        status, score_final = self.data_pool.resolver(conv_id)

        stats = self.data_pool.stats()
        logger.info(
            f"Conv {conv_id[:8]} → {status.upper()} (score={score_final:.2f}) | "
            f"Pool: {stats['aprobadas']} aprobadas / {stats['total']} total | "
            f"Training: {stats['training_size']} listas"
        )

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    async def _broadcast(self, msg: dict):
        for peer in list(self.peers.values()):
            try:
                await peer.enviar(msg)
            except Exception as e:
                logger.warning(f"Broadcast error {peer.node_id[:8]}: {e}")

    def estado(self) -> dict:
        return {
            "node_id":        self.node_id,
            "peers":          list(self.peers.keys()),
            "ronda":          self.ronda_actual,
            "rondas_activas": len(self._rondas),
            "puntos":         self.ledger.snapshot(),
            "pool":           self.data_pool.stats(),
        }
