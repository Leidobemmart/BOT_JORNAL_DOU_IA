#!/usr/bin/env python3
"""
Robô de monitoramento do Diário Oficial da União (DOU) - Versão 2.0

Pipeline principal:
1. Carregar configuração
2. Inicializar componentes
3. Executar busca no DOU
4. Processar resultados
5. Gerar resumos com IA
6. Enviar email
7. Atualizar estado

Uso:
    python src/main.py
    FORCE_TEST_EMAIL=true python src/main.py  # Para email de teste
"""

import asyncio
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Configurar path para importação dos módulos
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Importações dos módulos
from core.logger import setup_logging
from core.config import Config
from core.state import StateManager
from scraper.browser import BrowserManager
from scraper.dou_scraper import DOUScraper
from scraper.extractor import ContentExtractor
from ai.summarizer import Summarizer
from email_module.builder import EmailBuilder
from email.sender import EmailSender, SMTPConfig
from models.publication import Publication


class DOUBot:
    """Classe principal do robô DOU."""
    
    def __init__(self):
        self.logger = None
        self.config = None
        self.state = None
        self.browser = None
        self.scraper = None
        self.extractor = None
        self.summarizer = None
        self.email_builder = None
        self.email_sender = None
        self.start_time = None
        
    def initialize(self) -> bool:
        """
        Inicializa todos os componentes do robô.
        
        Returns:
            True se inicializado com sucesso
        """
        self.start_time = datetime.now()
        
        try:
            # Configurar logging
            log_level = os.getenv('LOG_LEVEL', 'INFO')
            self.logger = setup_logging(level=log_level)
            self.logger.info("=" * 60)
            self.logger.info("INICIANDO ROBÔ DOU - Versão 2.0")
            self.logger.info(f"Hora de início: {self.start_time.strftime('%d/%m/%Y %H:%M:%S')}")
            self.logger.info("=" * 60)
            
            # Carregar configuração
            self.logger.info("📄 Carregando configuração...")
            self.config = Config()
            self.config.load()
            self.config.validate()
            self.logger.info("✅ Configuração carregada")
            
            # Inicializar gerenciador de estado
            self.logger.info("💾 Inicializando gerenciador de estado...")
            self.state = StateManager()
            self.state.load()
            self.logger.info(f"   Itens no estado: {self.state.count}")
            
            # Inicializar extrator de conteúdo
            self.extractor = ContentExtractor()
            
            # Inicializar sumarizador IA (se habilitado)
            if self.config.ai.enabled:
                self.logger.info("🤖 Inicializando sumarizador IA...")
                self.summarizer = Summarizer(self.config.ai)
                self.logger.info(f"   Provedor: {self.summarizer.provider.__class__.__name__}")
            else:
                self.logger.info("🤖 IA desabilitada na configuração")
            
            # Inicializar construtor de email
            self.logger.info("📧 Inicializando construtor de email...")
            self.email_builder = EmailBuilder(self.config.email)
            
            # Validar configuração de email
            if not self.email_builder.validate_configuration():
                self.logger.error("Configuração de email inválida")
                return False
            
            recipient_summary = self.email_builder.get_recipient_summary()
            self.logger.info(f"   {recipient_summary}")
            
            # Inicializar enviador de email
            self.logger.info("📤 Inicializando enviador de email...")
            smtp_config_dict = self.config.get_smtp_config()
            smtp_config = SMTPConfig(**smtp_config_dict)
            self.email_sender = EmailSender(smtp_config)
            
            self.logger.info("✅ Inicialização concluída com sucesso")
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Erro na inicialização: {e}", exc_info=True)
            else:
                print(f"ERRO: {e}")
            return False
    
    async def run(self):
        """Executa o pipeline principal do robô."""
        try:
            # Verificar se deve forçar email de teste
            force_test = os.getenv('FORCE_TEST_EMAIL', '').lower() in ['1', 'true', 'yes']
            
            if force_test:
                self.logger.info("🚨 FORCE_TEST_EMAIL ativado - Enviando email de teste")
                success = await self.email_builder.send_test_email(self.email_sender)
                if success:
                    self.logger.info("✅ Email de teste enviado com sucesso")
                else:
                    self.logger.error("❌ Falha ao enviar email de teste")
                return
            
            # Inicializar navegador
            self.logger.info("🌐 Iniciando navegador...")
            self.browser = BrowserManager(headless=True)
            await self.browser.start()
            
            # Inicializar scraper
            self.scraper = DOUScraper(self.browser, self.config.search)
            
            # Executar busca no DOU
            self.logger.info("🔍 Executando busca no DOU...")
            search_stats = await self._execute_search()
            
            if search_stats['total_found'] == 0:
                self.logger.info("📭 Nenhuma publicação encontrada")
                await self._handle_no_results()
                return
            
            self.logger.info(f"📊 Resultados: {search_stats}")
            
            # Processar publicações
            self.logger.info("🔄 Processando publicações...")
            publications = await self._process_publications(search_stats['raw_publications'])
            
            if not publications:
                self.logger.info("📭 Nenhuma publicação válida após processamento")
                return
            
            # Gerar resumos com IA
            if self.summarizer and self.config.ai.enabled:
                self.logger.info("🤖 Gerando resumos com IA...")
                publications = await self._generate_ai_summaries(publications)
            
            # Ordenar publicações por data
            publications.sort(key=lambda x: x.data or "", reverse=True)
            
            # Construir e enviar email
            self.logger.info("📧 Preparando email...")
            await self._send_email(publications)
            
            # Atualizar estado
            self.logger.info("💾 Atualizando estado...")
            self.state.add_batch(publications)
            self.state.save()
            
            self.logger.info(f"✅ Pipeline concluído: {len(publications)} publicação(ões) enviada(s)")
            
        except Exception as e:
            self.logger.error(f"❌ Erro durante execução: {e}", exc_info=True)
            raise
            
        finally:
            # Garantir que o navegador seja fechado
            if self.browser:
                await self.browser.close()
                self.logger.info("🌐 Navegador fechado")
    
    async def _execute_search(self) -> dict:
        """
        Executa a busca no DOU e retorna estatísticas.
        
        Returns:
            Dicionário com estatísticas da busca
        """
        raw_publications = await self.scraper.search()
        
        return {
            'total_found': len(raw_publications),
            'raw_publications': raw_publications,
            'search_config': {
                'phrases': len(self.config.search.phrases),
                'sections': len(self.config.search.sections),
                'period': self.config.search.period
            }
        }
    
    async def _process_publications(self, raw_publications: list) -> list[Publication]:
        """
        Processa publicações brutas em objetos Publication.
        
        Args:
            raw_publications: Lista de publicações brutas
        
        Returns:
            Lista de objetos Publication processados
        """
        publications = []
        
        for i, raw_pub in enumerate(raw_publications, 1):
            try:
                self.logger.debug(f"Processando publicação {i}/{len(raw_publications)}: {raw_pub.get('url', '')[:80]}...")
                
                # Obter conteúdo HTML
                html_content = await self.scraper.get_page_content(raw_pub['url'])
                
                if not html_content:
                    self.logger.warning(f"Conteúdo vazio para: {raw_pub['url']}")
                    continue
                
                # Extrair conteúdo limpo e metadados
                result = self.extractor.extract(html_content, raw_pub['url'])
                
                # Criar objeto Publication
                pub = Publication(
                    url=raw_pub['url'],
                    titulo=result.get('titulo') or raw_pub.get('titulo', 'Sem título'),
                    orgao=result.get('orgao'),
                    tipo=result.get('tipo'),
                    numero=result.get('numero'),
                    data=result.get('data'),
                    secao=result.get('secao'),
                    pagina=result.get('pagina'),
                    texto_bruto=result.get('texto_bruto'),
                    texto_limpo=result.get('texto_limpo'),
                    resumo_ia=None
                )
                
                # Verificar se é válido e não foi visto
                if pub.is_valid and not self.state.contains(pub):
                    # Aplicar filtros adicionais
                    if self._passes_filters(pub):
                        publications.append(pub)
                    else:
                        self.logger.debug(f"Publicação filtrada: {pub.titulo[:50]}...")
                else:
                    self.logger.debug(f"Publicação ignorada (inválida ou já vista): {pub.titulo[:50]}...")
                
                # Pequena pausa para não sobrecarregar o servidor
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Erro ao processar publicação: {e}")
                continue
        
        return publications
    
    def _passes_filters(self, pub: Publication) -> bool:
        """
        Aplica filtros configurados à publicação.
        
        Args:
            pub: Publicação a filtrar
        
        Returns:
            True se passa nos filtros
        """
        filters_cfg = self.config.filters
        
        # Verificar palavras-chave no título
        if not self._passes_title_filter(pub.titulo, filters_cfg.get('title_keywords')):
            return False
        
        # Verificar palavras-chave no órgão
        if not self._passes_orgao_filter(pub.orgao, filters_cfg.get('orgao_keywords')):
            return False
        
        # Verificar filtro de data (edição do dia)
        if self.config.search.period in ['today', 'dia'] and pub.data:
            today = datetime.now().strftime("%d/%m/%Y")
            if pub.data != today:
                self.logger.debug(f"Filtro de data: {pub.data} != {today}")
                return False
        
        return True
    
    def _passes_title_filter(self, title: str, keywords: list) -> bool:
        """Verifica se o título passa no filtro."""
        from utils.validators import title_contains_keywords
        return title_contains_keywords(title, keywords)
    
    def _passes_orgao_filter(self, orgao: str, keywords: list) -> bool:
        """Verifica se o órgão passa no filtro."""
        from utils.validators import orgao_contains_keywords
        return orgao_contains_keywords(orgao, keywords)
    
    async def _generate_ai_summaries(self, publications: list[Publication]) -> list[Publication]:
        """
        Gera resumos com IA para as publicações.
        
        Args:
            publications: Lista de publicações
        
        Returns:
            Lista de publicações com resumos
        """
        for pub in publications:
            try:
                if pub.texto_limpo and not pub.resumo_ia:
                    self.logger.debug(f"Gerando resumo IA para: {pub.titulo[:50]}...")
                    
                    metadata = {
                        'tipo': pub.tipo,
                        'numero': pub.numero,
                        'orgao': pub.orgao,
                        'data': pub.data
                    }
                    
                    summary = await self.summarizer.summarize(pub.texto_limpo, metadata)
                    
                    if summary:
                        pub.resumo_ia = summary
                        self.logger.debug(f"Resumo gerado: {len(summary)} caracteres")
                    
                    # Pausa para respeitar rate limits da API
                    await asyncio.sleep(1)
                    
            except Exception as e:
                self.logger.warning(f"Erro ao gerar resumo IA: {e}")
                continue
        
        return publications
    
    async def _send_email(self, publications: list[Publication]):
        """
        Envia email com as publicações.
        
        Args:
            publications: Lista de publicações para incluir no email
        """
        # Construir conteúdo do email
        email_data = self.email_builder.build(
            publications=publications,
            search_config={
                'phrases': self.config.search.phrases,
                'sections': self.config.search.sections,
                'period': self.config.search.period,
                'days_window': self.config.search.days_window
            },
            include_ai_summaries=self.config.ai.enabled
        )
        
        # Enviar email
        success = await self.email_sender.send(**email_data)
        
        if success:
            self.logger.info(f"✅ Email enviado para {len(email_data['recipients'].to)} destinatário(s)")
        else:
            self.logger.error("❌ Falha ao enviar email")
    
    async def _handle_no_results(self):
        """Lida com cenário de nenhum resultado encontrado."""
        # Opcional: enviar email informando que não há resultados
        # Isso pode ser configurado no futuro
        self.logger.info("Nenhuma publicação nova encontrada")
    
    def cleanup(self):
        """Limpeza de recursos e logging final."""
        if self.start_time:
            duration = datetime.now() - self.start_time
            self.logger.info(f"⏱️  Duração total: {duration}")
        
        self.logger.info("=" * 60)
        self.logger.info("ROBÔ DOU FINALIZADO")
        self.logger.info("=" * 60)


async def main():
    """Função principal assíncrona."""
    bot = DOUBot()
    
    try:
        # Inicializar
        if not bot.initialize():
            return 1
        
        # Executar pipeline
        await bot.run()
        
        return 0
        
    except KeyboardInterrupt:
        if bot.logger:
            bot.logger.info("⏹️  Interrupção pelo usuário")
        else:
            print("\n⏹️  Interrupção pelo usuário")
        return 130
        
    except Exception as e:
        if bot.logger:
            bot.logger.error(f"💥 Erro fatal: {e}", exc_info=True)
        else:
            print(f"💥 ERRO FATAL: {e}")
        return 1
        
    finally:
        bot.cleanup()


if __name__ == "__main__":
    # Configurar asyncio para Windows se necessário
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Executar robô
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
