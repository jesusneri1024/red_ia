"""
Identidad persistente del nodo.

Guarda el keypair Ed25519 en disco para que el node_id
sea el mismo aunque el proceso se reinicie.

Cada nodo guarda su identidad en:
  ~/.red_ia/<port>/identity.json
"""
import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)

logger = logging.getLogger(__name__)


def _directorio(port: int) -> Path:
    d = Path.home() / ".red_ia" / str(port)
    d.mkdir(parents=True, exist_ok=True)
    return d


def cargar_o_crear(port: int) -> dict:
    """
    Carga la identidad del nodo desde disco.
    Si no existe, genera un nuevo keypair y lo guarda.

    Retorna:
      {
        "node_id":       str   — primeros 16 bytes del pubkey en hex
        "privkey":       Ed25519PrivateKey
        "privkey_bytes": bytes
        "pubkey_bytes":  bytes
        "creado":        str   — ISO timestamp
        "es_nuevo":      bool  — True si se acaba de crear
      }
    """
    ruta = _directorio(port) / "identity.json"

    if ruta.exists():
        with open(ruta) as f:
            datos = json.load(f)

        privkey_bytes = base64.b64decode(datos["privkey_b64"])
        privkey       = Ed25519PrivateKey.from_private_bytes(privkey_bytes)
        pubkey_bytes  = base64.b64decode(datos["pubkey_b64"])
        node_id       = datos["node_id"]

        logger.info(f"Identidad cargada: {node_id} (creada {datos['creado']})")
        return {
            "node_id":       node_id,
            "privkey":       privkey,
            "privkey_bytes": privkey_bytes,
            "pubkey_bytes":  pubkey_bytes,
            "creado":        datos["creado"],
            "es_nuevo":      False,
        }

    # Primera vez — generar keypair
    privkey       = Ed25519PrivateKey.generate()
    privkey_bytes = privkey.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pubkey_bytes  = privkey.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    node_id       = pubkey_bytes.hex()[:16]
    creado        = datetime.now(timezone.utc).isoformat()

    with open(ruta, "w") as f:
        json.dump({
            "node_id":    node_id,
            "privkey_b64": base64.b64encode(privkey_bytes).decode(),
            "pubkey_b64":  base64.b64encode(pubkey_bytes).decode(),
            "creado":      creado,
        }, f, indent=2)

    logger.info(f"Nueva identidad generada: {node_id} → {ruta}")
    return {
        "node_id":       node_id,
        "privkey":       privkey,
        "privkey_bytes": privkey_bytes,
        "pubkey_bytes":  pubkey_bytes,
        "creado":        creado,
        "es_nuevo":      True,
    }


def ruta_ledger(port: int) -> Path:
    """Retorna la ruta del ledger ligada a este nodo."""
    return _directorio(port) / "ledger.json"
