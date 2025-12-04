#!/usr/bin/env python3
"""
Teste da configuração de IA.
"""
import os
import asyncio
import sys
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ai.summarizer import Summarizer
from models.publication import AIConfig

async def test_gemini():
    """Testa conexão com Gemini."""
    print("🧪 Testando Google Gemini...")
    
    if not os.getenv('GEMINI_API_KEY'):
        print("❌ GEMINI_API_KEY não configurada")
        return False
    
    config = AIConfig(
        enabled=True,
        model="gemini-1.5-flash",
        max_chars_input=2000
    )
    
    try:
        summarizer = Summarizer(config)
        
        # Texto de teste
        test_text = """
        LEI Nº 15.270, DE 26 DE NOVEMBRO DE 2025
        
        Altera a Lei nº 9.250, de 26 de dezembro de 1995, e a Lei nº 9.249, 
        de 26 de dezembro de 1995, para instituir a redução do imposto sobre 
        a renda devido nas bases de cálculo mensal e anual e a tributação mínima 
        para as pessoas físicas que auferem altas rendas.
        
        Art. 1º Esta Lei altera a Lei nº 9.250, de 26 de dezembro de 1995, e a 
        Lei nº 9.249, de 26 de dezembro de 1995, para instituir a redução do 
        imposto sobre a renda devido nas bases de cálculo mensal e anual e a 
        tributação mínima para as pessoas físicas que auferem altas rendas.
        """
        
        metadata = {
            'tipo': 'LEI',
            'numero': '15.270/2025',
            'orgao': 'Atos do Poder Legislativo',
            'data': '26/11/2025'
        }
        
        summary = await summarizer.summarize(test_text, metadata)
        
        if summary:
            print("✅ Gemini funcionando!")
            print(f"Resumo: {summary[:200]}...")
            return True
        else:
            print("❌ Gemini não retornou resumo")
            return False
            
    except Exception as e:
        print(f"❌ Erro no Gemini: {e}")
        return False

async def test_huggingface():
    """Testa conexão com Hugging Face."""
    print("\n🧪 Testando Hugging Face...")
    
    if not os.getenv('HF_TOKEN'):
        print("❌ HF_TOKEN não configurada")
        return False
    
    config = AIConfig(
        enabled=True,
        model="recogna-nlp/ptt5-base-summ-xlsum",
        max_chars_input=2000
    )
    
    try:
        summarizer = Summarizer(config)
        
        test_text = "Portaria estabelece novas regras para declaração do IRPF."
        
        metadata = {
            'tipo': 'PORTARIA',
            'numero': '123/2025',
            'orgao': 'Receita Federal',
            'data': '01/12/2025'
        }
        
        summary = await summarizer.summarize(test_text, metadata)
        
        if summary:
            print("✅ Hugging Face funcionando!")
            print(f"Resumo: {summary}")
            return True
        else:
            print("❌ Hugging Face não retornou resumo")
            return False
            
    except Exception as e:
        print(f"❌ Erro no Hugging Face: {e}")
        return False

async def main():
    """Função principal de teste."""
    print("=" * 60)
    print("TESTE DE CONFIGURAÇÃO DE IA")
    print("=" * 60)
    
    # Verificar variáveis de ambiente
    has_gemini = bool(os.getenv('GEMINI_API_KEY'))
    has_hf = bool(os.getenv('HF_TOKEN'))
    
    print(f"GEMINI_API_KEY: {'✅ Configurada' if has_gemini else '❌ Não configurada'}")
    print(f"HF_TOKEN: {'✅ Configurada' if has_hf else '❌ Não configurada'}")
    
    results = []
    
    if has_gemini:
        results.append(await test_gemini())
    
    if has_hf:
        results.append(await test_huggingface())
    
    if not has_gemini and not has_hf:
        print("\n⚠️  Nenhuma API de IA configurada")
        print("O robô funcionará sem resumos automáticos.")
        return 0
    
    print("\n" + "=" * 60)
    print("RESULTADO:")
    print("=" * 60)
    
    if any(results):
        print("✅ IA configurada com sucesso!")
        return 0
    else:
        print("❌ Falha na configuração de IA")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
