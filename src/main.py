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
            # Garantir que o navegador seja fechado
            if self.browser:
                await self.browser.close()
    
    async def _enrich_publications(self, raw_publications):
        """Enriquece as publicações com metadados e conteúdo."""
        publications = []
        
        for raw in raw_publications:
            try:
                # Obter conteúdo completo da página
                html_content = await self.scraper.get_page_content(raw['url'])
                
                # Extrair conteúdo limpo e metadados
                result = self.extractor.extract(html_content, raw['url'])
                
                # Criar objeto Publication
                pub = Publication(
                    url=raw['url'],
                    titulo=result.get('titulo') or raw.get('titulo', 'Sem título'),
                    orgao=result.get('orgao'),
                    tipo=result.get('tipo'),
                    numero=result.get('numero'),
                    data=result.get('data'),
                    secao=result.get('secao'),
                    pagina=result.get('pagina'),
                    texto_bruto=result.get('texto_bruto'),
                    texto_limpo=result.get('texto_limpo')
                )
                
                if pub.is_valid:
                    publications.append(pub)
                    
            except Exception as e:
                self.logger.warning(f"Erro ao enriquecer publicação {raw.get('url')}: {e}")
                continue
        
        return publications
    
    def _apply_filters(self, publications):
        """Aplica filtros configurados às publicações."""
        filtered = []
        filters_cfg = self.config.filters
        
        for pub in publications:
            # Verificar palavras-chave no título
            if not self._passes_title_filter(pub.titulo, filters_cfg.get('title_keywords')):
                continue
            
            # Verificar palavras-chave no órgão
            if not self._passes_orgao_filter(pub.orgao, filters_cfg.get('orgao_keywords')):
                continue
            
            # Verificar filtro de data (edição do dia)
            if self.config.search.period in ['today', 'dia'] and pub.data:
                from utils.validators import parse_br_date
                from datetime import datetime
                
                today = datetime.now().strftime("%d/%m/%Y")
                if pub.data != today:
                    continue
            
            filtered.append(pub)
        
        return filtered
    
    def _passes_title_filter(self, title, keywords):
        """Verifica se o título passa no filtro."""
        from utils.validators import title_contains_keywords
        return title_contains_keywords(title, keywords)
    
    def _passes_orgao_filter(self, orgao, keywords):
        """Verifica se o órgão passa no filtro."""
        from utils.validators import orgao_contains_keywords
        return orgao_contains_keywords(orgao, keywords)
    
    async def _generate_summaries(self, publications):
        """Gera resumos IA para as publicações."""
        for pub in publications:
            try:
                if pub.texto_limpo:
                    summary = await self.summarizer.summarize(
                        pub.texto_limpo,
                        {
                            'tipo': pub.tipo,
                            'numero': pub.numero,
                            'orgao': pub.orgao,
                            'data': pub.data
                        }
                    )
                    if summary:
                        pub.resumo_ia = summary
                        
            except Exception as e:
                self.logger.warning(f"Erro ao gerar resumo para {pub.titulo}: {e}")
        
        return publications
    
    async def _handle_no_results(self):
        """Lida com cenário de nenhum resultado encontrado."""
        # Forçar email de teste se configurado
        if os.getenv('FORCE_TEST_EMAIL', '').lower() in ['1', 'true', 'yes']:
            self.logger.info("Enviando email de teste (FORCE_TEST_EMAIL)")
            
            test_pub = Publication(
                url="https://www.in.gov.br",
                titulo="E-mail de teste do robô DOU",
                tipo="Aviso",
                data=datetime.now().strftime("%d/%m/%Y"),
                texto_limpo="Este é um email de teste enviado porque não foram encontradas publicações relevantes."
            )
            
            email_content = self.email_builder.build([test_pub])
            await self.email_sender.send(email_content)
    
    def cleanup(self):
        """Limpeza de recursos."""
        self.logger.info("Realizando limpeza...")


async def main():
    """Função principal assíncrona."""
    bot = DOUBot()
    
    try:
        bot.initialize()
        await bot.run()
        
    except KeyboardInterrupt:
        bot.logger.info("Interrupção pelo usuário")
        sys.exit(130)
        
    except Exception as e:
        bot.logger.error(f"Erro fatal: {e}")
        sys.exit(1)
        
    finally:
        bot.cleanup()


if __name__ == "__main__":
    # Configurar asyncio para Windows se necessário
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Executar robô
    asyncio.run(main())
