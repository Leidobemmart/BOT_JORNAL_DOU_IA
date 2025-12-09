# src/scraper.py
from __future__ import annotations

import logging
from typing import Iterable, List

from publication import Publication  # importa o dataclass que criamos

logger = logging.getLogger(__name__)


class DouScraper:
    """
    Scraper simplificado do DOU.

    Nesta primeira versão ele é só um esqueleto:
    - define a interface pública
    - registra logs
    - retorna uma lista (por enquanto vazia ou com dados fake)
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

        🔹 Nesta etapa, vamos manter um stub para não quebrar nada:
           - registra no log que a função foi chamada
           - (opcional) retorna 1 publicação de exemplo
        🔹 No próximo passo trocamos a implementação por uma chamada real (Playwright/API).
        """
        logger.info(
            "Executando busca stub no DOU (ainda sem integração real). "
            "Frases: %s | Seções: %s | Período: %s",
            self.phrases,
            self.sections,
            self.period,
        )

        # 👉 Versão ultra-segura: não retorna nada (não manda conteúdo “fake”)
        # return []

        # 👉 Se quiser já ver o fluxo de e-mail funcionando com conteúdo,
        #    podemos devolver 1 publicação de exemplo:
        demo = Publication(
            title="EXEMPLO – Integração do robô com o DOU (stub)",
            url="https://www.in.gov.br/web/dou",
            section="DO1",
        )
        return [demo]
