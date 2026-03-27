"""
Tipos de mensajes y serialización del protocolo P2P.
"""
import json
from enum import Enum


class MsgType(str, Enum):
    # Conexión
    HELLO        = "HELLO"         # Nodo se presenta al conectarse
    PONG         = "PONG"          # Respuesta a HELLO

    # Coordinador
    VRF_ANNOUNCE = "VRF_ANNOUNCE"  # Nodo anuncia su VRF para ser coordinador

    # Inferencia
    PROMPT_REQ   = "PROMPT_REQ"    # Coordinador distribuye prompt a nodos
    COMMITMENT   = "COMMITMENT"    # Nodo envía hash(respuesta+nonce) — fase 1
    REVEAL       = "REVEAL"        # Nodo revela respuesta y nonce — fase 2
    RESULT       = "RESULT"        # Coordinador devuelve resultado final al usuario

    # Puntos
    POINTS_SYNC  = "POINTS_SYNC"   # Nodo comparte su ledger de puntos

    # Pool de datos
    CONV_RESULT  = "CONV_RESULT"   # Coordinador broadcast conversación resuelta a todos los nodos


def encode(msg_type: MsgType, payload: dict) -> bytes:
    msg = {"type": msg_type.value, **payload}
    return (json.dumps(msg) + "\n").encode()


def decode(raw: bytes) -> dict:
    return json.loads(raw.decode().strip())
