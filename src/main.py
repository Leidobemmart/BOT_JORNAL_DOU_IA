"""
Robô de monitoramento do Diário Oficial da União (DOU) - Versão Refatorada

Pipeline principal:
1. Carregar configuração
2. Inicializar componentes
3. Executar busca no DOU
4. Processar resultados
5. Enviar email
6. Atualizar estado
"""

import asyncio
import sys
import os
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.logger import setup_logging
from core.config import Config
from core.state import StateManager
from scraper.browser import BrowserManager
from scraper.dou_scraper import DOUScraper
from scraper.extractor import ContentExtractor
from ai.summarizer import Summarizer
from email.builder import EmailBuilder
from email.sender import EmailSender
from models.publication import Publication


class DOUBot:
    """Classe principal do robô DOU."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.config = None
        self.state = None
        self.browser = None
        self.scraper = None
        self.extractor = None
        self.summarizer = None
        self.email_builder = None
        self.email_sender = None
        
    def initialize(self):
        """Inicializa todos os componentes."""
        try:
            self.logger.info("Inicializando robô DOU...")
            
            # Carregar configuração
            self.config = Config()
            self.config.load()
            self.config.validate()
            self.logger.info("Configuração carregada e validada")
            
            # Inicializar gerenciador de estado
            self.state = StateManager()
            self.state.load()
            self.logger.info(f"Estado carregado: {self.state.count} itens")
            
            # Inicializar extrator de conteúdo
            self.extractor = ContentExtractor()
            
            # Inicializar sumarizador IA (se habilitado)
            if self.config.ai.enabled:
                self.summarizer = Summarizer(self.config.ai)
                self.logger.info("Sumarizador IA inicializado")
            else:
                self.logger.info("IA desabilitada na configuração")
            
            # Inicializar construtor de email
            self.email_builder = EmailBuilder(self.config.email)
            
            # Inicializar enviador de email
            smtp_config = self.config.get_smtp_config()
            self.email_sender = EmailSender(smtp_config)
            
            self.logger.info("Inicialização concluída")
            
        except Exception as e:
            self.logger.error(f"Erro na inicialização: {e}")
            raise
    
    async def run(self):
        """Executa o pipeline principal."""
        try:
            # Inicializar navegador
            self.browser = BrowserManager()
            await self.browser.start()
            
            # Inicializar scraper
            self.scraper = DOUScraper(self.browser, self.config.search)
            
            # Executar busca
            self.logger.info("Iniciando busca no DOU...")
            raw_publications = await self.scraper.search()
            
            if not raw_publications:
                self.logger.info("Nenhuma publicação encontrada")
                await self._handle_no_results()
                return
            
            self.logger.info(f"Encontradas {len(raw_publications)} publicações brutas")
            
            # Enriquecer publicações
            publications = await self._enrich_publications(raw_publications)
            
            # Filtrar publicações já vistas
            new_publications = self.state.filter_unseen(publications)
            
            if not new_publications:
                self.logger.info("Nenhuma publicação nova encontrada")
                return
            
            self.logger.info(f"{len(new_publications)} publicações novas")
            
            # Aplicar filtros adicionais
            filtered_publications = self._apply_filters(new_publications)
            
            if not filtered_publications:
                self.logger.info("Nenhuma publicação passou nos filtros")
                return
            
            self.logger.info(f"{len(filtered_publications)} publicações após filtros")
            
            # Gerar resumos IA (se habilitado)
            if self.summarizer:
                filtered_publications = await self._generate_summaries(filtered_publications)
            
            # Ordenar publicações
            filtered_publications.sort(key=lambda x: x.data or "", reverse=True)
            
            # Construir e enviar email
            email_content = self.email_builder.build(filtered_publications)
            await self.email_sender.send(email_content)
            
            # Atualizar estado
            self.state.add_batch(filtered_publications)
            self.state.save()
            
            self.logger.info("Pipeline concluído com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro durante execução: {e}")
            raise
            
        finally:
            #
