from __future__ import annotations

import logging
from typing import Iterable, List

from .publication import Publication  # import relativo

logger = logging.getLogger(__name__)


class DouScraper:
    """
    Scraper simplificado do DOU.

    Nesta primeira versão ele é só um esqueleto:
    - define a interface pública
    - registra logs
    - retorna uma lista (por enquanto com 1 publicação de exemplo)

    Depois vamos plugar a busca real com Playwright ou com a API oficial.
    """

    def __init__(
        self,
        phrases: Iterable[str],
        sections: Iterable[str],
        period: str = "today",
    ) -> None:
        self.phrases = list(phrases)
        self.sections = list(sections)
        self.period = period

        logger.info(
            "DouScraper inicializado: %d frases, %d seções, período=%s",
            len(self.phrases),
            len(self.sections),
            self.period,
        )

    async def search(self) -> List[Publication]:
        """
        Executa a busca no DOU e retorna uma lista de publicações.

        🔹 Stub: por enquanto devolve 1 publicação de exemplo.
        """
        logger.info(
            "Executando busca stub no DOU. Frases=%s | Seções=%s | Período=%s",
            self.phrases,
            self.sections,
            self.period,
        )

        demo = Publication(
            title="EXEMPLO – Integração do robô com o DOU (stub)",
            url="https://www.in.gov.br/web/dou",
            section="DO1",
        )
        return [demo]
