"""
Registro público de versiones del modelo.

Cada vez que el modelo cambia (nueva versión base, fine-tuning, etc.)
se registra una entrada con su hash, timestamp, y métricas.

Este historial es público, inmutable y verificable por cualquier nodo.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


RUTA_DEFAULT = Path.home() / ".red_ia" / "model_history.json"


class ModelRegistry:
    def __init__(self, ruta: Path = None):
        self._ruta = ruta or RUTA_DEFAULT
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._historial = self._cargar()

        # Si está vacío, registrar versión inicial
        if not self._historial:
            self._registrar_genesis()

    def _cargar(self) -> list[dict]:
        if self._ruta.exists():
            with open(self._ruta) as f:
                return json.load(f)
        return []

    def _guardar(self):
        with open(self._ruta, "w") as f:
            json.dump(self._historial, f, indent=2, ensure_ascii=False)

    def _hash_entrada(self, entrada: dict) -> str:
        """Hash de la entrada para encadenar el historial."""
        datos = json.dumps(entrada, sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(datos).hexdigest()

    def _registrar_genesis(self):
        entrada = {
            "version":            "0.1.0",
            "timestamp":          datetime.now(timezone.utc).isoformat(),
            "base_model":         "llama3.2",
            "tipo":               "genesis",
            "descripcion":        "Red IA testnet launch — base Llama 3.2 model",
            "conversaciones":     0,
            "score_promedio":     None,
            "nodos_participantes": 0,
            "prev_hash":          "0" * 64,
        }
        entrada["hash"] = self._hash_entrada(entrada)
        self._historial.append(entrada)
        self._guardar()

    def registrar_version(
        self,
        tipo: str,           # "fine-tune" | "base-update" | "config-change"
        descripcion: str,
        conversaciones: int,
        score_promedio: float,
        nodos_participantes: int,
        base_model: str = "llama3.2",
        version: str = None,
    ) -> dict:
        """Registra una nueva versión del modelo en el historial."""
        prev = self._historial[-1] if self._historial else {"hash": "0" * 64, "version": "0.0.0"}
        prev_hash = prev["hash"]

        # Auto-incrementar versión
        if not version:
            partes = prev["version"].split(".")
            partes[-1] = str(int(partes[-1]) + 1)
            version = ".".join(partes)

        entrada = {
            "version":             version,
            "timestamp":           datetime.now(timezone.utc).isoformat(),
            "base_model":          base_model,
            "tipo":                tipo,
            "descripcion":         descripcion,
            "conversaciones":      conversaciones,
            "score_promedio":      score_promedio,
            "nodos_participantes": nodos_participantes,
            "prev_hash":           prev_hash,
        }
        entrada["hash"] = self._hash_entrada(entrada)
        self._historial.append(entrada)
        self._guardar()
        return entrada

    def historial(self) -> list[dict]:
        return list(self._historial)

    def ultima_version(self) -> dict:
        return self._historial[-1] if self._historial else {}

    def verificar_integridad(self) -> bool:
        """Verifica que ninguna entrada del historial fue modificada."""
        for entrada in self._historial:
            hash_guardado = entrada.get("hash")
            copia = {k: v for k, v in entrada.items() if k != "hash"}
            hash_calculado = self._hash_entrada(copia)
            if hash_guardado != hash_calculado:
                return False
        return True
