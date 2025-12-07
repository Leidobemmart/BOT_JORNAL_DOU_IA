# Validações
"""
Validações diversas.
"""
import re
from typing import List, Pattern
from datetime import datetime

def compile_accept_patterns(patterns: List[str]) -> List[Pattern]:
    """
    Compila uma lista de padrões em regex.
    """
    compiled = []
    for p in patterns:
        if not p:
            continue
        try:
            compiled.append(re.compile(p))
        except re.error:
            # Se quiser, pode logar o erro aqui
            continue
    return compiled


def compile_accept_patterns(patterns: List[str]) -> List[Pattern]:
    """
    Compila lista de strings regex em padrões regex.
    
    Args:
        patterns: Lista de padrões em string
    
    Returns:
        Lista de regex compiladas
    """
    compiled = []
    for p in patterns:
        if not p:
            continue
        try:
            compiled.append(re.compile(p))
        except re.error:
            # Se quiser logar ou apenas ignorar padrão inválido
            continue
    return compiled

def should_reject_url(url: str, reject_patterns: List[str]) -> bool:
    """
    Verifica se uma URL deve ser rejeitada.
    
    Args:
        url: URL a verificar
        reject_patterns: Lista de padrões para rejeitar
    
    Returns:
        True se deve rejeitar
    """
    if not url:
        return True
    
    url_lower = url.lower()
    
    for pattern in reject_patterns:
        if pattern.lower() in url_lower:
            return True
    
    return False


def matches_accept_patterns(url: str, accept_patterns: List[Pattern]) -> bool:
    """
    Verifica se uma URL corresponde aos padrões de aceitação.
    
    Args:
        url: URL a verificar
        accept_patterns: Lista de regex compiladas
    
    Returns:
        True se corresponder a pelo menos um padrão
    """
    if not accept_patterns:
        return True
    
    for pattern in accept_patterns:
        if pattern.search(url):
            return True
    
    return False


def title_contains_keywords(title: str, keywords: List[str]) -> bool:
    """
    Verifica se o título contém palavras-chave.
    
    Args:
        title: Título a verificar
        keywords: Lista de palavras-chave
    
    Returns:
        True se contiver pelo menos uma palavra-chave
    """
    if not keywords:
        return True
    
    if not title:
        return False
    
    title_upper = title.upper()
    
    for keyword in keywords:
        if keyword and keyword.upper() in title_upper:
            return True
    
    return False


def orgao_contains_keywords(orgao: str, keywords: List[str]) -> bool:
    """
    Verifica se o órgão contém palavras-chave.
    
    Args:
        orgao: Nome do órgão
        keywords: Lista de palavras-chave
    
    Returns:
        True se contiver pelo menos uma palavra-chave
    """
    if not keywords:
        return True
    
    if not orgao:
        # Se não temos órgão, preferimos manter (não filtrar)
        return True
    
    from .text import normalize
    
    orgao_normalized = normalize(orgao)
    
    for keyword in keywords:
        if not keyword:
            continue
        
        keyword_normalized = normalize(keyword)
        if keyword_normalized in orgao_normalized:
            return True
    
    return False


def is_valid_br_date(date_str: str) -> bool:
    """
    Verifica se uma string é uma data válida no formato DD/MM/YYYY.
    
    Args:
        date_str: String de data
    
    Returns:
        True se for válida
    """
    try:
        datetime.strptime(date_str, "%d/%m/%Y")
        return True
    except (ValueError, TypeError):
        return False


def parse_br_date(date_str: str) -> datetime:
    """
    Converte string DD/MM/YYYY para datetime.
    
    Args:
        date_str: String de data
    
    Returns:
        datetime ou 01/01/1970 em caso de erro
    """
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except (ValueError, TypeError):
        return datetime(1970, 1, 1)
