# src/utils.py
from __future__ import annotations

import re
from urllib.parse import quote_plus
from typing import Optional


def strip_outer_quotes(s: str) -> str:
    """
    Remove aspas duplas no início/fim da string, se existirem.
    """
    s = s.strip()
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return s[1:-1]
    return s


def build_direct_query_url(phrase: str, period: str, section_code: str) -> str:
    """
    Constrói URL de busca direta no DOU.

    Args:
        phrase: Frase de busca
        period: Período (today, week, month, any, etc.)
        section_code: Código da seção (do1, do2, do3, todos)

    Returns:
        URL de busca para a consulta no DOU
    """
    # Mapeia período para o parâmetro exactDate da consulta
    period_map = {
        "today": "dia",
        "day": "dia",
        "dia": "dia",
        "hoje": "dia",
        "edicao": "dia",
        "edição": "dia",
        "week": "semana",
        "semana": "semana",
        "month": "mes",
        "mes": "mes",
        "mês": "mes",
        "any": "all",
        "all": "all",
        "qualquer": "all",
    }

    exact = period_map.get((period or "").lower(), "dia")

    # Garantir seção válida
    if section_code not in {"do1", "do2", "do3", "todos"}:
        section_code = "do1"

    # Preparar frase de busca entre aspas
    phrase_clean = strip_outer_quotes(phrase)
    phrase_encoded = "%22" + quote_plus(phrase_clean) + "%22"

    return (
        "https://www.in.gov.br/consulta/-/buscar/dou"
        f"?q={phrase_encoded}&s={section_code}&exactDate={exact}&sortType=0"
    )



def absolutize(href: str, base_url: str = "https://www.in.gov.br") -> str:
    """
    Converte uma URL relativa em absoluta.
    """
    if not href:
        return ""

    href = href.strip()

    # Já é absoluta
    if href.startswith(("http://", "https://")):
        return href

    # Protocolo relativo
    if href.startswith("//"):
        return "https:" + href

    # Caminho absoluto
    if href.startswith("/"):
        return base_url + href

    # Caminho relativo
    return base_url + "/" + href.lstrip("./")


def is_materia_url(url: str) -> bool:
    """
    Verifica se a URL parece ser de uma matéria do DOU.
    """
    if not url:
        return False

    patterns = [
        r"^https://www\.in\.gov\.br/web/dou/-/",
        r"^https://www\.in\.gov\.br/materia/-/",
        r"/web/dou/-/",
        r"/materia/-/",
    ]

    return any(re.search(p, url) for p in patterns)
