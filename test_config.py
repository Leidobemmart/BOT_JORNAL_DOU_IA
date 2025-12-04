#!/usr/bin/env python3
"""
Script para testar configuração do robô DOU.
"""
import os
import sys
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.logger import setup_logging
from core.config import Config
from email.builder import EmailBuilder
from email.sender import EmailSender, SMTPConfig, EmailConfig as EnvEmailConfig

def test_smtp_connection():
    """Testa conexão SMTP."""
    print("🔍 Testando configuração SMTP...")
    
    # Carregar configuração do ambiente
    env_config = EnvEmailConfig.from_env()
    
    if not EnvEmailConfig.validate(env_config):
        print("❌ Configuração SMTP inválida")
        return False
    
    smtp_config = env_config['smtp_config']
    
    print(f"   Host: {smtp_config.host}:{smtp_config.port}")
    print(f"   Usuário: {smtp_config.user}")
    print(f"   Senha: {'*' * len(smtp_config.password) if smtp_config.password else 'Não configurada'}")
    
    # Testar conexão
    sender = EmailSender(smtp_config)
    
    import asyncio
    try:
        success = asyncio.run(sender.test_connection())
        if success:
            print("✅ Conexão SMTP bem-sucedida")
            return True
        else:
            print("❌ Falha na conexão SMTP")
            return False
    except Exception as e:
        print(f"❌ Erro na conexão SMTP: {e}")
        return False

def test_email_recipients():
    """Testa configuração de destinatários."""
    print("\n👥 Testando destinatários...")
    
    # Carregar configuração
    config = Config()
    config.load()
    
    # Criar builder
    builder = EmailBuilder(config.email)
    
    # Validar configuração
    if builder.validate_configuration():
        summary = builder.get_recipient_summary()
        print(f"✅ {summary}")
        
        # Mostrar emails
        env_config = EnvEmailConfig.from_env()
        if env_config.get('to_emails'):
            print(f"   Para: {', '.join(env_config['to_emails'])}")
        if env_config.get('cc_emails'):
            print(f"   CC: {', '.join(env_config['cc_emails'])}")
        if env_config.get('bcc_emails'):
            print(f"   BCC: {len(env_config['bcc_emails'])} email(s) oculto(s)")
        
        return True
    else:
        print("❌ Configuração de email inválida")
        return False

def test_ai_config():
    """Testa configuração de IA."""
    print("\n🤖 Testando configuração de IA...")
    
    has_gemini = bool(os.getenv('GEMINI_API_KEY'))
    has_hf = bool(os.getenv('HF_TOKEN'))
    
    if has_gemini:
        print("✅ Google Gemini configurado")
    elif has_hf:
        print("✅ Hugging Face configurado")
    else:
        print("⚠️  IA não configurada (resumos automáticos desabilitados)")
    
    return has_gemini or has_hf

def test_search_config():
    """Testa configuração de busca."""
    print("\n🔍 Testando configuração de busca...")
    
    config = Config()
    config.load()
    
    search_cfg = config.search
    
    print(f"   Frases: {len(search_cfg.phrases)} configuradas")
    for i, phrase in enumerate(search_cfg.phrases[:3], 1):
        print(f"     {i}. {phrase}")
    if len(search_cfg.phrases) > 3:
        print(f"     ... e mais {len(search_cfg.phrases) - 3}")
    
    print(f"   Seções: {', '.join(search_cfg.sections)}")
    print(f"   Período: {search_cfg.period}")
    print(f"   Janela: {search_cfg.days_window} dia(s)")
    
    return True

def test_config_file():
    """Testa arquivo de configuração."""
    print("\n📄 Testando arquivo config.yml...")
    
    config_path = Path(__file__).parent / "config.yml"
    
    if not config_path.exists():
        print("❌ Arquivo config.yml não encontrado")
        return False
    
    try:
        config = Config(config_path)
        config.load()
        config.validate()
        print("✅ Configuração válida")
        return True
    except Exception as e:
        print(f"❌ Erro na configuração: {e}")
        return False

def main():
    """Função principal de teste."""
    print("=" * 60)
    print("DOU BOT - TESTE DE CONFIGURAÇÃO")
    print("=" * 60)
    
    # Verificar se .env existe
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        print("📁 Arquivo .env encontrado")
        # Carregar variáveis (opcional, normalmente feito pelo GitHub Actions)
    else:
        print("⚠️  Arquivo .env não encontrado")
        print("   Certifique-se de configurar as variáveis de ambiente")
    
    tests = [
        test_config_file,
        test_search_config,
        test_smtp_connection,
        test_email_recipients,
        test_ai_config
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ Erro durante teste: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("RESULTADO DOS TESTES:")
    print("=" * 60)
    
    for i, (test, result) in enumerate(zip(tests, results), 1):
        test_name = test.__name__.replace('test_', '').replace('_', ' ').title()
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i}. {test_name}: {status}")
    
    all_passed = all(results)
    
    if all_passed:
        print("\n🎉 TODOS OS TESTES PASSARAM! O robô está pronto para uso.")
        print("\nPróximos passos:")
        print("1. Execute: python src/main.py")
        print("2. Para teste completo: FORCE_TEST_EMAIL=true python src/main.py")
    else:
        print("\n⚠️  ALGUNS TESTES FALHARAM. Verifique a configuração.")
        print("\nVerifique:")
        print("1. Arquivo config.yml existe e é válido")
        print("2. Variáveis de ambiente estão configuradas")
        print("3. Credenciais SMTP estão corretas")
        print("4. Destinatários estão configurados")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
