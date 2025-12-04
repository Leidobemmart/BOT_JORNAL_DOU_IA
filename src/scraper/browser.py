# Gerenciamento do Playwright
"""
Gerenciamento do navegador Playwright.
"""
import asyncio
import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserManager:
    """Gerencia o navegador Playwright."""
    
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 45000,
        user_agent: Optional[str] = None
    ):
        """
        Inicializa o gerenciador de navegador.
        
        Args:
            headless: Executar em modo headless
            timeout: Timeout padrão em milissegundos
            user_agent: User agent personalizado
        """
        self.headless = headless
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
        )
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        logger.debug(f"BrowserManager inicializado (headless={headless})")
    
    async def start(self):
        """Inicia o navegador e cria contexto/página."""
        try:
            logger.info("Iniciando navegador Playwright...")
            
            self.playwright = await async_playwright().start()
            
            # Iniciar Chromium
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1920,1080'
                ]
            )
            
            # Criar contexto
            self.context = await self.browser.new_context(
                locale='pt-BR',
                timezone_id='America/Sao_Paulo',
                user_agent=self.user_agent,
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            # Criar página principal
            self.page = await self.context.new_page()
            
            # Configurar timeouts
            self.page.set_default_timeout(self.timeout)
            
            # Configurar event listeners para debugging
            self._setup_event_listeners()
            
            logger.info("Navegador iniciado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar navegador: {e}")
            await self.close()
            raise
    
    async def close(self):
        """Fecha o navegador e libera recursos."""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
                logger.debug("Página fechada")
            
            if self.context:
                await self.context.close()
                logger.debug("Contexto fechado")
            
            if self.browser:
                await self.browser.close()
                logger.debug("Browser fechado")
            
            if self.playwright:
                await self.playwright.stop()
                logger.debug("Playwright parado")
            
            logger.info("Navegador fechado")
            
        except Exception as e:
            logger.error(f"Erro ao fechar navegador: {e}")
    
    def _setup_event_listeners(self):
        """Configura event listeners para debugging."""
        if not self.page:
            return
        
        # Listener para requisições falhas
        self.page.on("requestfailed", lambda request: logger.debug(
            f"Request falhou: {request.url} - {request.failure.error_text}"
        ))
        
        # Listener para console messages
        self.page.on("console", lambda msg: logger.debug(
            f"Console [{msg.type}]: {msg.text}"
        ))
        
        # Listener para page errors
        self.page.on("pageerror", lambda error: logger.error(
            f"Erro na página: {error}"
        ))
    
    async def new_page(self) -> Page:
        """Cria uma nova página no mesmo contexto."""
        if not self.context:
            raise RuntimeError("Contexto do navegador não inicializado")
        
        page = await self.context.new_page()
        page.set_default_timeout(self.timeout)
        logger.debug("Nova página criada")
        return page
    
    async def goto(
        self,
        url: str,
        wait_until: str = "networkidle",
        timeout: Optional[int] = None
    ) -> Page:
        """
        Navega para uma URL na página principal.
        
        Args:
            url: URL para navegar
            wait_until: Quando considerar a navegação concluída
            timeout: Timeout personalizado
        
        Returns:
            A página atual
        """
        if not self.page:
            raise RuntimeError("Página não inicializada")
        
        timeout = timeout or self.timeout
        
        try:
            logger.debug(f"Navegando para: {url}")
            
            response = await self.page.goto(
                url,
                wait_until=wait_until,
                timeout=timeout
            )
            
            if response:
                logger.debug(f"Status: {response.status} - {response.url}")
            
            return self.page
            
        except Exception as e:
            logger.error(f"Erro ao navegar para {url}: {e}")
            raise
    
    async def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: str = "visible"
    ) -> bool:
        """
        Aguarda por um seletor CSS.
        
        Args:
            selector: Seletor CSS
            timeout: Timeout personalizado
            state: Estado esperado (visible, hidden, attached, detached)
        
        Returns:
            True se encontrado, False se timeout
        """
        if not self.page:
            return False
        
        timeout = timeout or self.timeout
        
        try:
            await self.page.wait_for_selector(
                selector,
                timeout=timeout,
                state=state
            )
            return True
            
        except Exception as e:
            logger.debug(f"Timeout ou erro ao esperar por {selector}: {e}")
            return False
    
    async def wait_for_timeout(self, milliseconds: int):
        """Aguarda por um tempo específico."""
        await self.page.wait_for_timeout(milliseconds)
    
    async def get_content(self) -> str:
        """Retorna o conteúdo HTML da página atual."""
        if not self.page:
            return ""
        
        return await self.page.content()
    
    async def screenshot(self, path: str):
        """Tira um screenshot da página atual."""
        if not self.page:
            return
        
        await self.page.screenshot(path=path, full_page=True)
        logger.debug(f"Screenshot salvo em: {path}")
    
    async def evaluate(self, expression: str, *args):
        """
        Executa JavaScript na página.
        
        Args:
            expression: Expressão JavaScript
            *args: Argumentos para a expressão
        
        Returns:
            Resultado da expressão
        """
        if not self.page:
            return None
        
        return await self.page.evaluate(expression, *args)
    
    async def reload(self):
        """Recarrega a página atual."""
        if not self.page:
            return
        
        await self.page.reload()
        logger.debug("Página recarregada")
    
    @property
    def is_ready(self) -> bool:
        """Verifica se o navegador está pronto para uso."""
        return all([self.playwright, self.browser, self.context, self.page])
