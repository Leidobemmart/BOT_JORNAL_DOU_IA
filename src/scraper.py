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
    ) -> None:
        self.phrases = [p for p in phrases if p]
        self.sections = [s for s in sections if s]
        self.period = period or "today"

        if not self.phrases:
            # fallback bem conservador
            self.phrases = ['"tratamento tributário"']

        if not self.sections:
            self.sections = ["do1"]

        logger.info(
            "DouScraper inicializado: %d frase(s), %d seção(ões), período=%s",
            len(self.phrases),
            len(self.sections),
            self.period,
        )

    async def search(self) -> List[Publication]:
        """
        Executa a busca no DOU e retorna uma lista de publicações (apenas cabeçalho).
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

                        # Verificar se a página indica "nenhum resultado"
                        page_html = await page.content()
                        if self._has_no_results(page_html):
                            logger.info(
                                "Nenhum resultado para frase=%r seção=%s",
                                phrase,
                                section,
                            )
                            continue

                        pubs = self._extract_results_from_html(page_html, section)
                        logger.info(
                            "Encontradas %d publicação(ões) na primeira página "
                            "para frase=%r seção=%s",
                            len(pubs),
                            phrase,
                            section,
                        )

                        for pub in pubs:
                            if pub.url not in results_by_url:
                                results_by_url[pub.url] = pub
            finally:
                await browser.close()

        final_list = list(results_by_url.values())
        logger.info("Total de publicações únicas retornadas: %d", len(final_list))
        return final_list

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
