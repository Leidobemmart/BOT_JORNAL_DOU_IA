"""
Robô de monitoramento do Diário Oficial da União (DOU) – Versão com IA (Hugging Face)
e layout de e-mail em formato de "jornal diário".

Funcionalidades principais:
- Busca termos configuráveis (fiscal/tributário, incentivos etc.) em seções do DOU.
- Foco, por padrão, na EDIÇÃO DO DIA (period: today -> exactDate=dia).
- Envia e-mail com boletim diário de publicações relevantes, evitando duplicidades via state/seen.json.
- (Opcional) Gera resumos automáticos via IA (Hugging Face Inference) para cada matéria.
"""

import os
import re
import json
import sys
import smtplib
import ssl
import asyncio
import time
import html
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import yaml
from bs4 import BeautifulSoup
from unidecode import unidecode
from tenacity import retry, wait_fixed, stop_after_attempt
from playwright.async_api import async_playwright
from huggingface_hub import InferenceClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Caminhos básicos do projeto / logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# Raiz do repositório (assumindo que este arquivo está em src/main.py)
ROOT = Path(__file__).resolve().parents[1]

# Arquivo de estado (publicações já enviadas)
STATE_FILE = ROOT / "state" / "seen.json"

# Arquivo de configuração principal
CONFIG_FILE = ROOT / "config.yml"


# ---------------------------------------------------------------------------
# IA – resumo automático via Hugging Face
# ---------------------------------------------------------------------------

def _prepare_summary_text(full_text: str, max_chars: int) -> str:
    """
    Limpa e limita o texto de entrada para a IA.
    """
    text = (full_text or "").strip()
    if not text:
        return ""
    # Colapsa espaços e quebras de linha
    text = re.sub(r"\s+", " ", text)
    # Limita tamanho máximo
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
    return text


def _postprocess_summary(summary: str, max_chars: int) -> str:
    """
    Limpa, normaliza e limita o resumo gerado pela IA.

    Objetivos:
    - remover aberturas do tipo "O Diário Oficial da União publicou..."
      ou "A Agência ... publicou...";
    - descartar saídas claramente inúteis/hallucinatórias;
    - evitar resumos muito curtos;
    - respeitar o limite de caracteres e terminar bem.
    """
    s = (summary or "").strip()
    if not s:
        return ""

    # Colapsa espaços e quebras de linha
    s = re.sub(r"\s+", " ", s).strip()
    low = s.lower()

    # Frases claramente erradas / metalinguagem de IA
    bad_snippets = [
        "este script",
        "este código",
        "como um modelo de linguagem",
        "i am an ai",
        "sou um modelo de linguagem",
        "sou apenas um modelo",
    ]
    if any(bad in low for bad in bad_snippets):
        return ""

    # Remove aberturas "noticiosas" comuns ("O DOU publicou...", etc.)
    strip_patterns = [
        r"(?i)^o diário oficial da união (publicou|publica)[^,\.]*[,\.]\s*",
        r"(?i)^o diario oficial da uniao (publicou|publica)[^,\.]*[,\.]\s*",
        r"(?i)^o diário oficial (publicou|publica)[^,\.]*[,\.]\s*",
        r"(?i)^o diario oficial (publicou|publica)[^,\.]*[,\.]\s*",
        r"(?i)^a agência nacional[^,\.]* (publicou|publica)[^,\.]*[,\.]\s*",
        r"(?i)^a agencia nacional[^,\.]* (publicou|publica)[^,\.]*[,\.]\s*",
        r"(?i)^o ato declaratório executivo (do )?(ministério da fazenda|ministerio da fazenda|mdf|mfd)[^,\.]*[,\.]\s*",
    ]
    for pat in strip_patterns:
        s = re.sub(pat, "", s).strip()

    low = s.lower()

    # Se ainda sobrou muito "notícia de jornal" pura, podemos descartar
    newsy_snippets = [
        "nesta sexta-feira",
        "nesta quinta-feira",
        "na última sexta-feira",
        "na ultima sexta-feira",
        "na data de hoje",
        "hoje",
    ]
    if any(ns in low for ns in newsy_snippets) and "ato declaratório" not in low and "solução de consulta" not in low:
        # se for só contextualização de data, sem o conteúdo, descarta
        return ""

    # Não aceitar resumos muito curtos
    if len(s) < 60:
        return ""

    # Aplica limite de caracteres
    if max_chars and len(s) > max_chars:
        s = s[:max_chars]
        # corta na última palavra inteira
        if " " in s:
            s = s.rsplit(" ", 1)[0] + "..."

    # Garante que termine com pontuação razoável
    if not s.endswith((".", "!", "?", ";")):
        s += "."

    return s


def _summarize_with_gemini(text: str, ai_cfg: dict) -> str:
    """
    Tenta gerar resumo usando Gemini (Google Generative AI).
    Requer GEMINI_API_KEY configurado.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("[IA] google-generativeai não está instalado; pulando Gemini.")
        return ""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("[IA] GEMINI_API_KEY não definido; pulando Gemini.")
        return ""

    try:
        genai.configure(api_key=api_key)
    except Exception as exc:
        logger.warning("[IA] Falha ao configurar Gemini: %s", exc)
        return ""

    model_id = (ai_cfg.get("model") or "gemini-2.5-flash").strip()
    g_cfg = (ai_cfg.get("gemini") or {}) if isinstance(ai_cfg.get("gemini"), dict) else {}
    temperature = float(g_cfg.get("temperature", 0.2))
    max_output_tokens = int(g_cfg.get("max_tokens", 300))

    prompt = (
        "Você é um analista jurídico-tributário especializado em normas publicadas "
        "no Diário Oficial da União.\n\n"
        "Leia o texto abaixo (apenas o corpo de um ato oficial) e produza um resumo "
        "em português do Brasil, com no máximo 350 caracteres, em um único parágrafo.\n\n"
        "O resumo deve:\n"
        "- indicar, se possível, o tipo do ato (lei, decreto, portaria, instrução normativa etc.);\n"
        "- destacar o tema central e o impacto prático para empresas, com foco em aspectos fiscais, "
        "tributários, regulatórios ou de incentivos;\n"
        "- mencionar tributos, benefícios ou obrigações relevantes, quando existirem;\n"
        "- evitar repetir literalmente o título do ato;\n"
        "- ser objetivo, técnico e sem adjetivos desnecessários.\n\n"
        "Texto do ato (corpo):\n"
        + text
    )

    try:
        model = genai.GenerativeModel(model_id)
        resp = model.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            },
        )
        summary = getattr(resp, "text", "") or ""
        return summary
    except Exception as exc:
        logger.warning("[IA] Erro ao chamar Gemini: %s", exc)
        return ""


def _summarize_with_hf(text: str, ai_cfg: dict) -> str:
    """
    Tenta gerar resumo usando Hugging Face Inference.
    Requer HF_TOKEN configurado.
    """
    token = os.getenv("HF_TOKEN")
    if not token:
        logger.warning("[IA] HF_TOKEN não definido; pulando Hugging Face.")
        return ""

    # Pega modelo específico de HF se existir; se não, cai no "model"
    model_id = (ai_cfg.get("hf_model") or ai_cfg.get("model") or "").strip()
    if not model_id:
        model_id = "recogna-nlp/ptt5-base-summ-xlsum"

    try:
        client = InferenceClient(model=model_id, token=token)
    except Exception as exc:
        logger.warning("[IA] Erro ao inicializar InferenceClient: %s", exc)
        return ""

    try:
        logger.info("[IA] Chamando summarization() para o modelo HF: %s", model_id)
        # IMPORTANTE: sem passar max_new_tokens aqui, para não quebrar
        result = client.summarization(text)
    except Exception as exc:
        logger.warning("[IA] Erro ao chamar Hugging Face Inference: %s", exc)
        return ""

    summary = ""
    # Possíveis formatos de retorno
    if hasattr(result, "summary_text"):
        summary = result.summary_text
    elif isinstance(result, dict) and "summary_text" in result:
        summary = result["summary_text"]
    elif isinstance(result, list) and result and isinstance(result[0], dict):
        summary = result[0].get("summary_text", "")
    elif isinstance(result, str):
        summary = result
    else:
        summary = str(result)

    return summary


def generate_summary_ia(full_text: str, cfg: dict) -> str:
    """
    Gera um resumo curto usando Gemini como provedor principal
    e Hugging Face como fallback.

    - Usa as configs em cfg['ai']['summaries'].
    - Requer GEMINI_API_KEY e/ou HF_TOKEN.
    - Em erro, retorna string vazia para não quebrar o robô.
    """
    ai_cfg = (cfg.get("ai") or {}).get("summaries") or {}
    if not ai_cfg.get("enabled"):
        logger.info("[IA] Summaries desabilitados no config.")
        return ""

    # Limites de entrada/saída
    max_chars_input = int(ai_cfg.get("max_chars_input", 4000))
    max_chars_output = int(ai_cfg.get("max_chars_output", 350))

    text = _prepare_summary_text(full_text, max_chars_input)
    if not text:
        return ""

    provider = (ai_cfg.get("provider") or "gemini").strip().lower()
    summary = ""

    # Provider "gemini" ou "fallback" → tenta Gemini primeiro
    if provider in ("gemini", "fallback"):
        summary = _summarize_with_gemini(text, ai_cfg)
        if summary:
            return _postprocess_summary(summary, max_chars_output)

    # Provider "hf" ou "fallback" ou caso Gemini falhe → tenta HF
    if provider in ("hf", "fallback", "gemini"):
        summary = _summarize_with_hf(text, ai_cfg)
        if summary:
            return _postprocess_summary(summary, max_chars_output)

    logger.info("[IA] Não foi possível gerar resumo com os provedores configurados.")
    return ""

# ---------------------------------------------------------------------------
# Utilitários de configuração e estado
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Lê o config.yml e devolve um dict Python com as configurações do robô."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_seen() -> set:
    """
    Carrega a lista de publicações já enviadas (state/seen.json)
    e devolve um set() para facilitar checagens de duplicidade.
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data if isinstance(data, list) else [])
        except Exception:
            return set()
    return set()


def save_seen(seen: set) -> None:
    """Salva o conjunto de itens já vistos em state/seen.json."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# Função shorten_orgao(...) para encurtar o nome do órgão
# ---------------------------------------------------------------------------

def normalize(txt: str) -> str:
    """
    Normaliza textos (minúsculas, sem acentos, espaços colapsados)
    para facilitar comparações de rótulos como 'Seção 1', órgãos, etc.
    """
    if not txt:
        return ""
    t = unidecode(txt).lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def shorten_orgao(orgao: str) -> str:
    """
    Encurta nomes longos de órgãos para uma forma mais compacta no e-mail.
    Se não bater nenhum padrão, devolve o texto original.
    """
    if not orgao:
        return ""

    o = orgao.strip()

    # Mapeamentos específicos que você já viu na prática
    replacements = [
        (
            "Ministério da Fazenda/Secretaria Especial da Receita Federal do Brasil/Secretaria-Adjunta/Superintendência Regional da Receita Federal do Brasil 8ª Região Fiscal/Delegacia da Receita Federal do Brasil em Sorocaba",
            "Min. Fazenda / RFB / DRF Sorocaba",
        ),
        (
            "Ministério da Fazenda/Secretaria Especial da Receita Federal do Brasil/Secretaria-Adjunta",
            "Min. Fazenda / RFB / Secretaria-Adjunta",
        ),
        (
            "Ministério da Fazenda/Secretaria Especial da Receita Federal do Brasil",
            "Min. Fazenda / RFB",
        ),
        (
            "Ministério da Fazenda/Conselho Nacional de Política Fazendária",
            "Min. Fazenda / Confaz",
        ),
        (
            "Ministério da Ciência, Tecnologia e Inovação/Conselho Nacional de Desenvolvimento Científico e Tecnológico",
            "MCTI / CNPq",
        ),
    ]

    for long_txt, short_txt in replacements:
        if long_txt in o:
            return short_txt

    # Fallback: se ficar muito grande, corta com reticências
    if len(o) > 120:
        return o[:117] + "..."
    return o

def extract_body_snippet(texto_bruto: str, max_chars: int = 320) -> str:
    """
    Extrai um "primeiro trecho do corpo" (fallback sem IA) a partir do texto bruto.
    Remove cabeçalhos comuns do DOU e pega as primeiras frases do conteúdo normativo.

    Retorna string vazia se não conseguir achar algo útil.
    """
    if not texto_bruto:
        return ""

    t = (texto_bruto or "").strip()
    if not t:
        return ""

    # Normaliza espaços/quebras
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)

    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if not lines:
        return ""

    # Remove linhas típicas do cabeçalho do DOU
    header_prefixes = (
        "Brasão do Brasil",
        "Diário Oficial da União",
        "Publicado em:",
        "Edição:",
        "Seção:",
        "Página:",
        "Órgão:",
    )
    cleaned_lines = []
    for ln in lines:
        if any(ln.startswith(p) for p in header_prefixes):
            continue
        # Também ignora linhas isoladas de separador
        if ln in {"|", "•", "-"}:
            continue
        cleaned_lines.append(ln)

    if not cleaned_lines:
        cleaned_lines = lines[:]  # fallback

    # Junta tudo num texto contínuo
    text = " ".join(cleaned_lines)
    text = re.sub(r"\s+", " ", text).strip()

    # Se existir "Assunto:", geralmente é o melhor ponto de corte (ex.: Solução de Consulta)
    m_assunto = re.search(r"\bAssunto:\s*", text, re.I)
    if m_assunto:
        text = text[m_assunto.end():].strip()

    # Remove metadados em linha (data/edição/página/órgão) quando grudados no texto
    text = re.sub(r"\b\d{2}/\d{2}/\d{4}\s+\d+\s+\d+\s+Minist[eé]rio\b", "Ministério", text)

    # Heurística: corta antes do "miolo" normativo (quando dá)
    # Procuramos um início típico do corpo, tipo: "O ADVOGADO-GERAL...", "O PRESIDENTE...", "Resolve:", etc.
    body_markers = [
        r"\bO\s+[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ\s\-]{3,}?\b",  # "O ADVOGADO-GERAL..."
        r"\bRESOLVE\b",
        r"\bDECRETA\b",
        r"\bCONSIDERANDO\b",
        r"\bArt\.\s*\d+º?\b",
    ]
    cut_pos = None
    for pat in body_markers:
        m = re.search(pat, text)
        if m:
            cut_pos = m.start()
            break

    if cut_pos is not None and cut_pos > 0:
        text = text[cut_pos:].strip()

    # Evita retornar algo que ainda seja só metadado / título repetido
    bad_starts = (
        "Ministério",
        "PORTARIA",
        "LEI",
        "DECRETO",
        "RESOLUÇÃO",
        "DESPACHO",
        "ATO DECLARATÓRIO",
        "SOLUÇÃO DE CONSULTA",
        "Solução de Consulta",
        "Ato Declaratório",
    )
    if any(text.startswith(bs) for bs in bad_starts):
        # tenta pegar após a primeira frase/linha de título
        # (busca o primeiro ponto seguido de espaço)
        dot = text.find(". ")
        if 0 <= dot < 220:
            text = text[dot + 2 :].strip()

    # Limite e acabamento
    if len(text) > max_chars:
        text = text[:max_chars]
        if " " in text:
            text = text.rsplit(" ", 1)[0].strip()
        text += "..."

    # Muito curto geralmente é inútil
    if len(text) < 60:
        return ""

    return text

# ---------------------------------------------------------------------------
# Heurísticas de texto/link
# ---------------------------------------------------------------------------

def looks_like_menu(text: str) -> bool:
    """
    Heurística para identificar textos de links que parecem ser
    itens de menu/navegação (Última hora, Voltar ao topo, etc.)
    e não resultados de matérias.
    """
    BAD_ANCHOR_TEXTS = [
        "Última hora", "Ultima hora",
        "Últimas 24 horas", "Ultimas 24 horas",
        "Semana passada", "Mes passado", "Mês passado",
        "Ano passado", "Período Personalizado", "Periodo Personalizado",
        "Pesquisa avançada", "Pesquisa Avançada", "Pesquisa",
        "Verificação de autenticidade", "Voltar ao topo",
        "Portal", "Tutorial", "Termo de Uso",
        "Ir para o conteúdo", "Ir para o rodapé",
        "REPORTAR ERRO", "Diário Oficial da União",
    ]
    BAD_TEXT_PAT = re.compile(r"(últim|ultima|semana|m[eê]s|ano|per[ií]odo).*(\(\d+\))?$", re.I)
    t = (text or "").strip()
    if not t:
        return False
    if t in BAD_ANCHOR_TEXTS:
        return True
    if BAD_TEXT_PAT.search(t):
        return True
    return False


def absolutize(href: str) -> str:
    """
    Converte um href relativo em uma URL absoluta da Imprensa Nacional.
    Se já for http/https, apenas devolve a própria URL.
    """
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):

        return "https://www.in.gov.br" + href
    return "https://www.in.gov.br" + ("/" + href.lstrip("./"))


def ensure_quoted(s: str) -> str:
    """Garante que uma string esteja entre aspas duplas."""
    s = s.strip()
    if not (s.startswith('"') and s.endswith('"')):
        return f'"{s}"'
    return s


def strip_outer_quotes(s: str) -> str:
    """Remove aspas duplas no início/fim da string, se existirem."""
    s = s.strip()
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return s[1:-1]
    return s


# ---------------------------------------------------------------------------
# E-mail – layout tipo "jornal diário"
# ---------------------------------------------------------------------------

def _escape_html(t: str) -> str:
    """Escapa caracteres especiais para HTML."""
    return html.escape(t or "", quote=True)

def send_email(items: list[dict], cfg: dict) -> None:
    """
    Monta e envia o e-mail de informe com os atos encontrados.

    Layout texto (plain):

    Bom dia! Seguem as principais publicações fiscais/tributárias do DOU de 11/12/2025.
    Janela considerada: 10/12/2025 a 11/12/2025 | Período lógico: today

    ATO DECLARATÓRIO 256
    ATO DECLARATÓRIO EXECUTIVO DECEX/RJO Nº 256, de 10 de dezembro de 2025
    Resumo: [se disponível]
    Órgão: Min. Fazenda / RFB / Secretaria-Adjunta · DOU: 11/12/2025 · ver no DOU

    ...

    E-mail HTML segue estrutura similar, com negrito e quebras de linha.
    """

    def _extract_emails(element):
        import re as _re
        if not element:
            return []
        if isinstance(element, list):
            return [e.strip() for e in element if e and e.strip()]
        if isinstance(element, str):
            return [e.strip() for e in _re.split(r"[;,]", element) if e.strip()]
        return []

    def clean_summary(resumo: str | None) -> str:
        """
        Limpa resumos ruins vindos da IA.
        Se o resumo for inútil, devolve string vazia (e ele não aparece no e-mail).
        """
        if not resumo:
            return ""
        r = resumo.strip()
        if not r:
            return ""

        low = r.lower()
        # Heurísticas para lixo típico
        if "acesse o script" in low:
            return ""
        if "script:" in low:
            return ""
        if "compartilhe o conteudo da pagina" in low or "compartilhe o conteúdo da página" in low:
            return ""
        # Muito curto = provavelmente não é resumo útil
        if len(r) < 40:
            return ""

        return r

    # ----------------- Destinatários -----------------
    to_list = _extract_emails(cfg["email"].get("to")) or _extract_emails(os.getenv("MAIL_TO"))
    cc_list = _extract_emails(cfg["email"].get("cc")) or _extract_emails(os.getenv("MAIL_CC"))
    bcc_list = _extract_emails(cfg["email"].get("bcc")) or _extract_emails(os.getenv("MAIL_BCC"))

    from_addr = cfg["email"].get("from_") or os.getenv("MAIL_FROM")

    if not to_list or not from_addr:
        print("WARN: destinatarios (TO) ou remetente nao configurados; pulando envio.")
        return

    # Config SMTP (sempre pega das env vars)
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    if not all([host, port, user, pwd]):
        print("WARN: variaveis SMTP_* ausentes; pulando envio.")
        return

    # ----------------- Labels / cabeçalho -----------------
    period_label = cfg.get("search", {}).get("period_effective")
    days_window = cfg.get("search", {}).get("days_window")

    # Janela (apenas informativo)
    if days_window and days_window > 0:
        hoje = datetime.now(timezone(timedelta(hours=-3)))
        inicio = (hoje - timedelta(days=days_window)).strftime("%d/%m/%Y")
        fim = hoje.strftime("%d/%m/%Y")
        days_label = f"{inicio} a {fim}"
    else:
        days_label = "sem limite (qualquer período)"

    prefix = cfg.get("email", {}).get("subject_prefix", "[DOU]")
    hoje_str = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")
    subject = f"{prefix} Boletim diário – {hoje_str}"

    phrases = cfg.get("search", {}).get("phrases", [])
    crit_line = "; ".join(phrases) if phrases else "(frases não especificadas)"

    org_filters = (cfg.get("filters") or {}).get("orgao_keywords") or []
    org_filters = [o for o in org_filters if o]

    ai_enabled = bool((cfg.get("ai") or {}).get("summaries", {}).get("enabled"))

    # ----------------- TEXTO SIMPLES -----------------
    text_lines: list[str] = []
    text_lines.append(
        f"Bom dia! Seguem as principais publicações fiscais/tributárias do DOU de {hoje_str}."
    )
    text_lines.append(
        f"Janela considerada: {days_label} | Período lógico: {period_label}"
    )
    text_lines.append("")

    if not items:
        text_lines.append("Não foram encontradas publicações relevantes para os critérios atuais.")
    else:
        for it in items:
            titulo = (it.get("titulo") or "").strip()
            org = (it.get("orgao") or "").strip()
            data_pub = (it.get("data") or "").strip()
            url = (it.get("url") or "").strip()
            resumo_editorial = (it.get("resumo_editorial") or "").strip()
            resumo_ia = clean_summary((it.get("resumo_ia") or "").strip())
            snippet = extract_body_snippet(it.get("texto_bruto") or "", max_chars=320)


            # 1) Título completo (apenas uma vez)
            if titulo:
                text_lines.append(titulo)

            # 2) Resumo (prioridade: editorial -> IA -> trecho)
            if resumo_editorial:
                text_lines.append(f"Resumo: {resumo_editorial}")
            elif resumo_ia:
                text_lines.append(f"Resumo: {resumo_ia}")
            else:
                if snippet:
                    text_lines.append(f"Trecho: {snippet}")


            # 3) Linha curta (sem "Órgão:" e sem "DOU:")
            org_short = shorten_orgao(org) if org else ""
            footer_parts = []
            if org_short:
                footer_parts.append(org_short)
            if data_pub:
                footer_parts.append(data_pub)
            if url:
                footer_parts.append(f"ver no DOU ({url})")

            if footer_parts:
                text_lines.append(" · ".join(footer_parts))

            text_lines.append("")

    text_lines.append("—")
    text_lines.append(f"Critérios de busca: {crit_line}")
    if org_filters:
        text_lines.append("Filtros por órgão: " + "; ".join(org_filters))
    if ai_enabled:
        text_lines.append(
            "Resumos gerados automaticamente por IA. Sempre confira o texto oficial no DOU."
        )

    text_body = "\n".join(text_lines)

    # ----------------- HTML -----------------
    html_lines: list[str] = []
    html_lines.append(
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
    )
    html_lines.append('<div style="font-family:Arial,Helvetica,sans-serif">')

    html_lines.append(
        f"<p>Bom dia! Seguem as principais "
        f"<b>publicações fiscais/tributárias</b> do DOU de <b>{_escape_html(hoje_str)}</b>.</p>"
    )
    html_lines.append(
        f"<p style='font-size:12px;color:#555;'>"
        f"Janela considerada: {_escape_html(days_label)} "
        f"| Período lógico: {_escape_html(str(period_label))}</p>"
    )

    if not items:
        html_lines.append(
            "<p>Não foram encontradas publicações relevantes para os critérios atuais.</p>"
        )
    else:
        for it in items:
            titulo = (it.get("titulo") or "").strip()
            org = (it.get("orgao") or "").strip()
            data_pub = (it.get("data") or "").strip()
            url = (it.get("url") or "").strip()
            resumo_editorial = (it.get("resumo_editorial") or "").strip()
            resumo_ia = clean_summary((it.get("resumo_ia") or "").strip())
            snippet = extract_body_snippet(it.get("texto_bruto") or "", max_chars=320)

            org_short = shorten_orgao(org) if org else ""

            html_lines.append("<p style='margin-bottom:12px;'>")

            # 1) Título completo
            html_lines.append(f"<b>{_escape_html(titulo)}</b><br/>" if titulo else "")

            # 2) Resumo (prioridade: editorial -> IA -> trecho)
            if resumo_editorial:
                html_lines.append(
                    "<span style='font-size:13px;color:#000;'>"
                    f"<b>Resumo:</b> {_escape_html(resumo_editorial)}"
                    "</span><br/>"
                )
            elif resumo_ia:
                html_lines.append(
                    "<span style='font-size:13px;color:#000;'>"
                    f"<b>Resumo:</b> {_escape_html(resumo_ia)}"
                    "</span><br/>"
                )
            else:
                if snippet:
                    html_lines.append(
                        "<span style='font-size:13px;color:#000;'>"
                        f"<b>Trecho:</b> {_escape_html(snippet)}"
                        "</span><br/>"
                    )

            # 3) Linha curta (sem rótulos)
            footer_parts = []
            if org_short:
                footer_parts.append(_escape_html(org_short))
            if data_pub:
                footer_parts.append(_escape_html(data_pub))
            if url:
                footer_parts.append(
                    f"<a href='{_escape_html(url)}' target='_blank' rel='noopener'>ver no DOU</a>"
                )

            if footer_parts:
                html_lines.append(
                    "<span style='font-size:12px;color:#555;'>"
                    + " · ".join(footer_parts)
                    + "</span>"
                )

            html_lines.append("</p>")

    # Rodapé com critérios de busca e filtros por órgão
    html_lines.append(
        "<p style='font-size:12px;color:#777;'>"
        "Critérios de busca: "
        f"{_escape_html(crit_line)}"
        "</p>"
    )
    if org_filters:
        html_lines.append(
            "<p style='font-size:12px;color:#777;'>"
            "Filtros por órgão: "
            f"{_escape_html('; '.join(org_filters))}"
            "</p>"
        )
    if ai_enabled:
        html_lines.append(
            "<p style='font-size:11px;color:#999;'>"
            "Resumos gerados automaticamente por IA. "
            "Sempre confira o texto oficial no DOU."
            "</p>"
        )

    html_lines.append("</div>")
    html_body = "\n".join(html_lines)

    # ----------------- Envio -----------------
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    all_recipients = to_list + cc_list + bcc_list

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, pwd)
        server.sendmail(from_addr, all_recipients, msg.as_string())

    print(f"Email enviado para {', '.join(all_recipients)} com {len(items)} item(ns).")


# ---------------------------------------------------------------------------
# Scraping helpers – busca no DOU
# ---------------------------------------------------------------------------

def build_direct_query_url(phrase: str, period: str, section_code: str) -> str:
    """
    Monta a URL de busca direta no site do DOU (consulta/-/buscar/dou),
    combinando frase, período e seção.

    Observação:
    - Para "today" (edição do dia) usamos exactDate=dia.
    - Para outros períodos, mapeamos para semana/mês/all conforme o DOU.
    """
    period_map = {
        # edição do dia
        "today": "dia",
        "day": "dia",
        "dia": "dia",
        "hoje": "dia",
        "edicao": "dia",
        "edição": "dia",

        # última semana
        "week": "semana",
        "semana": "semana",

        # último mês
        "month": "mes",
        "mes": "mes",
        "mês": "mes",

        # qualquer período
        "any": "all",
        "all": "all",
        "qualquer": "all",
        "qualquer periodo": "all",
        "qualquer período": "all",
    }

    exact = period_map.get(period, "dia")

    # Monta a query (busca exata pela frase)
    core = strip_outer_quotes(phrase)
    q = '%22' + quote_plus(core) + '%22'

    s = section_code if section_code in {"do1", "do2", "do3", "todos"} else "do1"
    return (
        "https://www.in.gov.br/consulta/-/buscar/dou"
        f"?q={q}&s={s}&exactDate={exact}&sortType=0"
    )


async def deep_collect_anchors(page):
    """
    Fallback: coleta, via JS, todos os links <a href> da página,
    inclusive dentro de Shadow DOM.
    """
    js = """
    () => {
        const anchors = [];
        function collectFrom(root) {
            const as = root.querySelectorAll('a[href]');
            for (const a of as) {
                anchors.push([a.href, a.textContent || '']);
            }
            if (root.shadowRoot) {
                collectFrom(root.shadowRoot);
            }
            const shadowHosts = root.querySelectorAll('*');
            for (const el of shadowHosts) {
                if (el.shadowRoot) collectFrom(el.shadowRoot);
            }
        }
        collectFrom(document);
        return anchors;
    }
    """
    try:
        return await page.evaluate(js)
    except Exception:
        return []


async def wait_results(page, timeout_ms=20000):
    """
    Aguarda até que a página de resultados carregue:
    - Algum link típico de resultado (a.resultado-item-titulo, /web/dou/-/, etc.), ou
    - Uma mensagem de 'Nenhum resultado'.
    """
    loc_none = page.get_by_text("Nenhum resultado", exact=False)
    loc_candidates = [
        page.locator("a.resultado-item-titulo"),
        page.locator("a[href*='/web/dou/-/']"),
        page.locator("a[href*='/materia/']"),
    ]
    deadline = datetime.now() + timedelta(milliseconds=timeout_ms)
    while datetime.now() < deadline:
        try:
            if await loc_none.count() > 0:
                return
        except Exception:
            pass
        for loc in loc_candidates:
            try:
                if await loc.count() > 0:
                    return
            except Exception:
                continue
        await page.wait_for_timeout(500)
    return


def compile_accept_patterns(cfg: dict):
    """Compila as expressões regulares de URLs aceitáveis (filters.accept_url_patterns)."""
    pats = cfg.get("filters", {}).get("accept_url_patterns", [])
    compiled = []
    for p in pats:
        try:
            compiled.append(re.compile(p))
        except re.error:
            print(f"WARN: regex invalida em accept_url_patterns: {p!r}")
    return compiled


def should_reject_url(url: str, cfg: dict) -> bool:
    """Verifica se uma URL deve ser rejeitada com base em substrings (filters.reject_url_substrings)."""
    rej = cfg.get("filters", {}).get("reject_url_substrings", [])
    u = url.lower()
    for s in rej:
        if s.lower() in u:
            return True
    return False


def title_allowed(title: str, cfg: dict) -> bool:
    """
    Caso haja palavras-chave de título configuradas, só aceita resultados
    cujo título contenha pelo menos uma delas (case-insensitive).
    """
    kws = cfg.get("filters", {}).get("title_keywords")
    if not kws:
        return True
    t = (title or "").upper()
    for kw in kws:
        if (kw or "").upper() in t:
            return True
    return False


def orgao_allowed(orgao: str | None, cfg: dict) -> bool:
    """
    Filtro opcional por órgão, com base em filters.orgao_keywords.

    Retorna True se:
      - não houver orgao_keywords configurados, OU
      - o órgão da matéria contiver pelo menos uma das palavras-chave
        configuradas (comparação com normalização).
    """
    kws = cfg.get("filters", {}).get("orgao_keywords")
    if not kws:
        return True
    o = normalize(orgao or "")
    if not o:
        # Se não conseguimos identificar o órgão, preferimos manter o item.
        return True
    for kw in kws:
        if not kw:
            continue
        if normalize(kw) in o:
            return True
    return False


async def collect_links_from_listing(page, cfg: dict, broad: bool = True) -> list[dict]:
    """
    Varre a página de listagem de resultados e coleta links de matérias,
    aplicando filtros por URL e por título para reduzir ruído.
    Faz deduplicação e, em último caso, usa deep_collect_anchors como fallback.
    """
    links = {}
    discards = {"menu_like": 0, "rejected_url": 0, "title_keyword": 0, "pattern_miss": 0}
    accept_pats = compile_accept_patterns(cfg)

    async def add_candidate(href, text, reason="primary"):
        if not href:
            return
        url = absolutize(href)
        if looks_like_menu(text):
            discards["menu_like"] += 1
            return
        if should_reject_url(url, cfg):
            discards["rejected_url"] += 1
            return
        if not title_allowed(text, cfg):
            discards["title_keyword"] += 1
            return
        if accept_pats:
            if not any(p.search(url) for p in accept_pats):
                discards["pattern_miss"] += 1
                return
        if url not in links:
            links[url] = text or ""

    selectors = [
        "a.resultado-item-titulo",
        "a[href*='/web/dou/-/']",
        "a[href*='/materia/']",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                href = await el.get_attribute("href")
                text = (await el.text_content()) or ""
                await add_candidate(href, text, reason=f"sel:{sel}")
        except Exception:
            continue

    if not links and broad:
        for href, text in await deep_collect_anchors(page):
            await add_candidate(href, text, reason="shadow")

    items = [{"url": u, "titulo": t} for u, t in links.items()]
    print(f"[DEBUG] collect_links_from_listing -> {len(items)} link(s). Discards: {discards}")
    return items


def extract_materia_id(url: str) -> str | None:
    """Tenta extrair um ID numérico longo da URL da matéria, quando existe."""
    m = re.search(r"/-(?:[^/]+/)*(\d{6,})/?$", url)
    return m.group(1) if m else None


async def resolve_to_materia(page, url: str) -> str:
    """
    Garante que a URL final a ser usada seja de uma página de matéria do DOU
    (contendo /web/dou/-/ ou /materia/-/). Se a URL não for de matéria,
    abre a página e procura dentro dela um link de matéria para seguir.
    """
    if "/web/dou/-/" in url or "/materia/-/" in url:
        return url

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        return url

    sel = "a[href*='/web/dou/-/'], a[href*='/materia/']"
    try:
        loc = page.locator(sel)
        if await loc.count() > 0:
            href = await loc.first.get_attribute("href")
            if href:
                return absolutize(href)
    except Exception:
        pass
    return url


async def collect_paginated_results(page, cfg: dict, broad: bool, max_pages: int = 5) -> list[dict]:
    """
    Percorre várias páginas de resultados (paginação), acumulando links únicos.
    Para cada página, usa collect_links_from_listing e tenta avançar via
    botões 'Próximo' ou mecanismos equivalentes.
    """
    all_items = []
    seen_urls = set()
    page_idx = 0
    while page_idx < max_pages:
        await wait_results(page, timeout_ms=20000)
        items = await collect_links_from_listing(page, cfg, broad=broad)
        if not items:
            break
        added = 0
        for it in items:
            u = it["url"]
            if u not in seen_urls:
                seen_urls.add(u)
                all_items.append(it)
                added += 1
        print(f"[DEBUG] Página {page_idx+1}: {len(items)} itens, {added} novos (total acumulado: {len(all_items)}).")

        # Tenta avançar para a próxima página
        next_clicked = False
        for txt in ["Próximo", "Proximo", "»", ">"]:
            try:
                btn = page.get_by_text(txt, exact=False)
                if await btn.count() > 0:
                    await btn.first.click(timeout=1500)
                    next_clicked = True
                    break
            except Exception:
                continue

        if not next_clicked:
            # Fallback: scroll para ver se aparecem mais itens
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await page.wait_for_timeout(1000)
                more = await collect_links_from_listing(page, cfg, broad=False)
                print(f"[DEBUG] Fallback scroll infinito: {len(more) if more else 0} novos itens.")
                if not more:
                    break
                for it in more:
                    u = it["url"]
                    if u not in seen_urls:
                        seen_urls.add(u)
                        all_items.append(it)
                break
            except Exception:
                break

        page_idx += 1

    return all_items

def extract_clean_text(soup: BeautifulSoup) -> str:
    """
    Extrai texto útil da matéria do DOU, removendo menus, navegação e lixo
    típico do portal, para uso na IA (texto_bruto).
    """
    # Tenta identificar o container principal da matéria
    main = (
        soup.select_one("div#materia") or
        soup.select_one("article") or
        soup.select_one("div.materia") or
        soup.select_one("div.coluna-2") or
        soup.body
    )

    raw = main.get_text("\n", strip=True)
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    # Trechos típicos de navegação/lixo que queremos remover
    noise = [
        "Página Inicial",
        "Página inicial",
        "Atividades da Página inicial",
        "Atividades da página inicial",
        "Clique aqui para",
        "Acesse o site",
        "Voltar para a página inicial",
        "Reportar erro",
        "Menu",
        "Buscar:",
        "Conteúdo da Página",
        "Conteudo da Pagina",
        "Assinatura eletrônica",
        "Assinatura eletronica",
    ]

    clean = []
    for ln in lines:
        low = ln.lower()
        if any(n.lower() in low for n in noise):
            continue
        clean.append(ln)

    texto = "\n".join(clean).strip()

    # Se ficar pouco texto, não arrisca perder conteúdo: usa o bruto
    if len(texto) < 300:
        return raw.strip()

    return texto

async def enrich_listing_item(page, item: dict) -> dict:
    """
    Abre a página da matéria para extrair metadados adicionais:
    órgão, tipo de ato (Portaria, Decreto, etc.), número e data de publicação.
    Também devolve um 'texto_bruto' para uso pela IA.
    """
    final_url = await resolve_to_materia(page, item["url"])
    try:
        await page.goto(final_url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        # fallback: sem texto bruto
        return {
            "url": final_url,
            "titulo": item.get("titulo") or "(sem título)",
            "orgao": None,
            "tipo": None,
            "numero": None,
            "data": datetime.now().strftime("%d/%m/%Y"),
            "texto_bruto": "",
        }

    html_page = await page.content()
    soup = BeautifulSoup(html_page, "lxml")

    titulo = item.get("titulo") or (soup.title.get_text(strip=True) if soup.title else "")

    # órgão (opcional)
    orgao = None
    for sel in ['.orgao', '.row-orgao', '.info-orgao', 'section.orgao', 'header .orgao']:
        el = soup.select_one(sel)
        if el:
            orgao = el.get_text(" ", strip=True)
            break
    if not orgao:
        m = re.search(r"Órg[aã]o:\s*([^\n]+)", soup.get_text("\n", strip=True), re.I)
        if m:
            orgao = m.group(1).strip()

    # texto bruto principal para heurísticas (tudo em uma linha)
    raw_all = soup.get_text("\n", strip=True)
    head_txt = raw_all.replace("\n", " ")[:4000]

    # tipo/número (heurística)
    m_tipo = re.search(
        r"\b(Portaria|Instru[cç][aã]o Normativa|Decreto|Lei|Resolu[cç][aã]o|Despacho|Ato Declarat[óo]rio|Solu[cç][aã]o de Consulta)\b",
        head_txt,
        re.I,
    )
    tipo = m_tipo.group(1).upper() if m_tipo else None

    m_num = re.search(r"\bN[ºo\.]?\s*([\d\.]+(?:/\d{4})?)", head_txt, re.I)
    numero = m_num.group(1) if m_num else None

    # data de publicação
    data_pub = None
    for pat in [
        r"Publicado em[:\s]+(\d{2}/\d{2}/\d{4})",
        r"Edi[cç][aã]o de[:\s]+(\d{2}/\d{2}/\d{4})",
        r"Data de publica[cç][aã]o[:\s]+(\d{2}/\d{2}/\d{4})",
    ]:
        m = re.search(pat, head_txt, re.I)
        if m:
            data_pub = m.group(1)
            break
    if not data_pub:
        data_pub = datetime.now().strftime("%d/%m/%Y")

    # resumo editorial (quando existir)
    resumo_editorial = extract_editorial_summary(soup, max_chars=400)
    # texto limpo para IA (corpo da matéria, sem menus)
    clean_text = extract_clean_text(soup)
    # limita para não explodir a IA
    clean_text = clean_text[:4000]

    return {
        "url": final_url,
        "titulo": titulo or "(sem título)",
        "orgao": orgao,
        "tipo": tipo,
        "numero": numero,
        "data": data_pub,
        "texto_bruto": clean_text,
        "resumo_editorial": resumo_editorial,
    }
    
#------------------------------------------------------------
# Extrai o resumo editorial do DOU
#------------------------------------------------------------

def extract_editorial_summary(soup: BeautifulSoup, max_chars: int = 400) -> str:
    """
    Extrai o resumo editorial do DOU (quando existir), normalmente exibido logo
    abaixo do título da matéria, antes do corpo normativo.

    Heurísticas:
    - procura parágrafos curtos logo após o título;
    - descarta texto claramente normativo ou metalinguístico;
    - evita repetir o título;
    - retorna string vazia se não encontrar algo confiável.
    """
    if not soup:
        return ""

    # 1) Identifica o título principal
    title_el = (
        soup.find("h1") or
        soup.find("h2") or
        soup.select_one(".titulo") or
        soup.select_one(".titulo-principal")
    )

    if not title_el:
        return ""

    title_text = title_el.get_text(" ", strip=True)
    title_norm = normalize(title_text)

    # 2) Percorre elementos logo após o título
    candidates = []
    for el in title_el.find_all_next(["p", "div"], limit=8):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue

        # Normalizações básicas
        txt_clean = re.sub(r"\s+", " ", txt).strip()
        low = txt_clean.lower()

        # 3) Filtros de descarte (normativo / lixo)
        if any(
            low.startswith(prefix)
            for prefix in (
                "art.", "artigo", "resolve", "decreta", "considerando",
                "o ministro", "o presidente", "o advogado-geral",
                "o auditor", "o secretário", "o diretor",
            )
        ):
            break  # a partir daqui já entrou no corpo normativo

        if any(
            kw in low
            for kw in (
                "diário oficial da união",
                "edição nº",
                "seção",
                "página",
                "brasão do brasil",
                "publicado em",
            )
        ):
            continue

        # Evita repetir o título
        if normalize(txt_clean) == title_norm:
            continue

        # Tamanho razoável para resumo editorial
        if len(txt_clean) < 40 or len(txt_clean) > 600:
            continue

        candidates.append(txt_clean)

        # geralmente o primeiro bom já é suficiente
        if len(candidates) >= 2:
            break

    if not candidates:
        return ""

    summary = candidates[0]

    # 4) Limite final e acabamento
    if len(summary) > max_chars:
        summary = summary[:max_chars]
        if " " in summary:
            summary = summary.rsplit(" ", 1)[0].strip()
        summary += "..."

    # Garante pontuação final
    if not summary.endswith((".", "!", "?", ";")):
        summary += "."

    return summary

# ---------------------------------------------------------------------------
# Ordenação / dedupe helpers
# ---------------------------------------------------------------------------

def _parse_br_date(s: str) -> datetime:
    """Converte data DD/MM/AAAA em datetime; em erro, devolve 01/01/1970."""
    try:
        return datetime.strptime(s, "%d/%m/%Y")
    except Exception:
        return datetime(1970, 1, 1)


def build_seen_keys(url: str):
    """
    A partir da URL da matéria, gera duas chaves possíveis para o seen.json:
    - 'url:<url>'  (sempre)
    - 'id:<id>'    (se for possível extrair o ID numérico).
    """
    url_key = f"url:{url}"
    mid = extract_materia_id(url)
    id_key = f"id:{mid}" if mid else None
    return url_key, id_key


# ---------------------------------------------------------------------------
# Query principal (busca no DOU)
# ---------------------------------------------------------------------------

@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
async def query_dou(page, cfg: dict, phrases: list[str]) -> list[dict]:
    """
    Executa a busca principal no DOU combinando frases e seções.

    Define:
    - período lógico (today/week/month/any), com override via PERIOD_OVERRIDE;
    - days_window (para label);
    - seções a partir de search.sections ou section_label.

    Usa apenas a busca direta por URL (consulta/-/buscar/dou).
    """
    # 1) Período efetivo:
    period = (
        os.getenv("PERIOD_OVERRIDE")
        or cfg.get("search", {}).get("period", "today")
    ).strip().lower()

    # 2) "days" é só informativo pro texto do e-mail
    if period in {"today", "day", "dia", "hoje", "edicao", "edição"}:
        days = 1
    elif period in {"week", "semana"}:
        days = 7
    elif period in {"month", "mes", "mês"}:
        days = 30
    elif period in {"any", "all", "qualquer", "qualquer periodo", "qualquer período"}:
        days = 0
    else:
        days = 1  # fallback

    override = os.getenv("DAYS_WINDOW_OVERRIDE")
    if override and override.isdigit():
        days = int(override)

    cfg["search"]["days_window"] = days
    cfg["search"]["period_effective"] = period

    # Seções a consultar
    sections = cfg.get("search", {}).get("sections")
    if not sections:
        lbl = normalize(cfg.get("search", {}).get("section_label", "seção 1"))
        if "seção 1" in lbl or "secao 1" in lbl:
            sections = ["do1"]
        elif "seção 2" in lbl or "secao 2" in lbl:
            sections = ["do2"]
        elif "seção 3" in lbl or "secao 3" in lbl:
            sections = ["do3"]
        elif "todos" in lbl:
            sections = ["todos"]
        else:
            sections = ["do1"]

    max_pages = int(cfg.get("pagination", {}).get("max_pages", 5))
    all_results = set()

    # Busca direta via URL montada
    for phrase in phrases:
        for sec in sections:
            direct_url = build_direct_query_url(phrase, period, sec)
            print(f"[DEBUG] Direct URL: {direct_url}")
            try:
                await page.goto(direct_url, wait_until="networkidle", timeout=45000)
            except Exception as e:
                print(f"[WARN] Falha ao carregar URL direta: {e}")
                continue

            await wait_results(page, timeout_ms=20000)
            items = await collect_paginated_results(page, cfg, broad=True, max_pages=max_pages)

            if not items:
                # Salva HTML para debug
                try:
                    content = await page.content()
                    artifacts_dir = ROOT / "artifacts"
                    artifacts_dir.mkdir(parents=True, exist_ok=True)
                    safe_phrase = re.sub(r"[^0-9a-zA-Z_-]+", "_", normalize(phrase))[:40]
                    fname = artifacts_dir / f"listing_direct_{sec}_{safe_phrase}.html"
                    with open(fname, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"[DEBUG] Nenhum item via URL direta; HTML salvo em {fname}")
                except Exception as e:
                    print(f"[WARN] Falha ao salvar HTML de debug: {e}")
            else:
                for it in items:
                    all_results.add((it["url"], it.get("titulo") or ""))

    listing = [{"url": u, "titulo": t} for (u, t) in all_results]
    print(f"[DEBUG] query_dou -> {len(listing)} itens únicos (via URL direta).")
    return listing


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

async def run() -> None:
    """
    Pipeline principal do robô:
    - Carrega config.yml e o seen.json
    - Abre navegador headless com Playwright
    - Executa a query no DOU
    - Enriquecimento de cada item (órgão, tipo, número, data, texto_bruto)
    - Filtra itens já vistos
    - Se período for 'today', mantém apenas a edição do dia
    - Filtro opcional por órgão
    - (Opcional) Gera resumos com IA
    - Ordena, envia e-mail e atualiza seen.json
    """
    cfg = load_config()
    if not isinstance(cfg, dict):
        raise RuntimeError("config.yml invalido ou vazio. Garanta as chaves 'search' e 'email'.")

    seen = load_seen()
    enrich = bool(cfg.get("search", {}).get("enrich_listing", True))
    phrases = cfg.get("search", {}).get("phrases", [])

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        context = await browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        listing = await query_dou(page, cfg, phrases)
        if not listing:
            print("Nenhuma publicação encontrada para os critérios configurados.")
            if str(os.getenv("FORCE_TEST_EMAIL", "")).lower() in {"1", "true", "yes"}:
                test_item = {
                    "url": "https://www.in.gov.br",
                    "titulo": "E-mail de teste do robô do DOU (sem resultados reais).",
                    "orgao": None,
                    "tipo": "Aviso",
                    "numero": "",
                    "data": datetime.now().strftime("%d/%m/%Y"),
                    "texto_bruto": "",
                }
                send_email([test_item], cfg)
                print("E-mail de teste enviado (FORCE_TEST_EMAIL).")
            await context.close()
            await browser.close()
            return

        relevant = []
        for it in listing:
            if enrich:
                v = await enrich_listing_item(page, it)
            else:
                v = {
                    "url": it["url"],
                    "titulo": it.get("titulo") or "(sem título)",
                    "orgao": None,
                    "tipo": None,
                    "numero": None,
                    "data": datetime.now().strftime("%d/%m/%Y"),
                    "texto_bruto": "",
                }

            key_url = v["url"]
            url_key, id_key = build_seen_keys(key_url)

            # Compatibilidade com histórico
            if (key_url in seen) or (url_key in seen) or (id_key and id_key in seen):
                continue

            relevant.append(v)

        await context.close()
        await browser.close()

    # ---- filtro EDIÇÃO DO DIA ----
    period_eff = cfg.get("search", {}).get("period_effective")
    if period_eff in {"today", "day", "dia", "hoje", "edicao", "edição"}:
        today_br = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")
        before = len(relevant)
        relevant = [r for r in relevant if (r.get("data") or "").strip() == today_br]
        print(f"[DEBUG] Filtro edição do dia {today_br}: {before} -> {len(relevant)} item(ns).")

    # ---- filtro opcional por órgão ----
    if cfg.get("filters", {}).get("orgao_keywords"):
        antes = len(relevant)
        relevant = [r for r in relevant if orgao_allowed(r.get("orgao"), cfg)]
        print(f"[DEBUG] Filtro por órgão: {antes} -> {len(relevant)} item(ns) após aplicar orgao_keywords")

    # ---- ordenar por data desc (e por título para estabilizar) ----
    def _sort_key(r):
        return (_parse_br_date(r.get("data")), (r.get("titulo") or ""))

    relevant.sort(key=_sort_key, reverse=True)

    # ---- IA: gerar resumos das matérias, se habilitado ----
    ai_cfg = (cfg.get("ai") or {}).get("summaries") or {}
    if ai_cfg.get("enabled"):
        for r in relevant:
            if r.get("resumo_ia"):
                continue
            raw = (r.get("texto_bruto") or "").strip()
            if not raw:
                continue

            titulo_dbg = (r.get("titulo") or "")[:80]
            logger.info("[IA] Gerando resumo para: %r", titulo_dbg)
            # DEBUG: inspecionar o que está indo para a IA
            logger.info(
                "[IA-DEBUG] Texto_bruto (%s) [len=%d]: %.500r",
                titulo_dbg,
                len(raw),
                raw[:300],
            )

            resumo = generate_summary_ia(raw, cfg)
            if resumo:
                r["resumo_ia"] = resumo
                logger.info("[IA] Resumo aplicado em: %r", titulo_dbg)
            # Pequena pausa para ser gentil com a API
            time.sleep(1)

    if relevant:
        send_email(relevant, cfg)
        for r in relevant:
            url_key, id_key = build_seen_keys(r["url"])
            seen.add(url_key)
            if id_key:
                seen.add(id_key)
        save_seen(seen)
        print(f"{len(relevant)} item(ns) novos registrados no seen.json.")
    else:
        print("Sem novidades para enviar.")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(130)
