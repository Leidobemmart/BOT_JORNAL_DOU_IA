# Seletores CSS para DOU
"""
Seletores CSS para o site do DOU.
"""

# Seletores para resultados de busca
RESULT_SELECTORS = [
    "a.resultado-item-titulo",
    "a[href*='/web/dou/-/']",
    "a[href*='/materia/']",
    "div.resultado-item a",
    ".resultado-titulo a"
]

# Seletores para conteúdo principal
CONTENT_SELECTORS = [
    "div.texto-dou",
    "article#materia",
    "div.dou-conteudo",
    "div.materia-conteudo",
    "section.conteudo"
]

# Seletores para metadados
METADATA_SELECTORS = {
    'orgao': [
        ".orgao-dou-data",
        ".info-orgao",
        ".row-orgao",
        'span[class*="orgao"]',
        'p:contains("Órgão:")'
    ],
    'data': [
        ".publicado-dou-data",
        ".data-publicacao",
        'span[class*="data"]',
        'p:contains("Publicado em:")',
        'time'
    ],
    'secao': [
        ".secao-dou-data",
        'span[class*="secao"]',
        'p:contains("Seção:")'
    ],
    'pagina': [
        ".pagina-dou-data",
        'span[class*="pagina"]',
        'p:contains("Página:")'
    ],
    'edicao': [
        ".edicao-dou-data",
        'span[class*="edicao"]',
        'p:contains("Edição:")'
    ]
}

# Seletores para elementos a remover
UNWANTED_SELECTORS = [
    'header',
    'footer',
    'nav',
    'aside',
    '.social-media-share',
    '.barra-botoes-materia',
    '.cabecalho-dou',
    '.detalhes-dou',
    '.informacao-conteudo-dou',
    '.rodape-dou',
    '.voltar-topo',
    '.back-to-top',
    '.modal',
    '.portlet',
    '.breadcrumb',
    'button',
    '.btn',
    '.compartilhe',
    'script',
    'style',
    'iframe',
    '.advertisement',
    '.newsletter',
    '.related-content'
]

# Seletores para botões de paginação
PAGINATION_SELECTORS = [
    "a:has-text('Próximo')",
    "a:has-text('Proximo')",
    "button:has-text('Próximo')",
    "button:has-text('Proximo')",
    "a[title*='Próximo']",
    "a[title*='Proximo']",
    "li.next a",
    "li.pagination-next a",
    "a.next"
]

# Textos que indicam "nenhum resultado"
NO_RESULTS_TEXTS = [
    "Nenhum resultado",
    "Não foram encontrados",
    "0 resultados",
    "nenhum registro",
    "Não encontramos"
]

# Textos de menu/navegação para ignorar
MENU_TEXTS = [
    "Última hora",
    "Voltar ao topo",
    "Pesquisa avançada",
    "Verificação de autenticidade",
    "Portal",
    "Tutorial",
    "Termo de Uso",
    "Ir para o conteúdo",
    "Ir para o rodapé",
    "REPORTAR ERRO",
    "Diário Oficial da União",
    "ACESSE O SCRIPT",
    "Compartilhe o conteúdo",
    "Versão certificada",
    "Diário Completo",
    "Impressão"
]

# URLs que devem ser rejeitadas
REJECT_URL_PATTERNS = [
    "consulta/-/buscar/dou",
    "web/guest/",
    "leiturajornal",
    "javascript:",
    "#",
    "acesso-",
    "govbr",
    "logout",
    "login",
    "registro"
]

# URLs que devem ser aceitas (padrões regex)
ACCEPT_URL_PATTERNS = [
    r"^https://www\.in\.gov\.br/web/dou/-/",
    r"^https://www\.in\.gov\.br/materia/-/",
    r"/web/dou/-/[^/]+$",
    r"/materia/-/[^/]+$"
]
