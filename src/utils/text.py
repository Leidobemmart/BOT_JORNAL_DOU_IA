# Utilitários de texto
"""
Utilitários para processamento de texto.
"""
import re
from typing import Optional
from unidecode import unidecode


def normalize(text: str) -> str:
    """
    Normaliza textos (minúsculas, sem acentos, espaços colapsados).
    
    Args:
        text: Texto a ser normalizado
    
    Returns:
        Texto normalizado
    """
    if not text:
        return ""
    
    # Converter para ASCII sem acentos
    text = unidecode(text)
    
    # Converter para minúsculas
    text = text.lower()
    
    # Colapsar espaços múltiplos
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def clean_html_text(text: str) -> str:
    """
    Limpa texto extraído de HTML.
    
    Args:
        text: Texto com possíveis artefatos de HTML
    
    Returns:
        Texto limpo
    """
    if not text:
        return ""
    
    # Remover espaços múltiplos
    text = re.sub(r'\s+', ' ', text)
    
    # Remover caracteres especiais comuns em HTML
    text = re.sub(r'&\w+;', ' ', text)
    
    # Remover quebras de linha múltiplas
    text = re.sub(r'\n+', '\n', text)
    
    return text.strip()


def extract_first_sentence(text: str, max_length: int = 200) -> str:
    """
    Extrai a primeira sentença de um texto.
    
    Args:
        text: Texto completo
        max_length: Comprimento máximo da sentença
    
    Returns:
        Primeira sentença
    """
    if not text:
        return ""
    
    # Encontrar primeira sentença (terminada por . ! ?)
    match = re.search(r'^([^.!?]+[.!?])', text)
    if match:
        sentence = match.group(1).strip()
    else:
        sentence = text
    
    # Limitar tamanho
    if len(sentence) > max_length:
        sentence = sentence[:max_length].rsplit(' ', 1)[0] + '...'
    
    return sentence


def looks_like_menu(text: str) -> bool:
    """
    Verifica se o texto parece ser um item de menu/navegação.
    
    Args:
        text: Texto a verificar
    
    Returns:
        True se parece ser menu
    """
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # Lista de textos de menu conhecidos
    menu_texts = [
        "última hora", "ultima hora",
        "últimas 24 horas", "ultimas 24 horas",
        "semana passada", "mês passado", "mes passado",
        "ano passado", "período personalizado", "periodo personalizado",
        "pesquisa avançada", "pesquisa",
        "verificação de autenticidade", "voltar ao topo",
        "portal", "tutorial", "termo de uso",
        "ir para o conteúdo", "ir para o rodapé",
        "reportar erro", "diário oficial da união",
        "acessibilidade", "alto contraste",
        "compartilhe", "facebook", "twitter", "whatsapp",
        "linkedin", "instagram", "youtube"
    ]
    
    # Padrões de menu
    menu_patterns = [
        r"(últim|ultima|semana|m[eê]s|ano|per[ií]odo).*(\(\d+\))?$",
        r"^[0-9\.\-/]+$",  # Apenas números/datas
        r"^[a-zA-Z]\s*$",  # Apenas uma letra
        r"^\.{3,}$",  # Apenas pontos
    ]
    
    # Verificar contra lista
    if text_lower in menu_texts:
        return True
    
    # Verificar contra padrões
    for pattern in menu_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    # Textos muito curtos provavelmente são menus
    if len(text_lower) < 3:
        return True
    
    return False


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Trunca texto para um comprimento máximo.
    
    Args:
        text: Texto a truncar
        max_length: Comprimento máximo
        suffix: Sufixo a adicionar se truncado
    
    Returns:
        Texto truncado
    """
    if not text or len(text) <= max_length:
        return text or ""
    
    truncated = text[:max_length]
    
    # Tentar quebrar em palavra completa
    if ' ' in truncated:
        truncated = truncated.rsplit(' ', 1)[0]
    
    return truncated + suffix
