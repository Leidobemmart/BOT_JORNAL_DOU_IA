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


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # Ajusta o logger raiz para o nível escolhido
    logging.getLogger().setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.info("Log configurado com nível %s", level.upper())


async def _run_bot() -> None:
    """
    Fluxo principal do robô:
    - Lê config.yml + variáveis de ambiente
    - Se FORCE_TEST_EMAIL=true -> envia email de teste e sai
    - Senão, roda o DouScraper, filtra publicações novas e envia email
    """
    logger.info("=" * 60)
    logger.info("INICIANDO DOU BOT (versão com scraper real do DOU)")

    force_test_email = os.getenv("FORCE_TEST_EMAIL", "false").lower() == "true"
    logger.info("FORCE_TEST_EMAIL = %s", force_test_email)

    # 1) Carregar configuração
    logger.info("Carregando configurações do config.yml + variáveis de ambiente...")
    config = load_config()
    logger.info(
        "Config carregada: %d frases, seções=%s, período=%s",
        len(config.search.phrases),
        ",".join(config.search.sections),
        config.search.period,
    )

    # 2) Modo de teste de email (sem acessar DOU)
    if force_test_email:
        logger.info("FORCE_TEST_EMAIL está ativo - enviando email de teste e finalizando.")
        send_test_email(config, reason="FORCE_TEST_EMAIL=true (sem consulta ao DOU)")
        return

    # 3) Scraper do DOU
    logger.info("Inicializando DouScraper...")
    scraper = DouScraper(
        phrases=config.search.phrases,
        sections=config.search.sections,
        period=config.search.period,
        max_pages=config.search.max_pages,
    )

    logger.info("Executando buscas no DOU...")
    all_pubs = await scraper.search_all()
    logger.info("Total de publicações encontradas (brutas): %d", len(all_pubs))

    # 4) Estado (para não reenviar o que já foi enviado antes)
    state = StateManager()
    state.load()

    new_pubs = [p for p in all_pubs if not state.has(p)]
    logger.info("Publicações novas (não vistas ainda): %d", len(new_pubs))

    if not new_pubs:
        logger.info("Nenhuma publicação nova encontrada. Nada será enviado por email.")
        return

    # 5) Montar email (assunto, HTML, texto plano)
    logger.info("Montando email com %d publicações...", len(new_pubs))
    subject, html_body, text_body = build_publications_email(config, new_pubs)

    # 6) Enviar email
    logger.info("Enviando email...")
    send_email(config, subject, html_body, text_body)
    logger.info("Email enviado com sucesso.")

    # 7) Atualizar estado (marcar como vistas)
    logger.info("Atualizando estado (seen.json)...")
    state.add_many(new_pubs)
    state.save()

    logger.info("DOU BOT finalizado com sucesso.")
    logger.info("=" * 60)


def main() -> None:
    # Lê LOG_LEVEL do ambiente (default INFO)
    log_level = os.getenv("LOG_LEVEL", "INFO")
    setup_logging(log_level)

    try:
        asyncio.run(_run_bot())
    except Exception as e:
        logging.getLogger("dou_bot").error("Erro fatal no bot: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Executar via: python -m src.bot
    main()
