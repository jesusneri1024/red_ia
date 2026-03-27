"""
Pool de datos de entrenamiento.

Guarda conversaciones verificadas y las clasifica según
el score que les da el árbitro (Llama).

Cada entrada en el pool:
  {
    "id":            str   — UUID de la conversación
    "prompt":        str   — pregunta del usuario
    "response":      str   — respuesta elegida por consenso
    "node_ids":      list  — nodos que contribuyeron
    "timestamp":     str   — ISO timestamp
    "score":         float — score promedio del árbitro (0.0-1.0)
    "status":        str   — "pending" | "approved" | "rejected"
    "arbiter_votes": list  — votos individuales de cada árbitro
  }

Las entradas aprobadas se exportan en formato instrucción/respuesta
listo para fine-tuning con LoRA.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCORE_MINIMO = 0.7   # Score mínimo para aprobar una conversación
PUNTOS_DATO_APROBADO = 5  # Puntos extra al nodo cuya respuesta fue aprobada


class DataPool:
    def __init__(self, ruta_dir: Path):
        self._ruta_pool     = ruta_dir / "pool.jsonl"
        self._ruta_training = ruta_dir / "training.jsonl"

    def guardar_pendiente(self, prompt: str, response: str, node_ids: list[str]) -> str:
        """
        Guarda una conversación nueva con status 'pending'.
        Retorna el ID de la conversación.
        """
        conv_id = uuid.uuid4().hex
        entrada = {
            "id":            conv_id,
            "prompt":        prompt,
            "response":      response,
            "node_ids":      node_ids,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "score":         None,
            "status":        "pending",
            "arbiter_votes": [],
        }
        self._append(self._ruta_pool, entrada)
        return conv_id

    def registrar_voto(self, conv_id: str, node_id: str, score: float):
        """Añade el voto de un árbitro a una conversación."""
        entradas = self._leer_todo()
        for e in entradas:
            if e["id"] == conv_id:
                e["arbiter_votes"].append({"node_id": node_id, "score": score})
                break
        self._escribir_todo(entradas)

    def resolver(self, conv_id: str) -> tuple[str, float]:
        """
        Promedia los votos y marca la conversación como aprobada o rechazada.
        Retorna (status, score_promedio).
        """
        entradas = self._leer_todo()
        for e in entradas:
            if e["id"] == conv_id:
                votos = e["arbiter_votes"]
                if not votos:
                    return "rejected", 0.0

                score = sum(v["score"] for v in votos) / len(votos)
                e["score"]  = round(score, 3)
                e["status"] = "approved" if score >= SCORE_MINIMO else "rejected"

                # Si se aprueba, exportar al archivo de entrenamiento
                if e["status"] == "approved":
                    self._append(self._ruta_training, {
                        "instruction": e["prompt"],
                        "output":      e["response"],
                    })

                self._escribir_todo(entradas)
                return e["status"], score

        return "not_found", 0.0

    def stats(self) -> dict:
        entradas = self._leer_todo()
        total     = len(entradas)
        aprobadas = sum(1 for e in entradas if e["status"] == "approved")
        pendientes = sum(1 for e in entradas if e["status"] == "pending")
        rechazadas = sum(1 for e in entradas if e["status"] == "rejected")
        training_size = sum(1 for _ in self._iter_training())
        return {
            "total":         total,
            "aprobadas":     aprobadas,
            "pendientes":    pendientes,
            "rechazadas":    rechazadas,
            "training_size": training_size,
        }

    def training_data(self) -> list[dict]:
        """Retorna todas las conversaciones aprobadas listas para entrenamiento."""
        return list(self._iter_training())

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    def _append(self, ruta: Path, datos: dict):
        with open(ruta, "a") as f:
            f.write(json.dumps(datos, ensure_ascii=False) + "\n")

    def _leer_todo(self) -> list[dict]:
        if not self._ruta_pool.exists():
            return []
        entradas = []
        with open(self._ruta_pool) as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    entradas.append(json.loads(linea))
        return entradas

    def _escribir_todo(self, entradas: list[dict]):
        with open(self._ruta_pool, "w") as f:
            for e in entradas:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def _iter_training(self):
        if not self._ruta_training.exists():
            return
        with open(self._ruta_training) as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    yield json.loads(linea)
