# src/scraper.py
from __future__ import annotations

import logging
from typing import Iterable, List, Dict, Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from .publication import Publication
from .utils import build_direct_query_url, absolutize, is_materia_url

logger = logging.getLogger(__name__)


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
    Scraper do DOU usando Playwright.

    - Abre a página de busca para cada combinação frase + seção
    - Lê os resultados a partir do JSON em
      <script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params">
    - Percorre até max_pages páginas (tentando clicar em "Próxima")
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

        if not self.phrases:
            self.phrases = ['"tratamento tributário"']
        if not self.sections:
            self.sections = ["do1"]

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

                            # Primeira página: checar se não há resultados
                            if page_index == 1 and self._has_no_results(page_html):
                                logger.info(
                                    "Nenhum resultado para frase=%r seção=%s",
                                    phrase,
                                    section,
                                )
                                break

                            pubs = await self._collect_page_results(page, page_html, section)
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

                            # Se não achou nada nesta página, não faz sentido tentar avançar mais
                            if not pubs:
                                logger.info(
                                    "Nenhuma publicação na página %d; parando paginação "
                                    "para frase=%r seção=%s",
                                    page_index,
                                    phrase,
                                    section,
                                )
                                break

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

    async def _go_to_next_page(self, page: Page) -> bool:
        """
        Tenta navegar para a próxima página de resultados.

        Retorna:
            True  -> conseguiu ir para a próxima página
            False -> não encontrou botão/link de próxima página
        """
        # Tentativas de seletor para botão de "Próxima página".
        candidate_selectors = [
            'a[aria-label*="Próxima"]',
            'a[aria-label*="Próximo"]',
            'a[rel="next"]',
            'a.page-link[rel="next"]',
            'button[aria-label*="Próxima"]',
            'button[aria-label*="Próximo"]',
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

    async def _collect_page_results(
        self,
        page: Page,
        html: str,
        section: str | None = None,
    ) -> List[Publication]:
        """
        Coleta os resultados da página atual.

        1) Tenta ler o JSON em
           <script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params">
           e usar a propriedade jsonArray.
        2) Se falhar, faz um fallback usando BeautifulSoup e links na página.
        """
        publications: List[Publication] = []

        # 1) Tentar via JSON (forma atual do site)
        js_code = """
        () => {
            const elem = document.getElementById("_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params");
            if (!elem) {
                return null;
            }
            try {
                const text = elem.textContent || elem.innerHTML;
                const data = JSON.parse(text);
                if (!data || !Array.isArray(data.jsonArray)) {
                    return null;
                }
                const base = "https://www.in.gov.br/web/dou/-/";
                const hits = data.jsonArray;

                return hits.map(hit => {
                    const orgao = hit.hierarchyStr
                        || (Array.isArray(hit.hierarchyList)
                            ? hit.hierarchyList.join(" / ")
                            : null);

                    return {
                        url: base + hit.urlTitle,
                        titulo: hit.title || "",
                        snippet: hit.content || "",
                        data: hit.pubDate || "",
                        secao: hit.pubName || "",
                        pagina: hit.numberPage || "",
                        orgao: orgao || "",
                        art_type: hit.artType || "",
                        edition: hit.editionNumber || ""
                    };
                });
            } catch (e) {
                return null;
            }
        }
        """

        hits: List[Dict[str, Any]] | None = None
        try:
            hits = await page.evaluate(js_code)
        except Exception as e:
            logger.warning("Erro ao avaliar JSON de resultados: %s", e)

        if hits:
            logger.debug("Coletados %d resultados via JSON (jsonArray).", len(hits))
            seen_urls = set()
            for hit in hits:
                url = (hit.get("url") or "").strip()
                titulo = (hit.get("titulo") or "").strip()
                if not url or not titulo:
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                pub = Publication(
                    title=titulo,
                    url=url,
                    section=(hit.get("secao") or section or "").upper() or None,
                    organ=hit.get("orgao") or None,
                    # Podemos evoluir depois para parsear a data se for útil
                )
                publications.append(pub)

            if publications:
                return publications

        # 2) Fallback antigo: varrer todos os links da página
        logger.debug(
            "Nenhum resultado via JSON; usando fallback BeautifulSoup em links."
        )
        publications.extend(self._extract_results_from_html(html, section))
        return publications

    def _extract_results_from_html(
        self,
        html: str,
        section: str | None = None,
    ) -> List[Publication]:
        """
        Fallback: extrai lista de publicações a partir do HTML da página de resultados,
        procurando por links de matérias.
        """
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        publications: List[Publication] = []

        # Na estrutura atual do site é pouco provável que isso encontre algo,
        # mas mantemos como plano B.
        for link in soup.find_all("a", href=True):
            href = (link.get("href") or "").strip()
            title = (link.get_text(strip=True) or "").strip()

            if not href or not title:
                continue

            url = absolutize(href)
            if not is_materia_url(url):
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
