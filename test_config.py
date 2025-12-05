#!/usr/bin/env python3
"""
Script para testar configuração do robô DOU.
"""
import os
import sys
from pathlib import Path

# ADIÇÃO CRÍTICA: Adicionar src ao path do Python para resolver imports
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Verificar se os módulos existem
email_module_path = src_path / "email_module"
if not email_module_path.exists():
    print(f"❌ Diretório email_module não encontrado em: {email_module_path}")
    print(f"📁 Estrutura encontrada em {src_path}:")
    if src_path.exists():
        for item in src_path.iterdir():
            print(f"   - {item.name}")
    sys.exit(1)

try:
    from core.logger import setup_logging
    from core.config import Config
    from email_module.builder import EmailBuilder
    from email_module.sender import EmailSender, SMTPConfig, EmailConfig as EnvEmailConfig
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print(f"\n📁 Path atual do Python: {sys.path}")
    print(f"📁 Diretório atual: {os.getcwd()}")
    print(f"📁 Caminho src: {src_path}")
    print(f"📁 Existe src? {src_path.exists()}")
    if src_path.exists():
        print(f"📁 Conteúdo de src/:")
        for item in src_path.iterdir():
            print(f"   - {item.name} {'(diretório)' if item.is_dir() else ''}")
    sys.exit(1)

def test_smtp_connection():
    """Testa conexão SMTP."""
    print("🔍 Testando configuração SMTP...")
    
    try:
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
    except Exception as e:
        print(f"❌ Erro ao carregar configuração SMTP: {e}")
        return False

def test_email_recipients():
    """Testa configuração de destinatários."""
    print("\n👥 Testando destinatários...")
    
    try:
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
    except Exception as e:
        print(f"❌ Erro ao testar destinatários: {e}")
        return False

def test_ai_config():
    """Testa configuração de IA."""
    print("\n🤖 Testando configuração de IA...")
    
    try:
        has_gemini = bool(os.getenv('GEMINI_API_KEY'))
        has_hf = bool(os.getenv('HF_TOKEN'))
        
        if has_gemini:
            print("✅ Google Gemini configurado")
        elif has_hf:
            print("✅ Hugging Face configurado")
        else:
            print("⚠️  IA não configurada (resumos automáticos desabilitados)")
        
        return has_gemini or has_hf
    except Exception as e:
        print(f"❌ Erro ao testar configuração de IA: {e}")
        return False

def test_search_config():
    """Testa configuração de busca."""
    print("\n🔍 Testando configuração de busca...")
    
    try:
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
    except Exception as e:
        print(f"❌ Erro ao testar configuração de busca: {e}")
        return False

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

def test_imports():
    """Testa se todos os imports funcionam corretamente."""
    print("🔧 Testando imports...")
    
    modules_to_test = [
        ("core.logger", "setup_logging"),
        ("core.config", "Config"),
        ("email_module.builder", "EmailBuilder"),
        ("email_module.sender", "EmailSender"),
    ]
    
    all_imports_ok = True
    for module_name, attr_name in modules_to_test:
        try:
            # Tentar importar dinamicamente
            __import__(module_name)
            print(f"   ✅ {module_name}")
        except ImportError as e:
            print(f"   ❌ {module_name}: {e}")
            all_imports_ok = False
    
    return all_imports_ok

def main():
    """Função principal de teste."""
    print("=" * 60)
    print("DOU BOT - TESTE DE CONFIGURAÇÃO")
    print("=" * 60)
    
    # Informações do ambiente
    print(f"📁 Diretório atual: {os.getcwd()}")
    print(f"📁 Caminho src: {src_path}")
    print(f"📁 src existe? {src_path.exists()}")
    
    # Verificar se .env existe
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        print("📁 Arquivo .env encontrado")
        # Carregar variáveis do .env se existir
        from dotenv import load_dotenv
        load_dotenv(env_file)
    else:
        print("⚠️  Arquivo .env não encontrado")
        print("   Certifique-se de configurar as variáveis de ambiente")
    
    tests = [
        test_imports,
        test_config_file,
        test_search_config,
        test_smtp_connection,
        test_email_recipients,
        test_ai_config
    ]
    
    results = []
    for test in tests:
        print(f"\n{'─' * 40}")
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ Erro durante teste: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print("RESULTADO DOS TESTES:")
    print("=" * 60)
    
    for i, (test, result) in enumerate(zip(tests, results), 1):
        test_name = test.__name__.replace('test_', '').replace('_', ' ').title()
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i}. {test_name}: {status}")
    
    all_passed = all(results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 TODOS OS TESTES PASSARAM! O robô está pronto para uso.")
        print("\nPróximos passos:")
        print("1. Execute: python src/main.py")
        print("2. Para teste completo: FORCE_TEST_EMAIL=true python src/main.py")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM. Verifique a configuração.")
        print("\nSolução de problemas:")
        print("1. Verifique se o arquivo config.yml existe e é válido")
        print("2. Configure as variáveis de ambiente (SMTP_HOST, SMTP_PORT, etc.)")
        print("3. Verifique se as credenciais SMTP estão corretas")
        print("4. Certifique-se de que os destinatários estão configurados")
        print("5. Execute: python -c \"import sys; print(sys.path)\" para verificar o PATH")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
