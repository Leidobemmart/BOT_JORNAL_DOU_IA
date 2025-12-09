from __future__ import annotations
import logging
import sys
from pathlib import Path

from .config import load_config
from .emailer import send_test_email


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger("dou_bot")

    logger.info("=" * 60)
    logger.info("INICIANDO DOU BOT (nova versão simplificada)")
    logger.info("=" * 60)

    try:
        cfg = load_config()
        logger.info("Configuração carregada com sucesso.")
    except Exception as e:
        logger.error("Falha ao carregar configuração: %s", e, exc_info=True)
        sys.exit(1)

    try:
        logger.info("Enviando email de teste...")
        send_test_email(cfg)
        logger.info("Email de teste enviado com sucesso.")
    except Exception as e:
        logger.error("Falha ao enviar email de teste: %s", e, exc_info=True)
        sys.exit(1)

    logger.info("Finalizado com sucesso.")


if __name__ == "__main__":
    # importante: rodar como módulo: python -m src.bot
    main()
