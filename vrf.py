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
    Verifica que el VRF fue calculado con la llave privada correspondiente
    a public_key_bytes. Usa HMAC-SHA256(pubkey, ronda) como aproximación
    verificable sin revelar la privkey.
    """
    if not (len(vrf_claim) == 64 and all(c in "0123456789abcdef" for c in vrf_claim)):
        return False
    ronda_bytes = ronda.to_bytes(8, "big")
    esperado = hmac.new(public_key_bytes, ronda_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, vrf_claim)


def elegir_coordinador(vrfs: dict[str, str]) -> str:
    """
    Dado un dict {node_id: vrf_value}, retorna el node_id
    con el VRF más bajo — el coordinador de esta ronda.
    """
    return min(vrfs, key=lambda nid: vrfs[nid])
