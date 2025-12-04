# Envio de emails
"""
Envio de emails com suporte para SMTP.
"""
import os
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SMTPConfig:
    """Configuração SMTP."""
    host: str
    port: int
    user: str
    password: str
    use_tls: bool = True
    timeout: int = 30


@dataclass
class EmailRecipients:
    """Destinatários do email."""
    to: List[str]
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    
    def __post_init__(self):
        """Valida e normaliza listas de email."""
        self.to = self._normalize_emails(self.to)
        self.cc = self._normalize_emails(self.cc) if self.cc else []
        self.bcc = self._normalize_emails(self.bcc) if self.bcc else []
    
    @staticmethod
    def _normalize_emails(emails) -> List[str]:
        """Normaliza lista de emails."""
        if isinstance(emails, str):
            # Separar por vírgula ou ponto e vírgula
            emails = [e.strip() for e in emails.replace(';', ',').split(',')]
        elif not isinstance(emails, list):
            emails = []
        
        # Filtrar emails válidos
        valid_emails = []
        for email in emails:
            email = email.strip()
            if email and '@' in email:
                valid_emails.append(email)
        
        return valid_emails
    
    @property
    def all_recipients(self) -> List[str]:
        """Retorna todos os destinatários (to + cc + bcc)."""
        return self.to + self.cc + self.bcc
    
    @property
    def has_recipients(self) -> bool:
        """Verifica se há destinatários."""
        return bool(self.to or self.cc or self.bcc)


class EmailSender:
    """Gerencia envio de emails via SMTP."""
    
    def __init__(self, smtp_config: SMTPConfig):
        """
        Inicializa o enviador de emails.
        
        Args:
            smtp_config: Configuração SMTP
        """
        self.smtp_config = smtp_config
        logger.info(f"EmailSender inicializado para {smtp_config.host}:{smtp_config.port}")
    
    async def send(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        recipients: EmailRecipients,
        from_email: str,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Envia um email.
        
        Args:
            subject: Assunto do email
            html_content: Conteúdo HTML
            text_content: Conteúdo texto simples
            recipients: Destinatários
            from_email: Remetente
            reply_to: Email para resposta (opcional)
        
        Returns:
            True se enviado com sucesso
        """
        if not recipients.has_recipients:
            logger.error("Nenhum destinatário especificado")
            return False
        
        # Criar mensagem
        msg = self._create_message(
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            recipients=recipients,
            from_email=from_email,
            reply_to=reply_to
        )
        
        try:
            # Conectar e enviar
            success = await self._send_via_smtp(msg, recipients.all_recipients, from_email)
            
            if success:
                logger.info(
                    f"Email enviado para {len(recipients.to)} destinatários "
                    f"(CC: {len(recipients.cc)}, BCC: {len(recipients.bcc)})"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Erro ao enviar email: {e}")
            return False
    
    def _create_message(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        recipients: EmailRecipients,
        from_email: str,
        reply_to: Optional[str] = None
    ) -> MIMEMultipart:
        """Cria a mensagem de email."""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['Date'] = formatdate(localtime=True)
        
        # Configurar destinatários
        if recipients.to:
            msg['To'] = ', '.join(recipients.to)
        
        if recipients.cc:
            msg['Cc'] = ', '.join(recipients.cc)
        
        if reply_to:
            msg['Reply-To'] = reply_to
        
        # Adicionar conteúdo
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        return msg
    
    async def _send_via_smtp(
        self,
        msg: MIMEMultipart,
        recipients: List[str],
        from_email: str
    ) -> bool:
        """Envia a mensagem via SMTP."""
        try:
            # Criar contexto SSL
            context = ssl.create_default_context()
            
            # Usar asyncio para operação de rede
            loop = asyncio.get_event_loop()
            
            await loop.run_in_executor(
                None,
                self._sync_send_via_smtp,
                msg,
                recipients,
                from_email,
                context
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Erro SMTP: {e}")
            return False
    
    def _sync_send_via_smtp(
        self,
        msg: MIMEMultipart,
        recipients: List[str],
        from_email: str,
        context: ssl.SSLContext
    ):
        """Versão síncrona para envio SMTP (executada em thread separada)."""
        with smtplib.SMTP(self.smtp_config.host, self.smtp_config.port, timeout=self.smtp_config.timeout) as server:
            server.ehlo()
            
            if self.smtp_config.use_tls:
                server.starttls(context=context)
                server.ehlo()
            
            server.login(self.smtp_config.user, self.smtp_config.password)
            server.sendmail(from_email, recipients, msg.as_string())
    
    async def test_connection(self) -> bool:
        """Testa a conexão com o servidor SMTP."""
        try:
            context = ssl.create_default_context()
            loop = asyncio.get_event_loop()
            
            result = await loop.run_in_executor(
                None,
                self._sync_test_connection,
                context
            )
            
            if result:
                logger.info("Teste de conexão SMTP bem-sucedido")
            else:
                logger.warning("Teste de conexão SMTP falhou")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro no teste de conexão SMTP: {e}")
            return False
    
    def _sync_test_connection(self, context: ssl.SSLContext) -> bool:
        """Versão síncrona do teste de conexão."""
        try:
            with smtplib.SMTP(self.smtp_config.host, self.smtp_config.port, timeout=10) as server:
                server.ehlo()
                
                if self.smtp_config.use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                
                # Testar login apenas se credenciais estiverem configuradas
                if self.smtp_config.user and self.smtp_config.password:
                    server.login(self.smtp_config.user, self.smtp_config.password)
                
                return True
                
        except Exception:
            return False


class EmailConfig:
    """Configuração de email a partir de variáveis de ambiente."""
    
    @staticmethod
    def from_env() -> Dict[str, Any]:
        """
        Carrega configuração de email das variáveis de ambiente.
        
        Returns:
            Dicionário com configuração
        """
        # Carregar destinatários
        to_emails = EmailConfig._parse_email_list('MAIL_TO')
        cc_emails = EmailConfig._parse_email_list('MAIL_CC')
        bcc_emails = EmailConfig._parse_email_list('MAIL_BCC')
        
        # Remetente
        from_email = os.getenv('MAIL_FROM') or os.getenv('SMTP_USER')
        
        # Configuração SMTP
        smtp_config = SMTPConfig(
            host=os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            port=int(os.getenv('SMTP_PORT', '587')),
            user=os.getenv('SMTP_USER', ''),
            password=os.getenv('SMTP_PASS', ''),
            use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            timeout=int(os.getenv('SMTP_TIMEOUT', '30'))
        )
        
        return {
            'smtp_config': smtp_config,
            'from_email': from_email,
            'to_emails': to_emails,
            'cc_emails': cc_emails,
            'bcc_emails': bcc_emails
        }
    
    @staticmethod
    def _parse_email_list(env_var: str) -> List[str]:
        """
        Parseia lista de emails de variável de ambiente.
        
        Args:
            env_var: Nome da variável de ambiente
        
        Returns:
            Lista de emails
        """
        emails_str = os.getenv(env_var, '')
        if not emails_str:
            return []
        
        # Suporta vírgula ou ponto e vírgula como separadores
        emails = []
        for part in emails_str.replace(';', ',').split(','):
            email = part.strip()
            if email and '@' in email:
                emails.append(email)
        
        return emails
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> bool:
        """
        Valida a configuração de email.
        
        Args:
            config: Configuração a validar
        
        Returns:
            True se configuração é válida
        """
        smtp_config = config.get('smtp_config')
        from_email = config.get('from_email')
        
        if not smtp_config:
            logger.error("Configuração SMTP não fornecida")
            return False
        
        # Verificar configuração SMTP mínima
        if not all([smtp_config.host, smtp_config.port, smtp_config.user, smtp_config.password]):
            logger.error("Configuração SMTP incompleta")
            return False
        
        if not from_email or '@' not in from_email:
            logger.error("Remetente inválido")
            return False
        
        # Verificar se há pelo menos um destinatário
        to_emails = config.get('to_emails', [])
        cc_emails = config.get('cc_emails', [])
        bcc_emails = config.get('bcc_emails', [])
        
        if not any([to_emails, cc_emails, bcc_emails]):
            logger.error("Nenhum destinatário configurado")
            return False
        
        logger.debug("Configuração de email validada com sucesso")
        return True
