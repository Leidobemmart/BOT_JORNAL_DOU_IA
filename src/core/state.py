# Gerenciamento de estado (seen.json)
"""
Gerenciamento de estado (publicações já vistas).
"""
import json
from pathlib import Path
from typing import Set, List, Optional
import logging

logger = logging.getLogger(__name__)


class StateManager:
    """Gerencia o estado das publicações já processadas."""
    
    def __init__(self, state_file: Path = None):
        if state_file is None:
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent
            state_file = project_root / "state" / "seen.json"
        
        self.state_file = state_file
        self._seen: Set[str] = set()
        
    def load(self) -> Set[str]:
        """Carrega o estado do arquivo."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.state_file.exists():
            logger.info("Arquivo de estado não encontrado, criando novo.")
            self._seen = set()
            return self._seen
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                self._seen = set(data)
            else:
                self._seen = set()
                logger.warning("Formato inválido no arquivo de estado.")
            
            logger.info(f"Carregados {len(self._seen)} itens do estado.")
            return self._seen
            
        except Exception as e:
            logger.error(f"Erro ao carregar estado: {e}")
            self._seen = set()
            return self._seen
    
    def save(self) -> None:
        """Salva o estado no arquivo."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(sorted(self._seen), f, ensure_ascii=False, indent=2)
            
            logger.info(f"Estado salvo com {len(self._seen)} itens.")
            
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
            raise
    
    def add(self, publication) -> None:
        """Adiciona uma publicação ao estado."""
        from models.publication import Publication
        
        if isinstance(publication, Publication):
            url = publication.url
            pub_id = publication.extract_id()
        elif isinstance(publication, str):
            url = publication
            pub_id = None
        else:
            raise ValueError("Tipo inválido para publicação")
        
        # Adicionar chave da URL
        url_key = f"url:{url}"
        self._seen.add(url_key)
        
        # Adicionar chave do ID se disponível
        if pub_id:
            id_key = f"id:{pub_id}"
            self._seen.add(id_key)
    
    def add_batch(self, publications) -> None:
        """Adiciona múltiplas publicações ao estado."""
        for pub in publications:
            self.add(pub)
    
    def contains(self, publication) -> bool:
        """Verifica se uma publicação já foi vista."""
        from ..models.publication import Publication
        
        if isinstance(publication, Publication):
            url = publication.url
            pub_id = publication.extract_id()
        elif isinstance(publication, str):
            url = publication
            pub_id = None
        else:
            return False
        
        # Verificar por URL
        url_key = f"url:{url}"
        if url_key in self._seen:
            return True
        
        # Verificar por ID
        if pub_id:
            id_key = f"id:{pub_id}"
            if id_key in self._seen:
                return True
        
        return False
    
    def filter_unseen(self, publications: List) -> List:
        """Filtra apenas publicações não vistas."""
        return [pub for pub in publications if not self.contains(pub)]
    
    def clear(self) -> None:
        """Limpa o estado."""
        self._seen.clear()
        logger.info("Estado limpo.")
    
    @property
    def count(self) -> int:
        """Retorna o número de itens no estado."""
        return len(self._seen)
