# src/publication.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Publication:
    """
    Representa uma publicação encontrada no DOU (forma simplificada).
    """

    title: str
    url: str

    # Campos opcionais – vamos preencher quando tiver o scraper real
    section: Optional[str] = None          # ex: "DO1"
    pub_date: Optional[date] = None        # data da edição
    organ: Optional[str] = None            # órgão responsável (se conseguirmos extrair)
    raw_text: Optional[str] = None         # texto completo
    summary: Optional[str] = None          # resumo (IA ou regra simples)

    def as_line(self) -> str:
        """
        Linha amigável para usar no corpo do e-mail.
        """
        parts = [self.title, f"({self.url})"]
        return " ".join(parts)
