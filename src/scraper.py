# src/scraper.py
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Iterable, List, Dict, Any, Optional, Set

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page
from unidecode import unidecode

from .publication import Publication
from .utils import build_direct_query_url, absolutize

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Helpers de normalização / filtros
# -------------------------------------------------------------------
def _normalize(text: str) -> str:
    t = unidecode((text or "")).lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _looks_like_menu(text: str) -> bool:
    """Heurística para descartar links de navegação/menus."""
    BAD_ANCHORS = [
        "última hora",
        "ultimas 24 horas",
        "últimas 24 horas",
        "semana passada",
        "mês passado",
        "mes passado",
        "ano passado",
        "período personalizado",
        "periodo personalizado",
        "pesquisa avançada",
        "pesquisa",
        "verificação de autenticidade",
        "voltar ao topo",
        "portal",
        "tutorial",
        "termo de uso",
        "mapa do site",
        "imprensa nacional",
        "governo federal",
        "navegação",
        "institucional",
        "contato",
        "fale conosco",
        "ir para o conteúdo",
        "ir para o rodapé",
        "acessibilidade",
        "acesso gov.br",
    ]
    t = _normalize(text)
    return any(b in t for b in BAD_ANCHORS)


async def _deep_collect_anchors(page: Page) -> List[Dict[str, str]]:
    """
    Varre DOM + Shadow DOM coletando todos os anchors com href.
    """
    anchors = await page.evaluate(
        """
() => {
  function collectFrom(root) {
    const out = [];
    const stack = [root];
    while (stack.length) {
      const node = stack.pop();
      if (!node) continue;
      if (node.querySelectorAll) {
        node.querySelectorAll('a[href]').forEach(a => {
          const href = a.getAttribute('href') || '';
          const text = (a.innerText || a.textContent || '').trim();
          out.push([href, text]);
        });
        node.querySelectorAll('*').forEach(el => {
          if (el.shadowRoot) stack.push(el.shadowRoot);
        });
      }
      if (node.host && node.host.shadowRoot && node !== node.host.shadowRoot) {
        stack.push(node.host.shadowRoot);
      }
    }
    return out;
  }
  return collectFrom(document);
}
"""
    )
    out: List[Dict[str, str]] = []
    for href, text in anchors:
        out.append({"href": href, "text": text})
    return out


async def _wait_results(page: Page, timeout_ms: int = 20000) -> None:
    """
    Espera até que apareçam resultados ou mensagem de "nenhum resultado".
    """
    try:
        await page.wait_for_function(
            """
() => {
  const hasList =
    document.querySelector('a.resultado-item-titulo') ||
    document.querySelector('a[href*="/web/dou/-/"]') ||
    document.querySelector('a[href*="/materia/-/"]');
  const pageText = document.body ? document.body.innerText : '';
  const noRes = /Nenhum resultado|N[ãa]o encontramos resultados/i.test(pageText);
  return Boolean(hasList) || noRes;
}
""",
            timeout=timeout_ms,
        )
    except Exception:
        # Timeout não é fatal; seguimos com o que houver na página
        return


async def _collect_links_from_listing(page: Page) -> List[Dict[str, str]]:
    """
    Coleta links da listagem de resultados que pareçam ser matérias do DOU.
    """
    links: Dict[str, str] = {}
    discards = {"menu": 0}

    async def consider(href: Optional[str], text: Optional[str]) -> None:
        nonlocal links, discards
        if not href:
            return
        href = absolutize(href)
        text = (text or "").strip()

        # só interessa URLs de matéria
        if "/web/dou/-/" not in href and "/materia/-/" not in href:
            return

        if _looks_like_menu(text):
            discards["menu"] += 1
            return

        links[href] = text or "(sem título)"

    # 1) Títulos principais da listagem
    try:
        loc = page.locator("a.resultado-item-titulo")
        count = await loc.count()
        for i in range(min(count, 800)):
            try:
                a = loc.nth(i)
                await consider(await a.get_attribute("href"), await a.inner_text())
            except Exception:
                continue
    except Exception:
        pass

    # 2) Fallback: qualquer link que pareça matéria
    if not links:
        try:
            loc = page.locator('a[href*="/web/dou/-/"], a[href*="/materia/-/"]')
            count = await loc.count()
            for i in range(min(count, 800)):
                try:
                    a = loc.nth(i)
                    await consider(await a.get_attribute("href"), await a.inner_text())
                except Exception:
                    continue
        except Exception:
            pass

    # 3) Fallback profundo (inclui Shadow DOM)
    if not links:
        try:
            deep = await _deep_collect_anchors(page)
            for item in deep:
                await consider(item["href"], item["text"])
        except Exception:
            pass

    items = [{"url": u, "titulo": t} for u, t in links.items()]
    logger.debug(
        "_collect_links_from_listing -> %d link(s). Discards=%s",
        len(items),
        discards,
    )
    return items


async def _collect_paginated_results(
    page: Page,
    max_pages: int = 5,
) -> List[Dict[str, str]]:
    """
    Varre paginação clicando em 'Próximo' (quando existir), até max_pages.
    """
    seen_urls: Set[str] = set()
    all_items: List[Dict[str, str]] = []
    page_idx = 1

    while True:
        await _wait_results(page, timeout_ms=15000)
        items = await _collect_links_from_listing(page)
        new_count = 0
        for it in items:
            if it["url"] not in seen_urls:
                seen_urls.add(it["url"])
                all_items.append(it)
                new_count += 1

        logger.debug(
            "Página %d: %d itens, %d novos (total acumulado: %d).",
            page_idx,
            len(items),
            new_count,
            len(all_items),
        )

        # Tentar avançar para "Próximo"
        next_clicked = False
        for sel in [
            "a[aria-label*='próxima']",
            "a[aria-label*='próximo']",
            "a[title*='próxima']",
            "a[title*='próximo']",
            "a:has-text('Próximo')",
            "button:has-text('Próximo')",
        ]:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    await loc.click(timeout=2000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    next_clicked = True
                    page_idx += 1
                    break
            except Exception:
                continue

        # Fallback: pequeno scroll (pode disparar lazy-load)
        if not next_clicked:
            try:
                before = await page.evaluate("document.body.scrollHeight")
                for _ in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(600)
                    after = await page.evaluate("document.body.scrollHeight")
                    if after <= before:
                        break
                    before = after
            except Exception:
                pass

        # Parar se não clicou em próximo ou atingiu limite de páginas
        if (not next_clicked) or (page_idx >= max_pages):
            break

    return all_items


async def _resolve_to_materia(page: Page, url: str) -> str:
    """
    Garante que voltamos com URL que seja claramente de matéria do DOU.
    """
    if "/web/dou/-/" in url or "/materia/-/" in url:
        return url

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        loc = page.locator('a[href*="/web/dou/-/"], a[href*="/materia/-/"]').first
        if await loc.count() > 0:
            href = await loc.get_attribute("href")
            if href:
                return absolutize(href)
    except Exception:
        pass

    return url


async def _enrich_listing_item(page: Page, item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Abre a matéria e extrai título, órgão, tipo, número e data (quando possível).
    """
    final_url = await _resolve_to_materia(page, item["url"])
    try:
        await page.goto(final_url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        # Se der erro, devolve só o básico
        return {
            "url": final_url,
            "titulo": item.get("titulo") or "(sem título)",
            "orgao": None,
            "tipo": None,
            "numero": None,
            "data": None,
        }

    html = await page.content()
    soup = BeautifulSoup(html, "lxml")

    titulo = item.get("titulo") or (soup.title.get_text(strip=True) if soup.title else "")

    # órgão (heurísticas)
    orgao = None
    for sel in [".orgao", ".row-orgao", ".info-orgao", "section.orgao", "header .orgao"]:
        el = soup.select_one(sel)
        if el:
            orgao = el.get_text(" ", strip=True)
            break
    if not orgao:
        m = re.search(r"Órg[aã]o:\s*([^\n]+)", soup.get_text("\n", strip=True), re.I)
        if m:
            orgao = m.group(1).strip()

    # tipo / número (heurísticas simples)
    tipo = None
    numero = None
    full_text = soup.get_text("\n", strip=True)

    m = re.search(
        r"(Portaria|Resolu[cç][aã]o|Instru[cç][aã]o Normativa|Despacho|Aviso)",
        full_text,
        re.I,
    )
    if m:
        tipo = m.group(1).strip()

    m = re.search(r"n[ºo]\s*([\w./-]+)", full_text, re.I)
    if m:
        numero = m.group(1).strip()

    # data de publicação
    data_pub = None
    for sel in [".data-publicacao", ".dataPub", ".data-publicacao-dou"]:
        el = soup.select_one(sel)
        if el:
            data_pub = el.get_text(" ", strip=True)
            break
    if not data_pub:
        m = re.search(
            r"Data de public[aç][aã]o:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
            full_text,
            re.I,
        )
        if m:
            data_pub = m.group(1).strip()

    return {
        "url": final_url,
        "titulo": titulo or "(sem título)",
        "orgao": orgao,
        "tipo": tipo,
        "numero": numero,
        "data": data_pub,
    }


# -------------------------------------------------------------------
# Classe principal
# -------------------------------------------------------------------
class DouScraper:
    """
    Scraper do DOU baseado na lógica do main.py antigo:
    - Usa build_direct_query_url (URL de consulta)
    - Usa Playwright para carregar resultados e paginar
    - Coleta links da listagem e enriquece cada matéria
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

    async def run(self) -> List[Publication]:
        """Alias amigável para search()."""
        return await self.search()

    async def search(self) -> List[Publication]:
        """
        Executa buscas para todas as frases x seções usando URL direta,
        paginação e enriquecimento das matérias.
        """
        if not self.phrases:
            logger.warning("Nenhuma frase de busca configurada; retornando lista vazia.")
            return []

        logger.info("Iniciando busca real no DOU (URL direta + paginação)...")

        all_pubs: List[Publication] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                for section in self.sections:
                    for phrase in self.phrases:
                        pubs = await self._search_phrase_section(
                            page=page,
                            phrase=phrase,
                            section=section,
                        )
                        all_pubs.extend(pubs)
            finally:
                await context.close()
                await browser.close()

        # Deduplicar por URL
        seen_urls: Set[str] = set()
        unique_pubs: List[Publication] = []
        for pub in all_pubs:
            if not pub.url or pub.url in seen_urls:
                continue
            seen_urls.add(pub.url)
            unique_pubs.append(pub)

        logger.info("Total de publicações únicas retornadas: %d", len(unique_pubs))
        return unique_pubs

    async def _search_phrase_section(
        self,
        page: Page,
        phrase: str,
        section: str,
    ) -> List[Publication]:
        """
        Faz a busca para uma única combinação de frase + seção,
        usando URL direta + paginação + enriquecimento.
        """
        url = build_direct_query_url(
            phrase=phrase,
            period=self.period,
            section_code=section,
        )
        logger.info("Abrindo URL (seção=%s, frase=%r): %s", section, phrase, url)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            logger.warning("Falha ao carregar URL de busca: %s", e)
            return []

        items = await _collect_paginated_results(
            page=page,
            max_pages=self.max_pages,
        )
        logger.info(
            "Encontrados %d candidato(s) na listagem para frase=%r seção=%s",
            len(items),
            phrase,
            section,
        )

        pubs: List[Publication] = []
        for it in items:
            meta = await _enrich_listing_item(page, it)
            data_str = meta.get("data")
            pub_date = None
            if data_str:
                try:
                    pub_date = datetime.strptime(data_str.strip(), "%d/%m/%Y").date()
                except Exception:
                    pub_date = None

            pub = Publication(
                title=meta.get("titulo") or it.get("titulo") or "",
                url=meta.get("url") or it.get("url"),
                section=section.upper() if section else None,
                pub_date=pub_date,
                organ=meta.get("orgao"),
                tipo=meta.get("tipo"),
                numero=meta.get("numero"),
            )
            pubs.append(pub)

        return pubs
