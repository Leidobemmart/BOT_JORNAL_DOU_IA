# Data classes
"""
Data classes para representar publicações do DOU.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Tuple

@dataclass
class Publication:
    """Representa uma publicação do DOU."""
    url: str
    titulo: str
    orgao: Optional[str] = None
    tipo: Optional[str] = None  # LEI, PORTARIA, DECRETO, etc.
    numero: Optional[str] = None
    data: Optional[str] = None  # DD/MM/YYYY
    secao: Optional[str] = None
    pagina: Optional[str] = None
    texto_bruto: Optional[str] = None
    texto_limpo: Optional[str] = None
    resumo_ia: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Converte para dicionário para serialização."""
        return {
            'url': self.url,
            'titulo': self.titulo,
            'orgao': self.orgao,
            'tipo': self.tipo,
            'numero': self.numero,
            'data': self.data,
            'secao': self.secao,
            'pagina': self.pagina,
            'texto_bruto': self.texto_bruto,
            'texto_limpo': self.texto_limpo,
            'resumo_ia': self.resumo_ia
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Publication':
        """Cria a partir de um dicionário."""
        return cls(
            url=data.get('url', ''),
            titulo=data.get('titulo', ''),
            orgao=data.get('orgao'),
            tipo=data.get('tipo'),
            numero=data.get('numero'),
            data=data.get('data'),
            secao=data.get('secao'),
            pagina=data.get('pagina'),
            texto_bruto=data.get('texto_bruto'),
            texto_limpo=data.get('texto_limpo'),
            resumo_ia=data.get('resumo_ia')
        )
    
    @property
    def headline(self) -> str:
        """Retorna o título formatado para exibição."""
        parts = []
        if self.tipo and self.numero:
            parts.append(f"{self.tipo} {self.numero}")
        elif self.tipo:
            parts.append(self.tipo)
        
        if parts:
            return f"{' - '.join(parts)} - {self.titulo}"
        return self.titulo
    
    @property
    def is_valid(self) -> bool:
        """Verifica se a publicação é válida."""
        return bool(self.url and self.titulo)
    
    def extract_id(self) -> Optional[str]:
        """Extrai o ID da matéria da URL."""
        import re
        match = re.search(r'/-(?:[^/]+/)*(\d{6,})/?$', self.url)
        return match.group(1) if match else None


@dataclass
class SearchConfig:
    """Configuração de busca."""
    phrases: List[str]
    sections: List[str]
    period: str
    days_window: int
    enrich_listing: bool
    max_pages: int
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> 'SearchConfig':
        """Cria a partir do dicionário de configuração."""
        search_cfg = config_dict.get('search', {})
        
        return cls(
            phrases=search_cfg.get('phrases', []),
            sections=search_cfg.get('sections', ['do1']),
            period=search_cfg.get('period', 'today'),
            days_window=search_cfg.get('days_window', 1),
            enrich_listing=search_cfg.get('enrich_listing', True),
            max_pages=config_dict.get('pagination', {}).get('max_pages', 5)
        )

@dataclass
class EmailConfig:
    """Configuração de email."""
    subject_prefix: str
    to: List[str]
    from_: str
    cc: Optional[List[str]] = None  # NOVO
    bcc: Optional[List[str]] = None  # NOVO
    smtp_config: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> 'EmailConfig':
        """Cria a partir do dicionário de configuração."""
        email_cfg = config_dict.get('email', {})
        
        return cls(
            subject_prefix=email_cfg.get('subject_prefix', '[DOU]'),
            to=email_cfg.get('to', []),
            from_=email_cfg.get('from_', ''),
            cc=email_cfg.get('cc', []),  # NOVO
            bcc=email_cfg.get('bcc', []),  # NOVO
            smtp_config=email_cfg.get('smtp', {})
        )

@dataclass  
class AIConfig:
    """Configuração de IA."""
    enabled: bool
    model: str
    max_chars_input: int
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> 'AIConfig':
        """Cria a partir do dicionário de configuração."""
        ai_cfg = config_dict.get('ai', {}).get('summaries', {})
        
        return cls(
            enabled=ai_cfg.get('enabled', False),
            model=ai_cfg.get('model', 'recogna-nlp/ptt5-base-summ-xlsum'),
            max_chars_input=ai_cfg.get('max_chars_input', 5000)
        )
