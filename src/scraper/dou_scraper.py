# Lógica de scraping do DOU
"""
Scraper principal para o site DOU.
"""
import asyncio
import logging
from typing import List, Dict, Optional, Set
from tenacity import retry, wait_fixed, stop_after_attempt

from .browser import BrowserManager
from .selectors import (
    RESULT_SELECTORS,
    PAGINATION_SELECTORS,
    NO_RESULTS_TEXTS,
    MENU_TEXTS
)
from utils.url import build_direct_query_url, absolutize, is_dou_materia_url
from utils.text import looks_like_menu
from utils.validators import (
    should_reject_url,
    matches_accept_patterns,
    compile_accept_patterns
)
from models.publication import SearchConfig

logger = logging.getLogger(__name__)


class DOUScraper:
    """Scraper para o Diário Oficial da União."""
    
    def __init__(self, browser: BrowserManager, search_config: SearchConfig):
        """
        Inicializa o scraper DOU.
        
        Args:
            browser: Gerenciador de navegador
            search_config: Configuração de busca
        """
        self.browser = browser
        self.config = search_config
        self.accept_patterns = compile_accept_patterns(
            ["^https://www\\.in\\.gov\\.br/(web/dou/-/|materia/-/)"]
        )
        self.reject_patterns = [
            "consulta/-/buscar/dou",
            "/web/guest/",
            "/leiturajornal",
            "javascript:",
            "#",
            "acesso-",
            "govbr"
        ]
    
    async def search(self) -> List[Dict]:
        """
        Executa a busca no DOU com base na configuração.
        
        Returns:
            Lista de publicações brutas (com url e título)
        """
        logger.info(
            f"Iniciando busca: {len(self.config.phrases)} frases, "
            f"{len(self.config.sections)} seções"
        )
        
        all_results: Set[tuple] = set()  # (url, titulo)
        
        for phrase in self.config.phrases:
            for section in self.config.sections:
                try:
                    section_results = await self._search_phrase_section(
                        phrase, section
                    )
                    
                    for result in section_results:
                        all_results.add((result['url'], result.get('titulo', '')))
                    
                    logger.info(
                        f"Frase '{phrase[:30]}...' - Seção {section}: "
                        f"{len(section_results)} resultados"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Erro na busca (frase: {phrase}, seção: {section}): {e}"
                    )
                    continue
        
        # Converter para lista de dicionários
        results = [
            {'url': url, 'titulo': titulo}
            for url, titulo in all_results
        ]
        
        logger.info(f"Busca concluída: {len(results)} resultados únicos")
        return results
    
    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def _search_phrase_section(
        self,
        phrase: str,
        section: str
    ) -> List[Dict]:
        """
        Busca por uma frase específica em uma seção específica.
        
        Args:
            phrase: Frase de busca
            section: Seção (do1, do2, do3, todos)
        
        Returns:
            Lista de resultados
        """
        # Construir URL de busca
        url = build_direct_query_url(phrase, self.config.period, section)
        logger.debug(f"URL de busca: {url}")
        
        # Navegar para a página de resultados
        await self.browser.goto(url, wait_until="networkidle")
        
        # Aguardar resultados
        await self._wait_for_results()
        
        # Verificar se há resultados
        if await self._has_no_results():
            logger.debug(f"Nenhum resultado para: {phrase}")
            return []
        
        # Coletar resultados paginados
        results = await self._collect_paginated_results()
        
        # Filtrar resultados
        filtered_results = self._filter_results(results)
        
        return filtered_results
    
    async def _wait_for_results(self, timeout_ms: int = 20000):
        """
        Aguarda até que a página de resultados carregue.
        
        Args:
            timeout_ms: Timeout em milissegundos
        """
        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000)
        
        while asyncio.get_event_loop().time() < deadline:
            # Verificar mensagem de "nenhum resultado"
            page_text = await self.browser.page.content()
            if any(text in page_text for text in NO_RESULTS_TEXTS):
                return
            
            # Verificar se há links de resultados
            for selector in RESULT_SELECTORS:
                if await self.browser.wait_for_selector(selector, timeout=1000):
                    return
            
            await asyncio.sleep(0.5)
        
        logger.debug("Timeout aguardando resultados")
    
    async def _has_no_results(self) -> bool:
        """Verifica se a página indica que não há resultados."""
        page_text = await self.browser.page.content()
        return any(text in page_text for text in NO_RESULTS_TEXTS)
    
    async def _collect_paginated_results(self) -> List[Dict]:
        """
        Coleta resultados de todas as páginas.
        
        Returns:
            Lista de resultados brutos
        """
        all_results = []
        seen_urls = set()
        page_num = 0
        
        while page_num < self.config.max_pages:
            # Coletar resultados da página atual
            page_results = await self._collect_page_results()
            
            # Adicionar novos resultados
            new_count = 0
            for result in page_results:
                if result['url'] not in seen_urls:
                    seen_urls.add(result['url'])
                    all_results.append(result)
                    new_count += 1
            
            logger.debug(
                f"Página {page_num + 1}: {len(page_results)} resultados, "
                f"{new_count} novos"
            )
            
            # Verificar se podemos ir para próxima página
            if not await self._go_to_next_page():
                break
            
            page_num += 1
            await asyncio.sleep(1)  # Pequena pausa entre páginas
        
        return all_results
    
    async def _collect_page_results(self) -> List[Dict]:
        """
        Coleta resultados da página atual.
        
        Returns:
            Lista de resultados
        """
        results = []
        
        # Coletar usando seletores CSS
        for selector in RESULT_SELECTORS:
            try:
                elements = await self.browser.page.query_selector_all(selector)
                
                for element in elements:
                    try:
                        href = await element.get_attribute('href')
                        text = await element.text_content()
                        
                        if href and text:
                            results.append({
                                'url': absolutize(href),
                                'titulo': text.strip(),
                                'selector': selector
                            })
                    except Exception as e:
                        logger.debug(f"Erro ao extrair elemento: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Erro com seletor {selector}: {e}")
                continue
        
        # Fallback: coletar todos os links via JavaScript
        if not results:
            logger.debug("Usando fallback JavaScript para coletar links")
            js_links = await self._collect_links_via_js()
            results.extend(js_links)
        
        return results
    
    async def _collect_links_via_js(self) -> List[Dict]:
        """
        Coleta links via JavaScript (fallback).
        
        Returns:
            Lista de links
        """
        js_code = """
        () => {
            const links = [];
            const anchors = document.querySelectorAll('a[href]');
            
            for (const a of anchors) {
                // Filtrar links que parecem ser de resultados
                const href = a.href;
                const text = a.textContent.trim();
                
                if (!href || !text) continue;
                
                // Ignorar links óbvios de menu/navegação
                const lowerText = text.toLowerCase();
                const menuKeywords = [
                    'última hora', 'voltar ao topo', 'pesquisa', 
                    'portal', 'tutorial', 'reportar erro',
                    'diário oficial', 'compartilhe', 'acesse'
                ];
                
                const isMenu = menuKeywords.some(keyword => 
                    lowerText.includes(keyword)
                );
                
                if (isMenu) continue;
                
                // Ignorar links muito curtos
                if (text.length < 10) continue;
                
                // Priorizar links que parecem ser de matérias
                const isMateria = href.includes('/web/dou/-/') || 
                                 href.includes('/materia/');
                
                if (isMateria || text.length > 20) {
                    links.push({
                        url: href,
                        titulo: text,
                        source: 'js_fallback'
                    });
                }
            }
            
            return links;
        }
        """
        
        try:
            links = await self.browser.evaluate(js_code)
            return links or []
        except Exception as e:
            logger.error(f"Erro no fallback JS: {e}")
            return []
    
    async def _go_to_next_page(self) -> bool:
        """
        Tenta ir para a próxima página de resultados.
        
        Returns:
            True se conseguiu avançar
        """
        for selector in PAGINATION_SELECTORS:
            try:
                element = await self.browser.page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    await asyncio.sleep(2)  # Aguardar carregamento
                    return True
            except Exception as e:
                logger.debug(f"Erro ao tentar próximo com {selector}: {e}")
                continue
        
        # Fallback: scroll infinito
        logger.debug("Tentando scroll infinito como fallback")
        await self.browser.page.evaluate(
            "window.scrollTo(0, document.body.scrollHeight)"
        )
        await asyncio.sleep(2)
        
        # Verificar se novos itens apareceram
        new_results = await self._collect_page_results()
        return len(new_results) > 0
    
    def _filter_results(self, results: List[Dict]) -> List[Dict]:
        """
        Filtra resultados indesejados.
        
        Args:
            results: Resultados brutos
        
        Returns:
            Resultados filtrados
        """
        filtered = []
        
        for result in results:
            url = result['url']
            titulo = result.get('titulo', '')
            
            # Pular se URL vazia
            if not url:
                continue
            
            # Verificar se é URL de matéria DOU
            if not is_dou_materia_url(url):
                continue
            
            # Verificar rejeição por padrões
            if should_reject_url(url, self.reject_patterns):
                continue
            
            # Verificar aceitação por padrões
            if not matches_accept_patterns(url, self.accept_patterns):
                continue
            
            # Verificar se título parece menu
            if looks_like_menu(titulo):
                continue
            
            # Verificar palavras-chave no título (se configurado)
            # Esta verificação será feita posteriormente com a configuração
            
            filtered.append(result)
        
        logger.debug(f"Filtrados: {len(results)} -> {len(filtered)} resultados")
        return filtered
    
    async def get_page_content(self, url: str) -> str:
        """
        Obtém o conteúdo HTML de uma página.
        
        Args:
            url: URL da página
        
        Returns:
            Conteúdo HTML
        """
        try:
            # Usar página existente ou criar nova
            if self.browser.page and not self.browser.page.is_closed():
                page = self.browser.page
            else:
                page = await self.browser.new_page()
            
            # Navegar para a URL
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000
            )
            
            # Aguardar conteúdo carregar
            await asyncio.sleep(1)
            
            # Obter conteúdo HTML
            content = await page.content()
            
            return content
            
        except Exception as e:
            logger.error(f"Erro ao obter conteúdo de {url}: {e}")
            return ""
    
    async def test_connection(self) -> bool:
        """Testa a conexão com o site DOU."""
        try:
            await self.browser.goto(
                "https://www.in.gov.br",
                wait_until="domcontentloaded",
                timeout=10000
            )
            
            # Verificar se carregou
            title = await self.browser.page.title()
            logger.debug(f"Teste de conexão: Título = {title}")
            
            return "Imprensa Nacional" in title or "DOU" in title
            
        except Exception as e:
            logger.error(f"Teste de conexão falhou: {e}")
            return False
