from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(eq=False)
class Publication:
    """
    Representa uma publicação do DOU (modelo simplificado).
    """

    title: str
    url: str

    section: Optional[str] = None          # ex: "DO1"
    pub_date: Optional[date] = None        # data da edição
    organ: Optional[str] = None            # órgão responsável
    tipo: Optional[str] = None             # tipo de ato (Portaria, Resolução...)
    numero: Optional[str] = None           # número do ato

    raw_text: Optional[str] = None         # texto completo bruto
    clean_text: Optional[str] = None       # texto limpo
    summary: Optional[str] = None          # resumo (IA ou regra simples)

    @property
    def id(self) -> str:
        """Identificador único da publicação (por enquanto, a própria URL)."""
        return self.url

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Publication):
            return False
        return self.id == other.id

    def as_line(self) -> str:
        """
        Linha amigável para usar em texto plano do email.
        """
        parts = [self.title, f"({self.url})"]
        return " ".join(parts)
