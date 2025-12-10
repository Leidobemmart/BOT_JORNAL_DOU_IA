# src/scraper.py
from __future__ import annotations

import json
import logging
import re
from typing import Iterable, List, Dict, Any, Optional, Set

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from .publication import Publication
from .utils import build_direct_query_url, absolutize, is_materia_url

logger = logging.getLogger(__name__)

# Textos que indicam "nenhum resultado" (case-insensitive)
NO_RESULTS_TEXTS = [
    "nenhum resultado",
    "não foram encontrados resultados",
    "não foram encontrados registros",
    "0 resultados",
    "nenhum registro encontrado",
    "não encontramos resultados",
    "sua pesquisa não retornou resultados",
]

# Seletores usados no fallback em HTML estático
RESULT_SELECTORS = [
    "a.resultado-item-titulo",
    "div.resultado-item a",
    ".resultado-titulo a",
    "a[href*='/web/dou/-/']",
    "a[href*='/materia/']",
]


class DouScraper:
    """
    Scraper do DOU usando busca direta por URL.

    Fluxo:
      - Monta a URL com build_direct_query_url(...)
      - Abre com Playwright
      - Lê o HTML da página
      - Prioriza o JSON dentro do <script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params">
      - Se falhar / vier vazio, usa fallback baseado em links HTML
    """

    def __init__(
        self,
        phrases: Iterable[str],
        sections: Iterable[str],
        period: str = "today",
        max_pages: int = 5,
        accept_url_patterns: Optional[Iterable[str]] = None,
        reject_url_substrings: Optional[Iterable[str]] = None,
        title_keywords: Optional[Iterable[str]] = None,
    ) -> None:
        self.phrases: List[str] = [p for p in phrases if p]
        self.sections: List[str] = [s for s in sections if s] or ["do1"]
        self.period: str = period or "today"
        self.max_pages: int = max_pages

        # Filtros opcionais (podem vir do config.yml)
        self.accept_url_patterns: List[re.Pattern[str]] = [
            re.compile(p) for p in (accept_url_patterns or [])
        ]
        self.reject_url_substrings: List[str] = list(reject_url_substrings or [])
        # Para comparação case-insensitive
        self.title_keywords: List[str] = [k.upper() for k in (title_keywords or [])]

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
        """Alias amigável para search_all()."""
        return await self.search_all()

    async def search_all(self) -> List[Publication]:
        """
        Executa todas as buscas (todas as frases x seções) e retorna
        uma lista de publicações únicas (deduplicadas por URL).
        """
        if not self.phrases:
            logger.warning("Nenhuma frase de busca configurada; retornando lista vazia.")
            return []

        logger.info("Iniciando busca real no DOU...")

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

        # Deduplicar por URL, preservando ordem
        seen_urls: Set[str] = set()
        unique_pubs: List[Publication] = []
        for pub in all_pubs:
            url = getattr(pub, "url", None)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            unique_pubs.append(pub)

        logger.info("Total de publicações únicas retornadas: %d", len(unique_pubs))
        return unique_pubs

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
        Faz a busca para uma única combinação de frase + seção,
        paginando até max_pages ou até não encontrar mais resultados.
        """
        logger.info("Iniciando busca para frase=%r seção=%s", phrase, section)

        all_pubs: List[Publication] = []

        for page_index in range(1, self.max_pages + 1):
            url = build_direct_query_url(phrase=phrase, period=self.period, section_code=section)
            if page_index > 1:
                url = f"{url}&page={page_index}"

            logger.info(
                "Abrindo URL de busca (página %d/%d): %s",
                page_index,
                self.max_pages,
                url,
            )

            await page.goto(url, wait_until="networkidle")
            page_html = await page.content()

            # Primeira página: checar se não há resultados
            if page_index == 1 and self._has_no_results(page_html):
                logger.info(
                    "Nenhum resultado aparente para frase=%r seção=%s (detecção por texto).",
                    phrase,
                    section,
                )
                break

            pubs = self._collect_page_results(page_html, section)
            logger.info(
                "Encontradas %d publicação(ões) na página %d para frase=%r seção=%s",
                len(pubs),
                page_index,
                phrase,
                section,
            )

            if not pubs:
                logger.info(
                    "Nenhuma publicação na página %d; parando paginação para frase=%r seção=%s",
                    page_index,
                    phrase,
                    section,
                )
                break

            all_pubs.extend(pubs)

        return all_pubs

    # ------------------------------------------------------------------
    # Detecção de "nenhum resultado"
    # ------------------------------------------------------------------
    def _has_no_results(self, html: str) -> bool:
        """
        Verifica se o HTML contém mensagens típicas de "nenhum resultado".
        """
        if not html:
            return True

        lower = html.lower()
        for marker in NO_RESULTS_TEXTS:
            if marker in lower:
                return True
        return False

    # ------------------------------------------------------------------
    # Coleta de resultados da página
    # ------------------------------------------------------------------
    def _collect_page_results(self, html: str, section: Optional[str]) -> List[Publication]:
        """
        Coleta resultados de uma página de busca.

        1) Primeiro tenta extrair do JSON dentro do
           <script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params">
        2) Se falhar ou vier vazio, cai para o fallback baseado em links (<a href="...">)
        """
        pubs_from_json = self._extract_from_json_script(html, section)
        if pubs_from_json:
            logger.debug(
                "Coletados %d resultados via JSON (script params).",
                len(pubs_from_json),
            )
            return pubs_from_json

        logger.debug("Nenhum resultado via JSON; usando fallback BeautifulSoup em links.")
        return self._extract_from_html_links(html, section)

    # ------------------------------------------------------------------
    # 1) Extração via JSON do <script>
    # ------------------------------------------------------------------
    def _extract_from_json_script(self, html: str, section: Optional[str]) -> List[Publication]:
        """
        Extrai resultados a partir do JSON embutido no script de parâmetros
        da busca do DOU.

        O HTML da página de busca contém um <script type="application/json">
        com id "_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params"
        que possui um objeto com a chave "jsonArray", onde cada item representa
        uma publicação do DOU.
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

        hits: List[Dict[str, Any]] = data.get("jsonArray") or []
        if not isinstance(hits, list):
            logger.debug("Campo jsonArray não é uma lista; ignorando.")
            return []

        publications: List[Publication] = []
        seen_urls: Set[str] = set()
        base_url = "https://www.in.gov.br/web/dou/-/"

        logger.debug("JSON de resultados contém %d item(ns).", len(hits))

        for idx, item in enumerate(hits):
            if not isinstance(item, dict):
                continue

            title = (item.get("title") or "").strip()
            url_title = (item.get("urlTitle") or "").strip()

            if not title or not url_title:
                continue

            slug = url_title.lstrip("/")
            url = base_url + slug

            # Filtros de URL
            if not self._url_aceita(url):
                logger.debug("Descartando URL (filtro): %s", url)
                continue

            # Filtro opcional por palavras-chave no título
            if self.title_keywords and not self._titulo_aceito(title):
                logger.debug("Descartando título (filtro title_keywords): %r", title)
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            pub = Publication(
                title=title,
                url=url,
                # se Publication tiver section/organ/etc com default, não precisamos passar tudo
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
        seen_urls: Set[str] = set()

        for selector in RESULT_SELECTORS:
            for a in soup.select(selector):
                href = a.get("href")
                if not href:
                    continue

                url = absolutize(href)
                if not is_materia_url(url):
                    continue

                if not self._url_aceita(url):
                    continue

                title = (a.get_text(strip=True) or "").strip()
                if not title:
                    continue

                if self.title_keywords and not self._titulo_aceito(title):
                    continue

                if url in seen_urls:
                    continue
                seen_urls.add(url)

                pub = Publication(
                    title=title,
                    url=url,
                    # section pode ser preenchida aqui se fizer sentido:
                    # section=section.upper() if section else None,
                )
                publications.append(pub)

        return publications

    # ------------------------------------------------------------------
    # Filtros auxiliares
    # ------------------------------------------------------------------
    def _url_aceita(self, url: str) -> bool:
        """Aplica accept_url_patterns e reject_url_substrings, se configurados."""
        if not url:
            return False

        # Rejeição prioritária
        for bad in self.reject_url_substrings:
            if bad and bad in url:
                return False

        # Se não houver padrões de aceitação, qualquer URL passa aqui
        if not self.accept_url_patterns:
            return True

        return any(p.search(url) for p in self.accept_url_patterns)

    def _titulo_aceito(self, title: str) -> bool:
        """Aplica filtro opcional por palavras-chave no título (case-insensitive)."""
        if not self.title_keywords:
            return True

        upper = (title or "").upper()
        return any(k in upper for k in self.title_keywords)
