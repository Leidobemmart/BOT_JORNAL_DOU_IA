# Carregamento de configuração
"""
Carregamento e validação de configuração.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any
import yaml

# CORREÇÃO CRÍTICA: Ajustar o path para importações corretas
# Adiciona o diretório src ao sys.path se não estiver presente
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent  # src/core -> src -> projeto
src_path = current_dir.parent  # src/core -> src

# Adiciona o src ao path do Python
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from models.publication import SearchConfig, EmailConfig, AIConfig
except ImportError as e:
    # Fallback: tenta importar de forma relativa
    try:
        # Tenta importar do diretório acima (src)
        sys.path.insert(0, str(project_root))
        from src.models.publication import SearchConfig, EmailConfig, AIConfig
    except ImportError:
        # Último fallback: importa diretamente
        try:
            from ..models.publication import SearchConfig, EmailConfig, AIConfig
        except ImportError:
            raise ImportError(f"Não foi possível importar models.publication: {e}")


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
        host = os.getenv('SMTP_HOST')
        port_str = os.getenv('SMTP_PORT', '587')
        
        # Tratar conversão de porta com segurança
        try:
            port = int(port_str) if port_str else 587
        except ValueError:
            port = 587
        
        return {
            'host': host,
            'port': port,
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
            missing_fields = []
            for key, value in smtp_config.items():
                if key == 'port':
                    # Porta tem valor padrão, só verifica se não é None
                    if value is None:
                        missing_fields.append(key)
                elif not value:  # Para host, user, password
                    missing_fields.append(key)
            
            if missing_fields:
                raise ValueError(f"Configuração SMTP incompleta: {missing_fields}")
            
            return True
            
        except Exception as e:
            raise ValueError(f"Configuração inválida: {e}")
