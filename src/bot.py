from __future__ import annotations
import asyncio
import logging
import os
import sys

from .config import load_config
from .emailer import send_test_email, send_email, build_publications_email
from .scraper import DouScraper
from .state import StateManager

logger = logging.getLogger("dou_bot")


def setup_logging(level: str | None = None) -> None:
    """Configura logging usando LOG_LEVEL (env) ou INFO por padrão."""
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Log configurado com nível %s", level)


async def _run_bot() -> None:
    logger.info("=" * 60)
    logger.info("INICIANDO DOU BOT (versão com scraper real do DOU)")
    logger.info("=" * 60)

    # 1) Carregar configuração
    cfg = load_config()
    logger.info(
        "Config carregada: %d frases, seções=%s, período=%s, max_pages=%d",
        len(cfg.search.phrases),
        ",".join(cfg.search.sections),
        cfg.search.period,
        cfg.search.max_pages,
    )

    # 2) Checar modo de teste de e-mail
    force_test_email = os.getenv("FORCE_TEST_EMAIL", "").lower() == "true"
    logger.info("FORCE_TEST_EMAIL = %s", force_test_email)

    if force_test_email:
        logger.info("Executando modo de TESTE de e-mail (sem scraping).")
        send_test_email(cfg)
        logger.info("E-mail de teste enviado. Encerrando.")
        return

    # 3) Estado de publicações já vistas
    state = StateManager()
    state.load()

    # 4) Scraper do DOU
    scraper = DouScraper(
        phrases=cfg.search.phrases,
        sections=cfg.search.sections,
        period=cfg.search.period,
        max_pages=cfg.search.max_pages,
    )

    logger.info("Iniciando scraping do DOU...")
    publications = await scraper.search_all()
    logger.info("Scraper retornou %d publicação(ões).", len(publications))

    # 5) Filtrar apenas publicações novas
    new_pubs = [p for p in publications if not state.has(p)]
    logger.info("%d publicação(ões) nova(s) após filtro de estado.", len(new_pubs))

    if not new_pubs:
        logger.info("Nenhuma publicação nova encontrada. Encerrando.")
        return

    # 6) Montar e enviar e-mail
    subject, html_body, text_body = build_publications_email(new_pubs, cfg)
    send_email(subject, html_body, text_body, cfg)
    logger.info("E-mail enviado com sucesso.")

    # 7) Atualizar estado
    state.add_many(new_pubs)
    state.save()
    logger.info("Estado atualizado e salvo. BOT finalizado com sucesso.")


def main() -> None:
    setup_logging()
    try:
        asyncio.run(_run_bot())
    except Exception as exc:
        logger.error("Erro fatal no bot: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
