# Construção do conteúdo
"""
Construtor de emails para o robô DOU.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..models.publication import Publication, EmailConfig as EmailConfigModel
from .templates import EmailTemplates
from .sender import EmailSender, EmailRecipients, EmailConfig as EnvEmailConfig

logger = logging.getLogger(__name__)


class EmailBuilder:
    """Constrói e envia emails do boletim DOU."""
    
    def __init__(self, email_config: EmailConfigModel):
        """
        Inicializa o construtor de emails.
        
        Args:
            email_config: Configuração de email
        """
        self.email_config = email_config
        
        # Carregar configuração de ambiente (para CC/BCC)
        self.env_config = EnvEmailConfig.from_env()
        
        logger.info("EmailBuilder inicializado")
    
    def build(
        self,
        publications: List[Publication],
        search_config: Dict[str, Any],
        include_ai_summaries: bool = True
    ) -> Dict[str, Any]:
        """
        Constrói o conteúdo do email.
        
        Args:
            publications: Lista de publicações
            search_config: Configuração da busca
            include_ai_summaries: Incluir resumos de IA
        
        Returns:
            Dicionário com conteúdo do email pronto para envio
        """
        logger.info(f"Construindo email com {len(publications)} publicações")
        
        # Criar conteúdo usando templates
        email_content = EmailTemplates.create_daily_bulletin(
            publications=publications,
            search_config=search_config,
            email_config={
                'subject_prefix': self.email_config.subject_prefix
            },
            include_ai_summaries=include_ai_summaries
        )
        
        # Preparar destinatários
        recipients = self._prepare_recipients()
        
        # Preparar remetente
        from_email = self._prepare_from_email()
        
        return {
            'subject': email_content['subject'],
            'html_content': email_content['html'],
            'text_content': email_content['text'],
            'recipients': recipients,
            'from_email': from_email,
            'reply_to': from_email  # Usar mesmo email para resposta
        }
    
    def _prepare_recipients(self) -> EmailRecipients:
        """Prepara a lista de destinatários."""
        # Usar lista de config.yml como base
        to_emails = self.email_config.to.copy()
        
        # Adicionar emails de variáveis de ambiente (se houver)
        env_to = self.env_config.get('to_emails', [])
        for email in env_to:
            if email not in to_emails:
                to_emails.append(email)
        
        # Carregar CC e BCC das variáveis de ambiente
        cc_emails = self.env_config.get('cc_emails', [])
        bcc_emails = self.env_config.get('bcc_emails', [])
        
        return EmailRecipients(
            to=to_emails,
            cc=cc_emails,
            bcc=bcc_emails
        )
    
    def _prepare_from_email(self) -> str:
        """Prepara o email do remetente."""
        # Prioridade: variável de ambiente > config.yml
        from_env = self.env_config.get('from_email')
        if from_env:
            return from_env
        
        return self.email_config.from_
    
    async def send_test_email(self, email_sender: EmailSender) -> bool:
        """
        Envia email de teste.
        
        Args:
            email_sender: Instância do EmailSender
        
        Returns:
            True se enviado com sucesso
        """
        try:
            logger.info("Preparando email de teste...")
            
            # Criar conteúdo de teste
            test_content = EmailTemplates.create_test_email()
            
            # Preparar destinatários
            recipients = self._prepare_recipients()
            
            # Se não houver destinatários, usar remetente como teste
            if not recipients.has_recipients:
                from_email = self._prepare_from_email()
                recipients = EmailRecipients(to=[from_email])
                logger.warning("Usando remetente como destinatário de teste")
            
            # Enviar email
            success = await email_sender.send(
                subject=test_content['subject'],
                html_content=test_content['html'],
                text_content=test_content['text'],
                recipients=recipients,
                from_email=self._prepare_from_email()
            )
            
            if success:
                logger.info("✅ Email de teste enviado com sucesso")
            else:
                logger.error("❌ Falha ao enviar email de teste")
            
            return success
            
        except Exception as e:
            logger.error(f"Erro ao enviar email de teste: {e}")
            return False
    
    def validate_configuration(self) -> bool:
        """Valida a configuração de email."""
        # Validar configuração do ambiente
        if not EnvEmailConfig.validate(self.env_config):
            logger.error("Configuração de email do ambiente inválida")
            return False
        
        # Validar destinatários
        recipients = self._prepare_recipients()
        if not recipients.has_recipients:
            logger.error("Nenhum destinatário configurado")
            return False
        
        # Validar remetente
        from_email = self._prepare_from_email()
        if not from_email or '@' not in from_email:
            logger.error("Remetente inválido")
            return False
        
        logger.info("Configuração de email validada com sucesso")
        return True
    
    def get_recipient_summary(self) -> str:
        """Retorna um resumo dos destinatários configurados."""
        recipients = self._prepare_recipients()
        
        summary = []
        
        if recipients.to:
            summary.append(f"Para: {len(recipients.to)} email(s)")
        
        if recipients.cc:
            summary.append(f"CC: {len(recipients.cc)} email(s)")
        
        if recipients.bcc:
            summary.append(f"BCC: {len(recipients.bcc)} email(s)")
        
        return ", ".join(summary)
