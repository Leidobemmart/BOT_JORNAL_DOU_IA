"""
Módulo de email para o robô DOU.
"""

from .sender import EmailSender, SMTPConfig, EmailRecipients, EmailConfig
from .templates import EmailTemplates
from .builder import EmailBuilder

__all__ = [
    'EmailSender',
    'SMTPConfig',
    'EmailRecipients',
    'EmailConfig',
    'EmailTemplates',
    'EmailBuilder'
]
