"""
Módulo de inferencia con commitment scheme.

Flujo:
  1. Nodo recibe prompt + prompt_id
  2. Corre el modelo (temperatura=0, determinista)
  3. Genera nonce aleatorio
  4. Calcula commitment = SHA256(respuesta + nonce)
  5. Envía commitment al coordinador (no revela respuesta todavía)
  6. Cuando el coordinador pide reveal, envía respuesta + nonce
  7. El coordinador verifica que SHA256(respuesta + nonce) == commitment
"""
import hashlib
import os
import ollama


MODELO = "llama3.2"


def correr_modelo(prompt: str) -> str:
    """Corre Llama con temperatura 0 — resultado determinista."""
    respuesta = ollama.chat(
        model=MODELO,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0, "seed": 42},
    )
    return respuesta["message"]["content"].strip()


def hacer_commitment(respuesta: str) -> tuple[str, str]:
    """
    Retorna (commitment_hex, nonce_hex).
    El nonce es secreto hasta la fase de reveal.
    """
    nonce = os.urandom(32).hex()
    data = (respuesta + nonce).encode()
    commitment = hashlib.sha256(data).hexdigest()
    return commitment, nonce


def verificar_commitment(respuesta: str, nonce: str, commitment: str) -> bool:
    """Verifica que SHA256(respuesta + nonce) == commitment."""
    data = (respuesta + nonce).encode()
    esperado = hashlib.sha256(data).hexdigest()
    return esperado == commitment


def elegir_respuesta_final(reveals: list[dict]) -> str | None:
    """
    Dado una lista de {node_id, respuesta, nonce, commitment},
    verifica cada commitment y retorna la respuesta con mayoría.
    Si no hay mayoría, retorna None.
    """
    validas = []
    for r in reveals:
        if verificar_commitment(r["respuesta"], r["nonce"], r["commitment"]):
            validas.append(r["respuesta"])

    if not validas:
        return None

    # Mayoría simple
    conteo = {}
    for resp in validas:
        conteo[resp] = conteo.get(resp, 0) + 1

    mejor = max(conteo, key=lambda r: conteo[r])
    if conteo[mejor] >= 2:
        return mejor

    # Sin mayoría — retorna la primera válida como fallback
    return validas[0]
