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


class Nodo:
    def __init__(self, host: str, port: int, peers_iniciales: list[tuple[str, int]] = None, coordinator_only: bool = False, public_host: str = None):
        self.host = host
        self.port = port
        self.public_host = public_host or host  # IP pública para anunciarse a otros nodos
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

        # Estado como COORDINADOR
        self._prompt_activo:      str | None     = None
        self._prompt_texto:       str | None     = None
        self._workers_activos:    list[Peer]     = []
        self._commitments:        dict[str, str] = {}
        self._reveals:            dict[str, dict] = {}
        self._resultado_final:    str | None     = None
        self._vrfs_recibidos:     dict[str, str] = {}


        # Estado como TRABAJADOR
        self._respuesta_local:    str | None = None
        self._nonce_local:        str | None = None
        self._commitment_local:   str | None = None

        self.coordinator_only = coordinator_only
        self._servidor = Servidor(host, port, self._on_message)

    # ------------------------------------------------------------------
    # Arranque
    # ------------------------------------------------------------------

    async def arrancar(self):
        await self._servidor.iniciar()
        logger.info(f"Nodo {self.node_id} en {self.host}:{self.port}")

        for h, p in self.peers_iniciales:
            # Intentar conectar como seed primero (pide lista de peers)
            peers_descubiertos = await self._conectar_seed(h, p)
            if peers_descubiertos:
                for pd in peers_descubiertos:
                    peer = await conectar(pd["host"], pd["port"], self._on_message)
                    if peer:
                        await self._saludar(peer)
            else:
                # Conexión directa como peer normal
                peer = await conectar(h, p, self._on_message)
                if peer:
                    await self._saludar(peer)

        await self._loop()

    async def _conectar_seed(self, host: str, port: int) -> list[dict]:
        """
        Intenta conectarse a un seed node para obtener lista de peers.
        Si el nodo no es un seed, retorna lista vacía y se conecta normal.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5
            )
            # Mandar HELLO con nuestra info
            msg = json.dumps({
                "type":    "HELLO",
                "node_id": self.node_id,
                "host":    self.public_host,
                "port":    self.port,
            }) + "\n"
            writer.write(msg.encode())
            await writer.drain()

            # Esperar respuesta
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
        while True:
            await asyncio.sleep(30)
            await self._iniciar_ronda()

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
            self._commitments[msg["node_id"]] = msg["commitment"]
            logger.info(f"Commitment {msg['node_id'][:8]} ({len(self._commitments)}/{len(self._workers_activos)})")
            await self._revisar_commitments()

        elif tipo == "REVEAL":
            self._reveals[msg["node_id"]] = {
                "respuesta":  msg["respuesta"],
                "nonce":      msg["nonce"],
                "commitment": msg["commitment"],
                "node_id":    msg["node_id"],
            }
            logger.info(f"Reveal {msg['node_id'][:8]} ({len(self._reveals)}/{len(self._workers_activos)})")
            await self._resolver_ronda()

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

        loop = asyncio.get_event_loop()
        respuesta = await loop.run_in_executor(None, inference.correr_modelo, msg["prompt"])

        commitment, nonce = inference.hacer_commitment(respuesta)
        self._respuesta_local  = respuesta
        self._nonce_local      = nonce
        self._commitment_local = commitment

        await coordinador.enviar({
            "type":       "COMMITMENT",
            "node_id":    self.node_id,
            "prompt_id":  prompt_id,
            "commitment": commitment,
        })
        logger.info(f"Commitment enviado {prompt_id[:8]}")

    async def _revelar_respuesta(self, coordinador: Peer, prompt_id: str):
        await coordinador.enviar({
            "type":       "REVEAL",
            "node_id":    self.node_id,
            "prompt_id":  prompt_id,
            "respuesta":  self._respuesta_local,
            "nonce":      self._nonce_local,
            "commitment": self._commitment_local,
        })
        logger.info(f"Reveal enviado {prompt_id[:8]}")

    # ------------------------------------------------------------------
    # Coordinador: gestionar ronda
    # ------------------------------------------------------------------

    async def coordinar_prompt(self, prompt: str) -> str | None:
        if not self.peers:
            logger.warning("Sin peers conectados.")
            return None

        self._prompt_activo   = uuid.uuid4().hex
        self._prompt_texto    = prompt
        self._commitments     = {}
        self._reveals         = {}
        self._resultado_final = None

        n = min(3, len(self.peers))
        self._workers_activos = random.sample(list(self.peers.values()), n)
        logger.info(f"Workers: {[p.node_id[:8] for p in self._workers_activos]}")

        for peer in self._workers_activos:
            await peer.enviar({
                "type":      "PROMPT_REQ",
                "node_id":   self.node_id,
                "prompt_id": self._prompt_activo,
                "prompt":    prompt,
            })

        for _ in range(120):
            await asyncio.sleep(1)
            if self._resultado_final is not None:
                return self._resultado_final

        logger.warning("Timeout.")
        return None

    async def _revisar_commitments(self):
        if len(self._commitments) < len(self._workers_activos):
            return
        logger.info("Commitments completos — pidiendo reveals...")
        for peer in self._workers_activos:
            if peer.node_id in self._commitments:
                await peer.enviar({
                    "type":      "REVEAL_REQUEST",
                    "prompt_id": self._prompt_activo,
                })

    async def _resolver_ronda(self):
        if len(self._reveals) < len(self._workers_activos):
            return

        reveals   = list(self._reveals.values())
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

            # Broadcast puntos y la conversación resuelta a todos los nodos
            await self._broadcast({"type": "POINTS_SYNC", "puntos": self.ledger.snapshot()})
            await self._broadcast({
                "type":     "CONV_RESULT",
                "prompt":   self._prompt_texto,
                "response": respuesta,
                "node_ids": node_ids_correctos,
            })
            logger.info(f"Conversación broadcast a {len(self.peers)} peers")
        else:
            logger.warning("Sin consenso.")

        self._resultado_final = respuesta or "Sin consenso en la red."

    # ------------------------------------------------------------------
    # Pool de datos: cada nodo evalúa localmente
    # ------------------------------------------------------------------

    async def _procesar_conv_resultado(self, msg: dict):
        """
        Cada nodo persistente recibe la conversación resuelta,
        la evalúa con Llama localmente y la guarda en su propio pool.
        """
        prompt   = msg["prompt"]
        response = msg["response"]

        # Guardar como pendiente
        conv_id = self.data_pool.guardar_pendiente(
            prompt=prompt,
            response=response,
            node_ids=msg.get("node_ids", []),
        )

        # Evaluar con Llama (árbitro local)
        loop  = asyncio.get_event_loop()
        score = await loop.run_in_executor(None, arbiter.evaluar, prompt, response)
        self.ledger.sumar(self.node_id, PUNTOS_ARBITRO)

        # Registrar voto y resolver
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
            "node_id":   self.node_id,
            "peers":     list(self.peers.keys()),
            "ronda":     self.ronda_actual,
            "puntos":    self.ledger.snapshot(),
            "pool":      self.data_pool.stats(),
        }
