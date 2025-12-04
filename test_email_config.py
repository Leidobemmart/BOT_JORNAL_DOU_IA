#!/usr/bin/env python3
"""
Teste de configuração de email com CC/BCC.
"""
import sys
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.config import Config
from email.builder import EmailBuilder

def test_config_cc_bcc():
    """Testa se CC/BCC estão sendo lidos do config.yml."""
    print("📧 Testando configuração de email (CC/BCC)...")
    
    # Carregar configuração
    config = Config()
    config.load()
    
    email_config = config.email
    
    print(f"✅ Configuração carregada:")
    print(f"   From: {email_config.from_}")
    print(f"   To: {len(email_config.to)} email(s)")
    
    if email_config.cc:
        print(f"   CC: {len(email_config.cc)} email(s)")
        for email in email_config.cc:
            print(f"     - {email}")
    else:
        print(f"   CC: Nenhum")
    
    if email_config.bcc:
        print(f"   BCC: {len(email_config.bcc)} email(s)")
        for email in email_config.bcc:
            print(f"     - {email}")
    else:
        print(f"   BCC: Nenhum")
    
    # Testar builder
    builder = EmailBuilder(email_config)
    recipients = builder._prepare_recipients()
    
    print(f"\n📨 Destinatários preparados:")
    print(f"   Para: {len(recipients.to)} email(s)")
    print(f"   CC: {len(recipients.cc)} email(s)")
    print(f"   BCC: {len(recipients.bcc)} email(s)")
    
    if recipients.has_recipients:
        print("✅ Configuração de email válida")
        return True
    else:
        print("❌ Nenhum destinatário configurado")
        return False

if __name__ == "__main__":
    success = test_config_cc_bcc()
    sys.exit(0 if success else 1)
