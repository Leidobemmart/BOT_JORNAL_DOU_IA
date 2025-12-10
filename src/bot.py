from __future__ import annotations
import asyncio
import logging
import os
import sys

from .config import load_config
from .emailer import send_test_email, send_email, build_publications_email
from .scraper import DouScraper
from .state import StateManager


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def _run_bot() -> None:
    logger = logging.getLogger("dou_bot")

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

    # 2) Checar se é email de teste forçado
    force_test = os.getenv("FORCE_TEST_EMAIL", "").lower() == "true"
    logger.info("FORCE_TEST_EMAIL = %s", force_test)
    if force_test:
        logger.info("FORCE_TEST_EMAIL=TRUE -> enviando apenas email de teste.")
        send_test_email(cfg)
        logger.info("Email de teste enviado. Encerrando.")
        return

    # 3) Carregar estado
    state = StateManager()
    state.load()

    # 4) Scraper REAL do DOU
    scraper = DouScraper(
        phrases=cfg.search.phrases or ['"tratamento tributário"'],
        sections=cfg.search.sections or ["do1"],
        period=cfg.search.period,
        max_pages=cfg.search.max_pages,
    )

    publications = await scraper.search()
    logger.info("Scraper retornou %d publicação(ões).", len(publications))

    # 5) Filtrar apenas publicações novas
    new_pubs = [p for p in publications if not state.has(p)]
    logger.info("%d publicação(ões) nova(s) após filtro de estado.", len(new_pubs))

    if not new_pubs:
        logger.info("Nenhuma publicação nova para enviar. Encerrando.")
        return

    # 6) Montar e enviar email
    subject, html_body, text_body = build_publications_email(new_pubs, cfg)
    send_email(subject, html_body, text_body, cfg)

    # 7) Atualizar estado
    state.add_many(new_pubs)
    state.save()

    logger.info("BOT finalizado com sucesso.")


def main() -> None:
    setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    try:
        _ = os.getenv("FORCE_TEST_EMAIL", "false")
        logging.getLogger("dou_bot").info('FORCE_TEST_EMAIL = %s', _.lower())
        asyncio.run(_run_bot())
    except Exception as e:
        logging.getLogger("dou_bot").error("Erro fatal no bot: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
