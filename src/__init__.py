# src/__init__.py
import os
import sys
from pathlib import Path

__version__ = "1.0.0"

# Adiciona o diretório atual ao path para imports absolutos
_package_dir = Path(__file__).parent
if str(_package_dir) not in sys.path:
    sys.path.insert(0, str(_package_dir))

# Função helper para carregar configuração
def load_config(config_path=None):
    """Carrega configuração do bot."""
    from .core.config import Config
    return Config(config_path)

# Função helper para executar o bot
def run(config_path=None, test_mode=False):
    """Executa o bot DOU."""
    from .main import run_bot
    return run_bot(config_path, test_mode)

# Logger do pacote
import logging
logger = logging.getLogger(__name__)

# Exports principais
from .core.config import Config
from .main import main

__all__ = ['Config', 'main', 'load_config', 'run', 'logger']
