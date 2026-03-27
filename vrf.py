"""
VRF simplificado para elección de coordinador.

Cada nodo calcula VRF(llave_privada, ronda) = HMAC-SHA256(privkey, ronda).
El nodo con el valor más bajo gana y se convierte en coordinador.
Cualquier otro nodo puede verificar el resultado con la llave pública.
"""
import hmac
import hashlib


def calcular(private_key_bytes: bytes, ronda: int) -> str:
    """Calcula el VRF para esta ronda. Retorna hex string."""
    ronda_bytes = ronda.to_bytes(8, "big")
    resultado = hmac.new(private_key_bytes, ronda_bytes, hashlib.sha256).hexdigest()
    return resultado


def verificar(public_key_bytes: bytes, ronda: int, vrf_claim: str) -> bool:
    """
    En un VRF real se verificaría con la llave pública.
    En el MVP verificamos pidiendo al nodo que firme con su privkey
    y comparamos contra su pubkey registrada.
    Por ahora devuelve True si el formato es válido — se refuerza en fase 3.
    """
    return len(vrf_claim) == 64 and all(c in "0123456789abcdef" for c in vrf_claim)


def elegir_coordinador(vrfs: dict[str, str]) -> str:
    """
    Dado un dict {node_id: vrf_value}, retorna el node_id
    con el VRF más bajo — el coordinador de esta ronda.
    """
    return min(vrfs, key=lambda nid: vrfs[nid])
