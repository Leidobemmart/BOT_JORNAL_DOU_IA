# src/scraper.py
from __future__ import annotations

import json
import logging
from typing import Iterable, List, Dict, Any, Optional, Set

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from .publication import Publication
from .utils import build_direct_query_url, absolutize, is_materia_url

logger = logging.getLogger(__name__)

# Textos que indicam "nenhum resultado" (case-insensitive, em qualquer parte do HTML)
NO_RESULTS_TEXTS = [
    "nenhum resultado",
    "não foram encontrados",
    "nao foram encontrados",
    "sua pesquisa não retornou resultados",
    "sua pesquisa nao retornou resultados",
    "0 resultados",
    "nenhum registro encontrado",
    "não encontramos resultados",
    "nao encontramos resultados",
]

# Seletores HTML usados no fallback quando o JSON não é encontrado
RESULT_SELECTORS = [
    "a.resultado-item-titulo",
    "a[href*='/web/dou/-/']",
    "a[href*='/materia/']",
    "div.resultado-item a",
    ".resultado-titulo a",
]


class DouScraper:
    """
    Scraper do DOU baseado em:

    1) **Busca direta por URL**:
       - Usa build_direct_query_url(phrase, period, section_code)
       - Ex.: https://www.in.gov.br/consulta/-/buscar/dou?q="DCTF"&s=do1&exactDate=all&sortType=0

    2) **Extração de resultados via JSON embutido**:
       - <script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params" type="application/json">
         {"jsonArray":[ {...}, {...}, ... ]}
       - Cada item tem campos como title, urlTitle, pubName, pubDate etc.

    3) **Fallback em HTML**:
       - Se não achar o JSON ou ele vier vazio, tenta achar links de matéria
         com BeautifulSoup + is_materia_url().

    A lógica de UI (preencher campo, clicar em "Buscar", etc.) fica como
    **plano B** futuro, caso o endpoint direto mude.
    """

    def __init__(
        self,
        phrases: Iterable[str],
        sections: Iterable[str],
        period: str = "today",
        max_pages: int = 5,
    ) -> None:
        self.phrases: List[str] = [p for p in phrases if p]
        self.sections: List[str] = [s for s in sections if s] or ["do1"]
        self.period: str = period or "today"
        self.max_pages: int = max_pages

        logger.info(
            "DouScraper inicializado: %d frase(s), %d seção(ões), período=%s, max_pages=%d",
            len(self.phrases),
            len(self.sections),
            self.period,
            self.max_pages,
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    async def run(self) -> List[Publication]:
        """Alias para search_all()."""
        return await self.search_all()

    async def search_all(self) -> List[Publication]:
        """
        Executa todas as combinações frase x seção, paginando até max_pages.

        Retorna uma lista de Publication deduplicadas por URL.
        """
        if not self.phrases:
            logger.warning("Nenhuma frase de busca configurada; retornando lista vazia.")
            return []

        logger.info("Iniciando busca real no DOU (link direto)...")

        all_pubs: List[Publication] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                for section in self.sections:
                    for phrase in self.phrases:
                        pubs = await self._search_phrase_section(page, phrase, section)
                        all_pubs.extend(pubs)
            finally:
                await context.close()
                await browser.close()

        # Deduplicar por URL (Publication.id já usa a URL, mas garantimos aqui)
        seen_urls: Set[str] = set()
        unique: List[Publication] = []
        for pub in all_pubs:
            url = pub.url
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            unique.append(pub)

        logger.info("Total de publicações únicas retornadas: %d", len(unique))
        return unique

    # ------------------------------------------------------------------
    # Busca por combinação (frase + seção)
    # ------------------------------------------------------------------
    async def _search_phrase_section(
        self,
        page: Page,
        phrase: str,
        section: str,
    ) -> List[Publication]:
        """
        Roda a busca para uma frase em uma seção, com paginação via parâmetro `page`.
        """
        logger.info("Iniciando busca para frase=%r seção=%s", phrase, section)

        results: List[Publication] = []
        seen_urls_page: Set[str] = set()

        for page_index in range(1, self.max_pages + 1):
            base_url = build_direct_query_url(phrase=phrase, period=self.period, section_code=section)
            url = base_url if page_index == 1 else f"{base_url}&page={page_index}"

            logger.info(
                "Abrindo URL de busca (página %d/%d): %s",
                page_index,
                self.max_pages,
                url,
            )

            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
            except Exception as e:
                logger.error("Erro ao carregar página de busca (%s): %s", url, e)
                break

            html = await page.content()

            # Primeira página: se houver mensagem clara de "nenhum resultado", sai.
            if page_index == 1 and self._has_no_results(html):
                logger.info(
                    "Nenhum resultado aparente para frase=%r seção=%s (texto de 'nenhum resultado' encontrado).",
                    phrase,
                    section,
                )
                break

            pubs = self._collect_page_results(html, section)
            logger.info(
                "Encontradas %d publicação(ões) na página %d para frase=%r seção=%s",
                len(pubs),
                page_index,
                phrase,
                section,
            )

            # Deduplicação por página (caso o portal repita itens entre páginas)
            new_pubs: List[Publication] = []
            for pub in pubs:
                if pub.url not in seen_urls_page:
                    seen_urls_page.add(pub.url)
                    new_pubs.append(pub)

            if not new_pubs:
                logger.info(
                    "Nenhuma nova publicação na página %d; parando paginação para frase=%r seção=%s",
                    page_index,
                    phrase,
                    section,
                )
                break

            results.extend(new_pubs)

        return results

    # ------------------------------------------------------------------
    # Detecção de "nenhum resultado"
    # ------------------------------------------------------------------
    def _has_no_results(self, html: str) -> bool:
        """
        Verifica se o HTML contém mensagens de "nenhum resultado".
        """
        if not html:
            return True
        lower = html.lower()
        return any(marker in lower for marker in NO_RESULTS_TEXTS)

    # ------------------------------------------------------------------
    # Coleta de resultados da página (JSON + fallback HTML)
    # ------------------------------------------------------------------
    def _collect_page_results(self, html: str, section: Optional[str]) -> List[Publication]:
        """
        1) Tenta extrair resultados do JSON no <script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params">
        2) Se não der certo ou vier vazio, tenta extrair links direto do HTML.
        """
        pubs_json = self._extract_from_json_script(html, section)
        if pubs_json:
            logger.debug("Coletados %d resultados via JSON embutido.", len(pubs_json))
            return pubs_json

        logger.debug("Nenhum resultado via JSON; usando fallback por links HTML.")
        return self._extract_from_html_links(html, section)

    # ------------------------------------------------------------------
    # 1) Extração via JSON do <script> de parâmetros
    # ------------------------------------------------------------------
    def _extract_from_json_script(self, html: str, section: Optional[str]) -> List[Publication]:
        """
        Extrai resultados a partir do JSON embutido no script de parâmetros
        da busca do DOU.

        O HTML contém algo como:

        <script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params"
                type="application/json">
            {"jsonArray":[{...}, {...}, ...]}
        </script>
        """
        soup = BeautifulSoup(html, "lxml")
        script = soup.find(
            "script",
            id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params",
        )

        if not script or not script.string:
            logger.debug("Script de resultados (params) não encontrado ou vazio.")
            return []

        raw_json = script.string.strip()
        try:
            data = json.loads(raw_json)
        except Exception as e:
            logger.warning("Falha ao fazer json.loads no script de resultados: %s", e)
            return []

        hits = data.get("jsonArray") or []
        if not isinstance(hits, list):
            logger.debug("Campo jsonArray não é uma lista; ignorando.")
            return []

        publications: List[Publication] = []
        seen_urls: Set[str] = set()

        base_url = "https://www.in.gov.br/web/dou/-/"

        for item in hits:
            if not isinstance(item, dict):
                continue

            title = (item.get("title") or "").strip()
            url_title = (item.get("urlTitle") or "").strip()

            if not title or not url_title:
                continue

            # Montar URL absoluta a partir do slug
            if url_title.startswith("http://") or url_title.startswith("https://"):
                url = url_title
            else:
                slug = url_title.lstrip("/")
                url = base_url + slug

            if url in seen_urls:
                continue
            seen_urls.add(url)

            pub = Publication(
                title=title,
                url=url,
                section=(item.get("pubName") or section or "").upper() or None,
            )
            publications.append(pub)

        return publications

    # ------------------------------------------------------------------
    # 2) Fallback: extração via links HTML
    # ------------------------------------------------------------------
    def _extract_from_html_links(self, html: str, section: Optional[str]) -> List[Publication]:
        """
        Fallback para quando o JSON não estiver disponível ou falhar.

        Procura links que pareçam apontar para matérias do DOU usando
        seletores CSS e a função utilitária is_materia_url().
        """
        soup = BeautifulSoup(html, "lxml")
        publications: List[Publication] = []
        seen: Set[str] = set()

        for selector in RESULT_SELECTORS:
            for a in soup.select(selector):
                href = a.get("href")
                if not href:
                    continue

                url = absolutize(href)
                if not is_materia_url(url):
                    continue

                title = (a.get_text(strip=True) or "").strip()
                if not title:
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
