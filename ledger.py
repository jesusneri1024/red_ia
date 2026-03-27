"""
Ledger de puntos — registro de contribuciones de cada nodo.
En el MVP es un dict en memoria que se sincroniza entre peers.
En fase 3 migra a un ledger distribuido con consenso real.
"""
import json
import os
from pathlib import Path


class Ledger:
    def __init__(self, ruta: Path = None):
        self._ruta   = ruta or (Path(__file__).parent / "ledger.json")
        self._puntos: dict[str, int] = {}
        self._cargar()

    def _cargar(self):
        if self._ruta.exists():
            with open(self._ruta) as f:
                self._puntos = json.load(f)

    def _guardar(self):
        with open(self._ruta, "w") as f:
            json.dump(self._puntos, f, indent=2)

    def sumar(self, node_id: str, puntos: int):
        self._puntos[node_id] = self._puntos.get(node_id, 0) + puntos
        self._guardar()

    def restar(self, node_id: str, puntos: int):
        actual = self._puntos.get(node_id, 0)
        self._puntos[node_id] = max(0, actual - puntos)
        self._guardar()

    def balance(self, node_id: str) -> int:
        return self._puntos.get(node_id, 0)

    def snapshot(self) -> dict[str, int]:
        return dict(self._puntos)

    def merge(self, otro: dict[str, int]):
        """
        Recibe el ledger de otro nodo y toma el máximo por nodo.
        Estrategia simple de resolución de conflictos para el MVP.
        """
        for node_id, puntos in otro.items():
            self._puntos[node_id] = max(
                self._puntos.get(node_id, 0), puntos
            )
        self._guardar()

    def __repr__(self):
        return f"Ledger({self._puntos})"
