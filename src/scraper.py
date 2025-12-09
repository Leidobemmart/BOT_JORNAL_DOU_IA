# src/scraper.py
from __future__ import annotations

import logging
from typing import Iterable, List, Dict

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .publication import Publication
from .utils import build_direct_query_url, absolutize, is_materia_url

logger = logging.getLogger(__name__)


# Seletores CSS para resultados de busca (simplificados)
RESULT_SELECTORS = [
    "a.resultado-item-titulo",
    "a[href*='/web/dou/-/']",
    "a[href*='/materia/']",
    "div.resultado-item a",
    ".resultado-titulo a",
]

# Textos que indicam "nenhum resultado"
NO_RESULTS_TEXTS = [
    "Nenhum resultado",
    "Não foram encontrados",
    "0 resultados",
    "nenhum registro",
    "Não encontramos",
]


class DouScraper:
    """
    Scraper simplificado do DOU.

    - Usa Playwright para abrir a página de resultados
    - Usa BeautifulSoup para extrair links de matérias
    - Por enquanto, pega apenas a PRIMEIRA PÁGINA de resultados
    """

    def __init__(
        self,
        phrases: Iterable[str],
        sections: Iterable[str],
        period: str = "today",
        max_pages: int = 1,
    ) -> None:
        self.phrases = [p for p in phrases if p]
        self.sections = [s for s in sections if s]
        self.period = period or "today"

        try:
            self.max_pages = int(max_pages)
        except (TypeError, ValueError):
            self.max_pages = 1

        if self.max_pages < 1:
            self.max_pages = 1

        logger.info(
            "DouScraper inicializado: %d frase(s), %d seção(ões), período=%s, max_pages=%d",
            len(self.phrases),
            len(self.sections),
            self.period,
            self.max_pages,
        )

    async def search(self) -> List[Publication]:
        """
        Executa a busca no DOU e retorna uma lista de publicações (apenas cabeçalho).
        Percorre até max_pages páginas por combinação frase+seção.
        """
        results_by_url: Dict[str, Publication] = {}

        logger.info("Iniciando busca real no DOU...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                for phrase in self.phrases:
                    for section in self.sections:
                        search_url = build_direct_query_url(
                            phrase=phrase,
                            period=self.period,
                            section_code=section,
                        )
                        logger.info(
                            "Buscando no DOU | frase=%r | seção=%s | url=%s",
                            phrase,
                            section,
                            search_url,
                        )

                        await page.goto(search_url, wait_until="networkidle")

                        page_index = 1
                        while page_index <= self.max_pages:
                            logger.info(
                                "Processando página %d/%d para frase=%r seção=%s",
                                page_index,
                                self.max_pages,
                                phrase,
                                section,
                            )

                            page_html = await page.content()

                            # Na primeira página, checar se não há resultados
                            if page_index == 1 and self._has_no_results(page_html):
                                logger.info(
                                    "Nenhum resultado para frase=%r seção=%s",
                                    phrase,
                                    section,
                                )
                                break

                            pubs = self._extract_results_from_html(page_html, section)
                            logger.info(
                                "Encontradas %d publicação(ões) na página %d para frase=%r seção=%s",
                                len(pubs),
                                page_index,
                                phrase,
                                section,
                            )

                            for pub in pubs:
                                if pub.url not in results_by_url:
                                    results_by_url[pub.url] = pub

                            # Se já atingimos o limite de páginas, parar aqui
                            if page_index >= self.max_pages:
                                break

                            # Tentar ir para a próxima página
                            has_next = await self._go_to_next_page(page)
                            if not has_next:
                                logger.info(
                                    "Sem próxima página (parando em %d) para frase=%r seção=%s",
                                    page_index,
                                    phrase,
                                    section,
                                )
                                break

                            page_index += 1

            finally:
                await browser.close()

        final_list = list(results_by_url.values())
        logger.info("Total de publicações únicas retornadas: %d", len(final_list))
        return final_list

    async def _go_to_next_page(self, page) -> bool:
        """
        Tenta navegar para a próxima página de resultados.

        Retorna:
            True  -> conseguiu ir para a próxima página
            False -> não encontrou botão/link de próxima página
        """
        # Tentativas de seletor para botão de "Próxima página".
        # Isso pode precisar de ajuste conforme o HTML real do DOU.
        candidate_selectors = [
            'a[aria-label*="Próxima"]',
            'a[aria-label*="Próximo"]',
            'a[rel="next"]',
            'a.page-link[rel="next"]',
            'text=Próxima',
            'text=Próximo',
        ]

        for sel in candidate_selectors:
            try:
                btn = await page.query_selector(sel)
            except Exception:
                btn = None

            if btn:
                try:
                    await btn.click()
                    # Dar um tempo pra página carregar
                    await page.wait_for_load_state("networkidle")
                    logger.info("Avançou para a próxima página usando seletor: %s", sel)
                    return True
                except Exception as e:
                    logger.warning(
                        "Falha ao clicar em próxima página com seletor %s: %s",
                        sel,
                        e,
                    )
                    # tenta o próximo seletor

        return False

    
    # -----------------------
    #   Helpers internos
    # -----------------------

    def _has_no_results(self, html: str) -> bool:
        """Verifica se a página indica que não há resultados."""
        if not html:
            return True
        lower = html.lower()
        return any(text.lower() in lower for text in NO_RESULTS_TEXTS)

    def _extract_results_from_html(
        self,
        html: str,
        section: str | None = None,
    ) -> List[Publication]:
        """
        Extrai lista de publicações a partir do HTML da página de resultados.
        """
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        publications: List[Publication] = []

        for selector in RESULT_SELECTORS:
            for link in soup.select(selector):
                href = (link.get("href") or "").strip()
                title = (link.get_text(strip=True) or "").strip()

                if not href or not title:
                    continue

                url = absolutize(href)
                if not is_materia_url(url):
                    # ignora links genéricos de navegação
                    continue

                if url in seen:
                    continue

                seen.add(url)

                pub = Publication(
                    title=title,
                    url=url,
                    section=section.upper() if section else None,
                )
                publications.append(pub)

        return publications
