# BOT_JORNAL_DOU_IA
# 🤖 Robô DOU - Monitoramento Automático do Diário Oficial

Robô gratuito que monitora o Diário Oficial da União (DOU) e envia emails diários com publicações relevantes para o setor fiscal/tributário.

## ✨ Funcionalidades

- **Busca Automática**: Monitora publicações do DOU diariamente
- **Foco Fiscal**: Filtra apenas conteúdo relevante para contabilidade/tributação
- **Resumos com IA**: Gera resumos automáticos usando Google Gemini ou Hugging Face
- **Email Profissional**: Envia boletim diário com layout HTML moderno
- **Controle de Estado**: Evita duplicidades com sistema de "já visto"
- **CC/BCC**: Suporte a cópia e cópia oculta
- **GitHub Actions**: Execução automática diária (gratuita)

## 🚀 Começando Rápido

### 1. Clonar e Configurar

```bash
# Clonar repositório
git clone https://github.com/seu-usuario/dou-bot.git
cd dou-bot

# Instalar dependências
pip install -r requirements.txt

# Instalar Playwright
playwright install chromium

# Configurar arquivo de ambiente
cp .env.example .env
# Editar .env com suas credenciais
