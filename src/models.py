from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


# ==== Email ====

@dataclass
class EmailSettings:
    """Configuração de emails (remetente e destinatários)."""
    from_addr: str
    to: List[str] = field(default_factory=list)
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)

    @property
    def all_recipients(self) -> List[str]:
        return list(dict.fromkeys(self.to + self.cc + self.bcc))  # remove duplicados simples


# ==== IA ====

@dataclass
class AIConfig:
    """Configuração de IA para resumos."""
    enabled: bool = False
    model: str = "gemini-1.5-flash"


# ==== Busca (ainda não usamos, mas já deixamos pronto) ====

@dataclass
class SearchConfig:
    """Configuração de busca no DOU."""
    phrases: List[str] = field(default_factory=list)
    sections: List[str] = field(default_factory=lambda: ["do1"])
    period: str = "today"  # today | week | month | any


# ==== Publicações ====

@dataclass(eq=False)
class Publication:
    """Representa uma publicação do DOU."""

    url: str
    title: str
    orgao: Optional[str] = None
    tipo: Optional[str] = None
    numero: Optional[str] = None
    data: Optional[str] = None
    secao: Optional[str] = None
    pagina: Optional[str] = None

    texto_bruto: Optional[str] = None
    texto_limpo: Optional[str] = None
    resumo_ia: Optional[str] = None

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


# ==== Configuração geral do app ====

@dataclass
class SMTPSettings:
    host: str
    port: int
    user: str
    password: str
    use_tls: bool = True


@dataclass
class AppConfig:
    """Configuração completa do robô."""
    search: SearchConfig
    ai: AIConfig
    email: EmailSettings
    smtp: SMTPSettings
