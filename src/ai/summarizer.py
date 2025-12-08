# Resumos com IA
"""
Sumarizador de conteúdo DOU usando IA.
"""
import os
import re
import asyncio
import logging
from typing import Optional, Dict, Any
from tenacity import retry, wait_exponential, stop_after_attempt
from models.publication import AIConfig


logger = logging.getLogger(__name__)


class Summarizer:
    """Sumarizador de conteúdo usando diferentes provedores de IA."""
    
    def __init__(self, config: AIConfig):
        """
        Inicializa o sumarizador.
        
        Args:
            config: Configuração de IA
        """
        self.config = config
        self.provider = self._select_provider()
        
        logger.info(
            f"Sumarizador inicializado: {self.provider.__class__.__name__} "
            f"(modelo: {config.model})"
        )
    
    def _select_provider(self):
        """Seleciona o provedor de IA baseado na configuração."""
        # Prioridade: Google Gemini > Hugging Face > Fallback
        if self._can_use_gemini():
            return GeminiProvider(self.config)
        elif self._can_use_huggingface():
            return HuggingFaceProvider(self.config)
        else:
            return FallbackProvider(self.config)
    
    def _can_use_gemini(self) -> bool:
        """Verifica se pode usar Google Gemini."""
        api_key = os.getenv('GEMINI_API_KEY')
        return bool(api_key)
    
    def _can_use_huggingface(self) -> bool:
        """Verifica se pode usar Hugging Face."""
        api_token = os.getenv('HF_TOKEN')
        return bool(api_token)
    
    async def summarize(
        self,
        text: str,
        metadata: Dict[str, Any],
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Gera um resumo do texto usando IA.
        
        Args:
            text: Texto para resumir
            metadata: Metadados da publicação
            max_retries: Número máximo de tentativas
        
        Returns:
            Resumo gerado ou None
        """
        if not self.config.enabled:
            logger.debug("Sumarização desabilitada na configuração")
            return None
        
        if not text or len(text.strip()) < 100:
            logger.debug("Texto muito curto para sumarização")
            return None
        
        # Limitar tamanho do texto
        text = text[:self.config.max_chars_input]
        
        # Pré-processar texto
        text = self._preprocess_text(text)
        
        if len(text) < 50:
            logger.debug("Texto insuficiente após pré-processamento")
            return None
        
        try:
            summary = await self.provider.summarize(text, metadata)
            
            if summary:
                # Pós-processar resumo
                summary = self._postprocess_summary(summary, metadata)
                
                if self._is_useful_summary(summary):
                    logger.debug(f"Resumo gerado ({len(summary)} caracteres)")
                    return summary
                else:
                    logger.debug("Resumo considerado não útil")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Erro na sumarização: {e}")
            return None
    
    def _preprocess_text(self, text: str) -> str:
        """
        Pré-processa o texto para a IA.
        
        Args:
            text: Texto original
        
        Returns:
            Texto pré-processado
        """
        if not text:
            return ""
        
        # Remover múltiplos espaços e quebras de linha
        text = re.sub(r'\s+', ' ', text)
        
        # Remover textos de sistema comuns
        junk_patterns = [
            r'ACESSE O SCRIPT.*?\n',
            r'Compartilhe o conteúdo.*?\n',
            r'Voltar ao topo.*?\n',
            r'Portal da Imprensa.*?\n',
            r'Este conteúdo não substitui.*?\n',
            r'Diário Oficial da União.*?\n',
            r'Publicado em:.*?\n',
            r'Edição:.*?\n',
            r'Seção:.*?\n',
            r'Página:.*?\n',
            r'Órgão:.*?\n',
        ]
        
        for pattern in junk_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remover URLs
        text = re.sub(r'https?://\S+', '', text)
        
        # Garantir que temos texto suficiente
        text = text.strip()
        
        return text
    
    def _postprocess_summary(self, summary: str, metadata: Dict[str, Any]) -> str:
        """
        Pós-processa o resumo gerado.
        
        Args:
            summary: Resumo bruto
            metadata: Metadados da publicação
        
        Returns:
            Resumo processado
        """
        if not summary:
            return ""
        
        summary = summary.strip()
        
        # Remover marcações de IA
        summary = re.sub(r'^Resumo:\s*', '', summary, flags=re.IGNORECASE)
        summary = re.sub(r'^Aqui está.*?:', '', summary, flags=re.IGNORECASE)
        summary = re.sub(r'^Com base.*?:', '', summary, flags=re.IGNORECASE)
        
        # Remover frases de sistema que podem ter sido geradas
        junk_phrases = [
            'acesse o script',
            'compartilhe o conteúdo',
            'clique aqui para',
            'para mais informações',
            'consulte o texto completo',
            'leia a matéria completa',
            'veja também',
            'para saber mais'
        ]
        
        for phrase in junk_phrases:
            if phrase in summary.lower():
                summary = re.sub(
                    f'.*{re.escape(phrase)}.*',
                    '',
                    summary,
                    flags=re.IGNORECASE
                )
        
        # Formatar com quebras de linha apropriadas
        summary = re.sub(r'([.!?])\s+', r'\1\n\n', summary)
        summary = re.sub(r'\n{3,}', '\n\n', summary)
        
        # Garantir que termina com ponto
        if summary and not summary.endswith(('.', '!', '?')):
            summary = summary.rstrip('.') + '.'
        
        # Limitar tamanho
        max_length = 300  # Caracteres para resumo
        if len(summary) > max_length:
            summary = summary[:max_length].rsplit(' ', 1)[0] + '...'
        
        return summary.strip()
    
    def _is_useful_summary(self, summary: str) -> bool:
        """
        Verifica se o resumo é útil.
        
        Args:
            summary: Resumo a verificar
        
        Returns:
            True se o resumo for útil
        """
        if not summary or len(summary) < 30:
            return False
        
        # Verificar se não é apenas repetição de palavras
        words = summary.lower().split()
        unique_words = set(words)
        
        if len(unique_words) < 5:
            return False
        
        # Verificar se contém palavras significativas
        significant_words = ['lei', 'portaria', 'decreto', 'instrução', 
                           'resolução', 'altera', 'estabelece', 'dispõe',
                           'tribut', 'fiscal', 'imposto', 'receita']
        
        if not any(word in summary.lower() for word in significant_words):
            # Pode ainda ser útil, mas verificamos mais critérios
            if len(summary) < 50:
                return False
        
        return True


class BaseProvider:
    """Classe base para provedores de IA."""
    
    def __init__(self, config: AIConfig):
        self.config = config
    
    async def summarize(self, text: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Método a ser implementado por provedores específicos."""
        raise NotImplementedError


class GeminiProvider(BaseProvider):
    """Provedor usando Google Gemini API."""
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
        self.client = self._initialize_client()
    
    def _initialize_client(self):
        """Inicializa o cliente Gemini."""
        try:
            import google.generativeai as genai
            
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY não configurada")
            
            genai.configure(api_key=api_key)
            
            # Usar modelo configurado ou default
            model_name = self.config.model if 'gemini' in self.config.model.lower() else 'gemini-1.5-flash'
            
            return genai.GenerativeModel(model_name)
            
        except ImportError:
            logger.error("google-generativeai não instalado")
            raise
        except Exception as e:
            logger.error(f"Erro ao inicializar Gemini: {e}")
            raise
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3)
    )
    async def summarize(self, text: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Gera resumo usando Gemini."""
        try:
            prompt = self._create_prompt(text, metadata)
            
            # Executar de forma assíncrona
            response = await asyncio.to_thread(
                self.client.generate_content,
                prompt,
                generation_config={
                    'max_output_tokens': 300,
                    'temperature': 0.2,
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            
            if response and response.text:
                return response.text.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Erro no Gemini: {e}")
            raise
    
    def _create_prompt(self, text: str, metadata: Dict[str, Any]) -> str:
        """Cria prompt especializado para Gemini."""
        tipo = metadata.get('tipo', 'Norma')
        numero = metadata.get('numero', '')
        orgao = metadata.get('orgao', 'Órgão não especificado')
        
        return f"""
        Você é um especialista em legislação fiscal/tributária analisando publicações do DOU.
        
        PUBLICAÇÃO: {tipo} {numero} - Emitido por: {orgao}
        
        TEXTO DA PUBLICAÇÃO:
        {text[:2500]}
        
        ---
        
        INSTRUÇÕES PARA O RESUMO:
        
        1. FOCO EM ASPECTOS FISCAIS/TRIBUTÁRIOS:
           - Identifique alterações em leis tributárias
           - Destaque impactos para empresas/contribuintes
           - Mencione prazos, alíquotas, valores importantes
        
        2. ESTRUTURA DO RESUMO (máximo 150 palavras):
           - Linha 1: Tipo e número da norma + descrição breve
           - Linha 2-4: Principais pontos relevantes para contabilidade/tributação
           - Linha final: Vigência e órgão responsável
        
        3. FORMATAÇÃO:
           - Use linguagem clara e objetiva
           - Destaque valores numéricos importantes
           - Use marcadores (•) para pontos-chave
           - Mantenha em português do Brasil
        
        4. EVITE:
           - Menções a "acesse o script" ou elementos do portal
           - Opiniões pessoais ou julgamentos
           - Repetição excessiva
        
        Gere APENAS o resumo, sem introduções ou explicações adicionais.
        """
class HuggingFaceProvider(BaseProvider):
    """Provedor usando Hugging Face Inference API."""
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
        self.client = self._initialize_client()
    
    def _initialize_client(self):
        """Inicializa o cliente Hugging Face."""
        try:
            from huggingface_hub import InferenceClient
            
            token = os.getenv('HF_TOKEN')
            if not token:
                raise ValueError("HF_TOKEN não configurada")
            
            return InferenceClient(
                model=self.config.model,
                token=token
            )
            
        except ImportError:
            logger.error("huggingface_hub não instalado")
            raise
        except Exception as e:
            logger.error(f"Erro ao inicializar Hugging Face: {e}")
            raise
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3)
    )
    async def summarize(self, text: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Gera resumo usando Hugging Face."""
        try:
            prompt = self._create_prompt(text, metadata)
            
            # Executar de forma assíncrona
            response = await asyncio.to_thread(
                self.client.text_generation,
                prompt,
                max_new_tokens=200,
                temperature=0.3,
                do_sample=True,
                return_full_text=False
            )
            
            if response:
                return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Erro no Hugging Face: {e}")
            raise
    
    def _create_prompt(self, text: str, metadata: Dict[str, Any]) -> str:
        """Cria prompt especializado para Hugging Face."""
        tipo = metadata.get('tipo', 'Norma')
        numero = metadata.get('numero', '')
        
        return f"""
        Resuma esta publicação do DOU focando em aspectos fiscais/tributários:

        {text[:2000]}

        Resumo conciso (máximo 100 palavras) destacando:
        1. Tipo de ato ({tipo} {numero})
        2. Principais pontos fiscais/tributários
        3. Prazos ou valores relevantes
        4. Impacto prático

        Resumo:
        """


class FallbackProvider(BaseProvider):
    """Provedor de fallback (regras baseadas)."""
    
    async def summarize(self, text: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Gera resumo usando regras baseadas (fallback)."""
        try:
            tipo = metadata.get('tipo', '')
            numero = metadata.get('numero', '')
            orgao = metadata.get('orgao', '')
            
            # Extrair primeiras sentenças
            sentences = re.split(r'[.!?]+', text)
            first_sentences = [s.strip() for s in sentences[:3] if s.strip()]
            
            # Encontrar palavras-chave fiscais
            fiscal_keywords = [
                'tribut', 'imposto', 'fiscal', 'receita', 'alíquota',
                'isenção', 'dedução', 'crédito', 'obrigação', 'declaração',
                'IRPJ', 'CSLL', 'PIS', 'COFINS', 'ICMS', 'IPI'
            ]
            
            relevant_parts = []
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in fiscal_keywords):
                    if len(sentence) > 20 and len(sentence) < 150:
                        relevant_parts.append(sentence)
            
            # Construir resumo
            summary_parts = []
            
            if tipo and numero:
                summary_parts.append(f"{tipo} {numero}")
            elif tipo:
                summary_parts.append(tipo)
            
            if first_sentences:
                summary_parts.append(first_sentences[0])
            
            if relevant_parts:
                summary_parts.extend(relevant_parts[:2])
            
            if orgao:
                summary_parts.append(f"Órgão: {orgao}")
            
            if summary_parts:
                summary = ' '.join(summary_parts)
                # Limitar tamanho
                if len(summary) > 250:
                    summary = summary[:250].rsplit(' ', 1)[0] + '...'
                return summary
            
            return None
            
        except Exception as e:
            logger.error(f"Erro no fallback: {e}")
            return None


class SummaryValidator:
    """Validador de resumos gerados."""
    
    @staticmethod
    def validate(summary: str, original_text: str) -> bool:
        """
        Valida se um resumo é de qualidade aceitável.
        
        Args:
            summary: Resumo gerado
            original_text: Texto original
        
        Returns:
            True se o resumo for válido
        """
        if not summary or len(summary) < 30:
            return False
        
        # Verificar se não é cópia excessiva
        summary_words = set(summary.lower().split())
        original_words = set(original_text.lower().split()[:100])
        
        overlap = len(summary_words.intersection(original_words))
        overlap_ratio = overlap / len(summary_words) if summary_words else 0
        
        if overlap_ratio > 0.8:  # Muito similar ao original
            return False
        
        # Verificar estrutura mínima
        sentences = re.split(r'[.!?]+', summary)
        if len(sentences) < 2:
            return False
        
        return True
    
    @staticmethod
    def extract_key_phrases(summary: str) -> list:
        """Extrai frases-chave do resumo."""
        if not summary:
            return []
        
        # Remover conectores comuns
        connectors = ['e', 'ou', 'mas', 'porém', 'entretanto', 'contudo',
                     'portanto', 'assim', 'dessa forma', 'além disso']
        
        phrases = re.split(r'[,;]', summary)
        key_phrases = []
        
        for phrase in phrases:
            phrase = phrase.strip()
            words = phrase.split()
            
            if (len(phrase) > 10 and 
                len(words) > 2 and 
                words[0].lower() not in connectors):
                
                # Garantir que termina com ponto se for sentença completa
                if phrase and not phrase.endswith(('.', '!', '?')):
                    phrase = phrase + '.'
                
                key_phrases.append(phrase)
        
        return key_phrases[:3]  # Retornar até 3 frases-chave
