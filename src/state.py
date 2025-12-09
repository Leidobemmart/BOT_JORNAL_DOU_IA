from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Set

from .models import Publication

logger = logging.getLogger(__name__)


class StateManager:
    """Gerencia publicações já vistas (para não reenviar)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parent.parent / "state" / "seen.json"
        self._seen: Set[str] = set()
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return

        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._seen = set()
            self._loaded = True
            logger.info("Estado inicializado (sem arquivo existente).")
            return

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f) or []
            self._seen = set(str(x) for x in data)
            logger.info("Estado carregado (%d itens).", len(self._seen))
        except Exception as e:
            logger.error("Erro ao carregar estado %s: %s", self.path, e)
            self._seen = set()

        self._loaded = True

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(sorted(self._seen), f, ensure_ascii=False, indent=2)
            logger.info("Estado salvo (%d itens).", len(self._seen))
        except Exception as e:
            logger.error("Erro ao salvar estado %s: %s", self.path, e)

    def has(self, pub: Publication) -> bool:
        return pub.id in self._seen

    def add(self, pub: Publication) -> None:
        self._seen.add(pub.id)

    def add_many(self, pubs: list[Publication]) -> None:
        for p in pubs:
            self.add(p)
