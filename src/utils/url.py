# Utilitários de URL
"""
Utilitários para processamento de URLs.
"""
import re
from urllib.parse import quote_plus, urlparse
from typing import Optional


def absolutize(href: str, base_url: str = "https://www.in.gov.br") -> str:
    """
    Converte uma URL relativa em absoluta.
    
    Args:
        href: URL (pode ser relativa ou absoluta)
        base_url: URL base para conversão
    
    Returns:
        URL absoluta
    """
    if not href:
        return ""
    
    href = href.strip()
    
    # Já é absoluta
    if href.startswith(('http://', 'https://')):
        return href
    
    # Protocolo relativo
    if href.startswith('//'):
        return 'https:' + href
    
    # Caminho absoluto
    if href.startswith('/'):
        return base_url + href
    
    # Caminho relativo
    return base_url + '/' + href.lstrip('./')


def ensure_quoted(s: str) -> str:
    """
    Garante que uma string esteja entre aspas duplas.
    
    Args:
        s: String
    
    Returns:
        String entre aspas
    """
    s = s.strip()
    if not (s.startswith('"') and s.endswith('"')):
        return f'"{s}"'
    return s


def strip_outer_quotes(s: str) -> str:
    """
    Remove aspas duplas no início/fim da string.
    
    Args:
        s: String
    
    Returns:
        String sem aspas externas
    """
    s = s.strip()
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return s[1:-1]
    return s


def extract_materia_id(url: str) -> Optional[str]:
    """
    Tenta extrair um ID numérico longo da URL da matéria.
    
    Args:
        url: URL da matéria
    
    Returns:
        ID ou None
    """
    pattern = r'/-(?:[^/]+/)*(\d{6,})/?$'
    match = re.search(pattern, url)
    return match.group(1) if match else None


def is_dou_materia_url(url: str) -> bool:
    """
    Verifica se uma URL é de uma matéria do DOU.
    
    Args:
        url: URL a verificar
    
    Returns:
        True se for URL de matéria
    """
    patterns = [
        r'^https://www\.in\.gov\.br/web/dou/-/',
        r'^https://www\.in\.gov\.br/materia/-/',
        r'/web/dou/-/',
        r'/materia/-/'
    ]
    
    return any(re.search(pattern, url) for pattern in patterns)


def build_direct_query_url(phrase: str, period: str, section_code: str) -> str:
    """
    Constrói URL de busca direta no DOU.
    
    Args:
        phrase: Frase de busca
        period: Período (today, week, month, any)
        section_code: Código da seção (do1, do2, do3, todos)
    
    Returns:
        URL de busca
    """
    # Mapear período para parâmetro exactDate
    period_map = {
        'today': 'dia',
        'day': 'dia',
        'dia': 'dia',
        'hoje': 'dia',
        'edicao': 'dia',
        'edição': 'dia',
        'week': 'semana',
        'semana': 'semana',
        'month': 'mes',
        'mes': 'mes',
        'mês': 'mes',
        'any': 'all',
        'all': 'all',
        'qualquer': 'all'
    }
    
    exact = period_map.get(period.lower(), 'dia')
    
    # Garantir seção válida
    if section_code not in {'do1', 'do2', 'do3', 'todos'}:
        section_code = 'do1'
    
    # Preparar frase de busca
    phrase_clean = strip_outer_quotes(phrase)
    phrase_encoded = '%22' + quote_plus(phrase_clean) + '%22'
    
    return (
        "https://www.in.gov.br/consulta/-/buscar/dou"
        f"?q={phrase_encoded}&s={section_code}&exactDate={exact}&sortType=0"
    )


def get_url_domain(url: str) -> Optional[str]:
    """
    Extrai o domínio de uma URL.
    
    Args:
        url: URL completa
    
    Returns:
        Domínio ou None
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return None
