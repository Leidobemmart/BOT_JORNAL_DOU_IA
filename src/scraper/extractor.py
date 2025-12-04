# Extração limpa de conteúdo
"""
Extração limpa de conteúdo DOU.
"""
import re
import logging
from typing import Dict, Optional, List
from bs4 import BeautifulSoup, Comment

from .selectors import (
    CONTENT_SELECTORS,
    METADATA_SELECTORS,
    UNWANTED_SELECTORS,
    MENU_TEXTS
)
from utils.text import normalize, looks_like_menu
from utils.url import extract_materia_id

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extrai conteúdo limpo e metadados de páginas DOU."""
    
    def __init__(self):
        self.system_texts = [
            'diário oficial da união',
            'publicado em:', 'edição:', 'seção:', 'página:', 'órgão:',
            'acesse o script', 'compartilhe o conteúdo',
            'voltar ao topo', 'portal da imprensa',
            'reportar erro', 'versão certificada',
            'diário completo', 'impressão',
            'este conteúdo não substitui o publicado na versão certificada',
            'brasão do brasil', 'logo da imprensa'
        ]
    
    def extract(self, html_content: str, url: str = "") -> Dict:
        """
        Extrai conteúdo limpo e metadados.
        
        Args:
            html_content: HTML da página
            url: URL da página (para referência)
        
        Returns:
            Dicionário com conteúdo e metadados
        """
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Extrair metadados
        metadata = self._extract_metadata(soup, url)
        
        # Extrair conteúdo limpo
        clean_text = self._extract_clean_content(soup)
        
        return {
            'titulo': metadata['titulo'],
            'orgao': metadata['orgao'],
            'tipo': metadata['tipo'],
            'numero': metadata['numero'],
            'data': metadata['data'],
            'secao': metadata['secao'],
            'pagina': metadata['pagina'],
            'edicao': metadata['edicao'],
            'texto_bruto': clean_text[:2000],  # Versão curta para logs
            'texto_limpo': clean_text,
            'materia_id': extract_materia_id(url)
        }
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extrai metadados da publicação."""
        metadata = {
            'titulo': self._extract_title(soup),
            'orgao': self._extract_orgao(soup),
            'tipo': None,
            'numero': None,
            'data': self._extract_date(soup),
            'secao': self._extract_secao(soup),
            'pagina': self._extract_pagina(soup),
            'edicao': self._extract_edicao(soup)
        }
        
        # Extrair tipo e número do título/texto
        metadata.update(self._extract_tipo_numero(metadata['titulo'], soup))
        
        logger.debug(f"Metadados extraídos: {metadata}")
        return metadata
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extrai o título da publicação."""
        # Tentar seletores específicos primeiro
        for selector in ['h1', 'h2.portlet-title-text', '.identifica strong']:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) > 10:
                    return title
        
        # Fallback: title tag
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remover sufixo comum
            title = re.sub(r' - DOU - Imprensa Nacional$', '', title)
            if title:
                return title
        
        # Último recurso: primeiro h1, h2 ou h3
        for tag in ['h1', 'h2', 'h3']:
            element = soup.find(tag)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) > 10:
                    return title
        
        return "Sem título"
    
    def _extract_orgao(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrai o órgão emissor."""
        for selector in METADATA_SELECTORS['orgao']:
            element = soup.select_one(selector)
            if element:
                orgao = element.get_text(strip=True)
                # Limpar prefixos comuns
                orgao = re.sub(r'^Órg[aã]o:\s*', '', orgao, flags=re.IGNORECASE)
                if orgao:
                    return orgao
        
        # Buscar por padrão no texto
        text = soup.get_text(' ', strip=True)[:2000]
        match = re.search(r'[ÓO]rg[ãa]o:\s*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrai a data de publicação."""
        for selector in METADATA_SELECTORS['data']:
            element = soup.select_one(selector)
            if element:
                date_text = element.get_text(strip=True)
                # Extrair data no formato DD/MM/YYYY
                match = re.search(r'(\d{2}/\d{2}/\d{4})', date_text)
                if match:
                    return match.group(1)
        
        # Buscar no texto
        text = soup.get_text(' ', strip=True)[:2000]
        date_patterns = [
            r'Publicado em[:\s]+(\d{2}/\d{2}/\d{4})',
            r'Edi[cç][aã]o de[:\s]+(\d{2}/\d{2}/\d{4})',
            r'Data de publica[cç][aã]o[:\s]+(\d{2}/\d{2}/\d{4})',
            r'(\d{2}/\d{2}/\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_secao(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrai a seção do DOU."""
        for selector in METADATA_SELECTORS['secao']:
            element = soup.select_one(selector)
            if element:
                secao = element.get_text(strip=True)
                # Extrair número
                match = re.search(r'(\d+)', secao)
                if match:
                    return match.group(1)
        
        return None
    
    def _extract_pagina(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrai a página do DOU."""
        for selector in METADATA_SELECTORS['pagina']:
            element = soup.select_one(selector)
            if element:
                pagina = element.get_text(strip=True)
                # Extrair número
                match = re.search(r'(\d+)', pagina)
                if match:
                    return match.group(1)
        
        return None
    
    def _extract_edicao(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrai a edição do DOU."""
        for selector in METADATA_SELECTORS['edicao']:
            element = soup.select_one(selector)
            if element:
                edicao = element.get_text(strip=True)
                # Extrair número
                match = re.search(r'(\d+)', edicao)
                if match:
                    return match.group(1)
        
        return None
    
    def _extract_tipo_numero(self, title: str, soup: BeautifulSoup) -> Dict:
        """Extrai tipo e número da publicação."""
        result = {'tipo': None, 'numero': None}
        
        # Primeiro, tentar extrair do título
        if title:
            # Padrão: "LEI Nº 15.270, DE 26 DE NOVEMBRO DE 2025"
            tipo_patterns = [
                (r'\b(LEI)\s+N[º°o\.\s]*([\d\.\-/]+)', 'LEI'),
                (r'\b(PORTARIA)\s+N[º°o\.\s]*([\d\.\-/]+)', 'PORTARIA'),
                (r'\b(DECRETO)\s+N[º°o\.\s]*([\d\.\-/]+)', 'DECRETO'),
                (r'\b(INSTRU[CÇ][AÃ]O NORMATIVA)\s+N[º°o\.\s]*([\d\.\-/]+)', 'INSTRUÇÃO NORMATIVA'),
                (r'\b(RESOLU[CÇ][AÃ]O)\s+N[º°o\.\s]*([\d\.\-/]+)', 'RESOLUÇÃO'),
                (r'\b(ATO DECLARAT[ÓO]RIO)\s+N[º°o\.\s]*([\d\.\-/]+)', 'ATO DECLARATÓRIO'),
                (r'\b(DESPACHO)\s+N[º°o\.\s]*([\d\.\-/]+)', 'DESPACHO')
            ]
            
            for pattern, tipo in tipo_patterns:
                match = re.search(pattern, title, re.IGNORECASE)
                if match:
                    result['tipo'] = tipo
                    result['numero'] = match.group(2)
                    return result
        
        # Se não encontrou no título, buscar no texto
        text = soup.get_text(' ', strip=True)[:3000]
        
        # Buscar tipo genérico
        tipo_match = re.search(
            r'\b(Portaria|Instru[cç][aã]o Normativa|Decreto|Lei|'
            r'Resolu[cç][aã]o|Despacho|Ato Declarat[óo]rio|'
            r'Solu[cç][aã]o de Consulta|Comunicado)\b',
            text,
            re.I
        )
        if tipo_match:
            result['tipo'] = tipo_match.group(1).upper()
        
        # Buscar número
        num_match = re.search(r'\bN[º°o\.\s]*([\d\.]+(?:/\d{4})?)', text, re.I)
        if num_match:
            result['numero'] = num_match.group(1)
        
        return result
    
    def _extract_clean_content(self, soup: BeautifulSoup) -> str:
        """Extrai o conteúdo limpo da publicação."""
        # Encontrar div principal do conteúdo
        content_element = self._find_content_element(soup)
        
        if not content_element:
            logger.warning("Elemento de conteúdo não encontrado")
            return ""
        
        # Remover elementos indesejados
        self._remove_unwanted_elements(content_element)
        
        # Extrair texto
        text = content_element.get_text('\n', strip=True)
        
        # Filtrar linhas
        clean_lines = self._filter_text_lines(text)
        
        return '\n'.join(clean_lines)
    
    def _find_content_element(self, soup: BeautifulSoup):
        """Encontra o elemento principal do conteúdo."""
        # Tentar seletores específicos
        for selector in CONTENT_SELECTORS:
            element = soup.select_one(selector)
            if element:
                return element
        
        # Fallback: procurar por divs com texto significativo
        for div in soup.find_all('div', class_=True):
            if any(keyword in div.get('class', '') for keyword in ['texto', 'conteudo', 'dou', 'materia']):
                if len(div.get_text(strip=True)) > 500:
                    return div
        
        # Último recurso: body
        return soup.body or soup
    
    def _remove_unwanted_elements(self, element):
        """Remove elementos indesejados do conteúdo."""
        # Primeiro, remover por seletores CSS
        for selector in UNWANTED_SELECTORS:
            for el in element.select(selector):
                el.decompose()
        
        # Remover elementos por texto (menus)
        all_elements = element.find_all(['a', 'button', 'span', 'div', 'p'])
        for el in all_elements:
            text = el.get_text(strip=True)
            if looks_like_menu(text):
                el.decompose()
        
        # Remover comentários
        for comment in element.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
    
    def _filter_text_lines(self, text: str) -> List[str]:
        """Filtra linhas de texto, removendo conteúdo irrelevante."""
        lines = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Pular linhas muito curtas
            if len(line) < 25:
                continue
            
            # Verificar se é texto de sistema
            line_lower = line.lower()
            is_system_text = False
            
            for system_text in self.system_texts + MENU_TEXTS:
                if system_text.lower() in line_lower:
                    is_system_text = True
                    break
            
            if is_system_text:
                continue
            
            # Pular linhas que são apenas números/separadores
            if re.match(r'^[\d\s\.\-/]+$', line):
                continue
            
            # Pular linhas que são URLs
            if re.match(r'^https?://', line):
                continue
            
            lines.append(line)
        
        return lines
