# Carregamento de configuração
"""
Carregamento e validação de configuração.
"""
import os
from pathlib import Path
from typing import Dict, Any
import yaml

from ..models.publication import SearchConfig, EmailConfig, AIConfig


class Config:
    """Gerencia a configuração do robô."""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or self._get_default_config_path()
        self._raw_config = None
        self._search_config = None
        self._email_config = None
        self._ai_config = None
        
    def _get_default_config_path(self) -> Path:
        """Retorna o caminho padrão para o config.yml."""
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent  # src/core -> src -> projeto
        return project_root / "config.yml"
    
    def load(self) -> Dict[str, Any]:
        """Carrega a configuração do arquivo YAML."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Arquivo de configuração não encontrado: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._raw_config = yaml.safe_load(f)
        
        if not isinstance(self._raw_config, dict):
            raise ValueError("Configuração inválida: deve ser um dicionário")
        
        # Validar configurações mínimas
        if 'search' not in self._raw_config:
            raise ValueError("Configuração inválida: seção 'search' ausente")
        
        if 'email' not in self._raw_config:
            raise ValueError("Configuração inválida: seção 'email' ausente")
        
        return self._raw_config
    
    @property
    def raw(self) -> Dict[str, Any]:
        """Retorna a configuração bruta."""
        if self._raw_config is None:
            self.load()
        return self._raw_config
    
    @property
    def search(self) -> SearchConfig:
        """Retorna a configuração de busca."""
        if self._search_config is None:
            self._search_config = SearchConfig.from_dict(self.raw)
        return self._search_config
    
    @property
    def email(self) -> EmailConfig:
        """Retorna a configuração de email."""
        if self._email_config is None:
            self._email_config = EmailConfig.from_dict(self.raw)
        return self._email_config
    
    @property
    def ai(self) -> AIConfig:
        """Retorna a configuração de IA."""
        if self._ai_config is None:
            self._ai_config = AIConfig.from_dict(self.raw)
        return self._ai_config
    
    @property
    def filters(self) -> Dict[str, Any]:
        """Retorna os filtros configurados."""
        return self.raw.get('filters', {})
    
    def get_smtp_config(self) -> Dict[str, Any]:
        """Retorna a configuração SMTP das variáveis de ambiente."""
        return {
            'host': os.getenv('SMTP_HOST'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'user': os.getenv('SMTP_USER'),
            'password': os.getenv('SMTP_PASS')
        }
    
    def validate(self) -> bool:
        """Valida se a configuração é válida."""
        try:
            # Verificar seções obrigatórias
            if not self.search.phrases:
                raise ValueError("Nenhuma frase de busca configurada")
            
            if not self.email.to:
                raise ValueError("Nenhum destinatário configurado")
            
            if not self.email.from_ and not os.getenv('MAIL_FROM'):
                raise ValueError("Remetente não configurado")
            
            # Verificar configuração SMTP
            smtp_config = self.get_smtp_config()
            if not all(smtp_config.values()):
                missing = [k for k, v in smtp_config.items() if not v]
                raise ValueError(f"Configuração SMTP incompleta: {missing}")
            
            return True
            
        except Exception as e:
            raise ValueError(f"Configuração inválida: {e}")
