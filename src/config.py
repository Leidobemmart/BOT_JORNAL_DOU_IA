from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict

import yaml  # certifique-se de ter pyyaml no requirements.txt

from .models import (
    AppConfig,
    SearchConfig,
    AIConfig,
    EmailSettings,
    SMTPSettings,
)


CONFIG_PATH_DEFAULT = Path(__file__).resolve().parent.parent / "config.yml"


def _load_yaml_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        # Config mínima padrão, caso não exista config.yml
        return {
            "search": {
                "phrases": [],
                "sections": ["do1"],
                "period": "today",
            },
            "ai": {
                "enabled": False,
                "model": "gemini-1.5-flash",
            },
        }

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_email_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [e.strip() for e in value.split(",") if e.strip()]


def load_config(config_path: Path | None = None) -> AppConfig:
    """Carrega configuração completa do robô (YAML + env)."""

    path = config_path or CONFIG_PATH_DEFAULT
    raw_cfg = _load_yaml_config(path)

    # ---- search ----
    search_cfg_raw = raw_cfg.get("search", {}) or {}
    search = SearchConfig(
        phrases=list(search_cfg_raw.get("phrases") or []),
        sections=list(search_cfg_raw.get("sections") or ["do1"]),
        period=str(search_cfg_raw.get("period") or "today"),
    )

    # ---- ai ----
    ai_cfg_raw = raw_cfg.get("ai", {}) or {}
    ai = AIConfig(
        enabled=bool(ai_cfg_raw.get("enabled", False)),
        model=str(ai_cfg_raw.get("model") or "gemini-1.5-flash"),
    )

    # ---- email (vem só do ambiente neste novo desenho) ----
    email_from = os.getenv("EMAIL_FROM", os.getenv("SMTP_USER", ""))

    email = EmailSettings(
        from_addr=email_from,
        to=_parse_email_list(os.getenv("EMAIL_TO")),
        cc=_parse_email_list(os.getenv("EMAIL_CC")),
        bcc=_parse_email_list(os.getenv("EMAIL_BCC")),
    )

    if not email.from_addr:
        raise ValueError("EMAIL_FROM ou SMTP_USER não definidos no ambiente.")

    if not email.to:
        raise ValueError("EMAIL_TO não definido no ambiente (sem destinatários).")

    # ---- SMTP ----
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    missing = [name for name, val in [
        ("SMTP_HOST", smtp_host),
        ("SMTP_PORT", smtp_port),
        ("SMTP_USER", smtp_user),
        ("SMTP_PASS", smtp_pass),
    ] if not val]

    if missing:
        raise ValueError(f"Variáveis SMTP obrigatórias ausentes: {', '.join(missing)}")

    smtp = SMTPSettings(
        host=smtp_host,
        port=int(smtp_port),
        user=smtp_user,
        password=smtp_pass,
        use_tls=True,
    )

    return AppConfig(
        search=search,
        ai=ai,
        email=email,
        smtp=smtp,
    )
