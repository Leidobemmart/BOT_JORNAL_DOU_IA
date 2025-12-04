# Prompts especializados
"""
Prompts especializados para diferentes tipos de publicações DOU.
"""

class PromptFactory:
    """Fábrica de prompts especializados por tipo de publicação."""
    
    @staticmethod
    def get_prompt(pub_type: str, text: str, metadata: dict) -> str:
        """
        Retorna prompt especializado para o tipo de publicação.
        
        Args:
            pub_type: Tipo da publicação (LEI, PORTARIA, etc.)
            text: Texto da publicação
            metadata: Metadados
        
        Returns:
            Prompt especializado
        """
        pub_type = (pub_type or '').upper()
        
        if 'LEI' in pub_type:
            return PromptFactory._law_prompt(text, metadata)
        elif 'PORTARIA' in pub_type:
            return PromptFactory._portaria_prompt(text, metadata)
        elif 'DECRETO' in pub_type:
            return PromptFactory._decreto_prompt(text, metadata)
        elif 'INSTRUÇÃO NORMATIVA' in pub_type or 'INSTRUCAO NORMATIVA' in pub_type:
            return PromptFactory._instrucao_normativa_prompt(text, metadata)
        elif 'RESOLUÇÃO' in pub_type or 'RESOLUCAO' in pub_type:
            return PromptFactory._resolucao_prompt(text, metadata)
        elif 'ATO DECLARATÓRIO' in pub_type or 'ATO DECLARATORIO' in pub_type:
            return PromptFactory._ato_declaratorio_prompt(text, metadata)
        elif 'SOLUÇÃO DE CONSULTA' in pub_type or 'SOLUCAO DE CONSULTA' in pub_type:
            return PromptFactory._solucao_consulta_prompt(text, metadata)
        else:
            return PromptFactory._generic_prompt(text, metadata)
    
    @staticmethod
    def _law_prompt(text: str, metadata: dict) -> str:
        """Prompt especializado para Leis."""
        numero = metadata.get('numero', '')
        orgao = metadata.get('orgao', '')
        
        return f"""
        ANALISE ESTA LEI DO DOU COM FOCO EM ASPECTOS FISCAIS/TRIBUTÁRIOS:

        LEI {numero} - {orgao}

        TEXTO (trecho):
        {text[:2000]}

        ---

        GERE UM RESUMO ESPECIALIZADO PARA CONTADORES/TRIBUTARISTAS:

        ESTRUTURA:
        1. IDENTIFICAÇÃO: "Lei {numero} - [Título resumido]"
        2. OBJETO: O que a lei altera/cria em termos tributários
        3. PRINCIPAIS PONTOS FISCAIS (use marcadores •):
           • Alterações em alíquotas, bases de cálculo, prazos
           • Novas obrigações acessórias ou benefícios fiscais
           • Impacto para empresas (lucro real/presumido, Simples Nacional)
        4. VIGÊNCIA: Quando passa a valer
        5. ÓRGÃO RESPONSÁVEL: {orgao}

        REGRAS:
        - Máximo 150 palavras
        - Linguagem técnica mas acessível
        - Destaque valores percentuais e prazos
        - Mencione leis alteradas (ex: "Altera a Lei 9.250/1995")
        - Foco em consequências práticas para contabilidade

        RESULTADO (apenas o resumo):
        """
    
    @staticmethod
    def _portaria_prompt(text: str, metadata: dict) -> str:
        """Prompt especializado para Portarias."""
        numero = metadata.get('numero', '')
        orgao = metadata.get('orgao', '')
        
        return f"""
        ANALISE ESTA PORTARIA DO DOU COM FOCO EM ASPECTOS FISCAIS:

        PORTARIA {numero} - {orgao}

        TEXTO (trecho):
        {text[:1800]}

        ---

        RESUMO PARA ÁREA FISCAL:

        FORMATO:
        Portaria {numero} - [Finalidade breve]

        Principais disposições:
        • [Regulamentação de procedimento fiscal]
        • [Alteração de formulário ou obrigação]
        • [Prazos para cumprimento]

        Aplicação: [Para quem se aplica]
        Vigência: [Data de início]
        Órgão: {orgao}

        INSTRUÇÕES:
        - Foque em mudanças processuais ou regulatórias
        - Destaque prazos e formulários afetados
        - Mencione impactos no SPED, EFD, DCTF
        - Seja prático e direto
        - Máximo 120 palavras

        RESPOSTA:
        """
    
    @staticmethod
    def _instrucao_normativa_prompt(text: str, metadata: dict) -> str:
        """Prompt especializado para Instruções Normativas."""
        numero = metadata.get('numero', '')
        orgao = metadata.get('orgao', '')
        
        return f"""
        ANALISE ESTA INSTRUÇÃO NORMATIVA DA RECEITA FEDERAL:

        INSTRUÇÃO NORMATIVA {numero} - {orgao}

        CONTEÚDO:
        {text[:2000]}

        ---

        RESUMO TÉCNICO PARA FISCAL/TRIBUTÁRIO:

        ESTRUTURA:
        Instrução Normativa RFB {numero}

        Objetivo: [Finalidade da norma]

        Alterações relevantes:
        1. [Mudança em procedimento fiscal]
        2. [Novo requisito para declarações]
        3. [Atualização de valores ou índices]

        Impactos práticos:
        • Para empresas do regime [especificar se aplicável]
        • Nos sistemas: [SPED, ECD, ECF, DCTF]
        • Prazos para adequação

        Vigência: [Data]
        Referência: [Leis/portarias relacionadas]

        DIRETRIZES:
        - Específico para área fiscal
        - Mencione números de artigos importantes
        - Destaque o que muda na prática
        - Limite: 130 palavras

        GERAR APENAS O RESUMO:
        """
    
    @staticmethod
    def _resolucao_prompt(text: str, metadata: dict) -> str:
        """Prompt especializado para Resoluções."""
        numero = metadata.get('numero', '')
        orgao = metadata.get('orgao', '')
        
        return f"""
        ANALISE ESTA RESOLUÇÃO COM FOCO EM NORMAS CONTÁBEIS/TRIBUTÁRIAS:

        RESOLUÇÃO {numero} - {orgao}

        TEXTO:
        {text[:1800]}

        ---

        RESUMO PARA CONTABILIDADE/TRIBUTAÇÃO:

        Formato:
        Resolução {numero} - [Entidade emissora: COSIT, CNEP, etc.]

        Matéria: [Assunto principal]

        Determinações relevantes:
        • [Tratamento contábil/tributário]
        • [Interpretação de legislação]
        • [Procedimentos a serem adotados]

        Aplicação: [Setor/atividade afetada]
        Base legal: [Leis/regulamentos referenciados]
        Efeitos: [Consequências práticas]

        ESPECIFICAÇÕES:
        - Destaque se trata de solução de dúvida ou nova regulamentação
        - Mencione impactos no LALUR, ECF, ECD
        - Incluir referências a pronunciamentos CPC se aplicável
        - Máximo 140 palavras

        SAÍDA:
        """
    
    @staticmethod
    def _ato_declaratorio_prompt(text: str, metadata: dict) -> str:
        """Prompt especializado para Atos Declaratórios."""
        numero = metadata.get('numero', '')
        orgao = metadata.get('orgao', '')
        
        return f"""
        ANALISE ESTE ATO DECLARATÓRIO DA RECEITA FEDERAL:

        ATO DECLARATÓRIO {numero} - {orgao}

        CONTEÚDO:
        {text[:1500]}

        ---

        RESUMO PARA ORIENTAÇÃO FISCAL:

        Estrutura:
        Ato Declaratório {numero} - [Carf/Cosit]

        Questão: [Dúvida ou matéria tratada]

        Posicionamento oficial:
        • [Interpretação adotada]
        • [Fundamentação jurídica]
        • [Condições para aplicação]

        Efeitos:
        - [Impacto em casos similares]
        - [Orientações para contabilização]
        - [Reflexos tributários]

        Vigência: [Data/publicação]
        Revogações: [Se aplicável]

        INSTRUÇÕES:
        - Foco na solução da controvérsia tributária
        - Destaque se favorável ou desfavorável ao contribuinte
        - Mencione setores/atividades afetados
        - Limite: 110 palavras
        - Linguagem técnica objetiva

        GERAR:
        """
    
    @staticmethod
    def _solucao_consulta_prompt(text: str, metadata: dict) -> str:
        """Prompt especializado para Soluções de Consulta."""
        numero = metadata.get('numero', '')
        orgao = metadata.get('orgao', '')
        
        return f"""
        ANALISE ESTA SOLUÇÃO DE CONSULTA TRIBUTÁRIA:

        SOLUÇÃO DE CONSULTA {numero} - {orgao}

        TEXTO:
        {text[:2000]}

        ---

        RESUMO PARA CONSULTORIA FISCAL:

        Formato:
        Solução de Consulta {numero}

        Consulta: [Pergunta/resumo da dúvida]

        Resposta oficial:
        1. [Entendimento da Receita/CARF]
        2. [Fundamentação legal]
        3. [Condicionantes e limitações]

        Aplicação prática:
        • Casos em que se aplica
        • Procedimentos recomendados
        • Riscos a considerar

        Referências: [Leis, regulamentos citados]
        Data: [Publicação]

        DIRETRIZES:
        - Identificar claramente a dúvida e a resposta
        - Destaque se o posicionamento é vinculante
        - Mencione impactos em planning tributário
        - Incluir alertas sobre limites da solução
        - Máximo 160 palavras

        PRODUZA O RESUMO:
        """
    
    @staticmethod
    def _decreto_prompt(text: str, metadata: dict) -> str:
        """Prompt especializado para Decretos."""
        numero = metadata.get('numero', '')
        orgao = metadata.get('orgao', '')
        
        return f"""
        ANALISE ESTE DECRETO COM ÊNFASE EM MATÉRIA TRIBUTÁRIA:

        DECRETO {numero} - {orgao}

        CONTEÚDO:
        {text[:2200]}

        ---

        RESUMO PARA ANÁLISE FISCAL:

        Estrutura:
        Decreto {numero} - [Finalidade principal]

        Disposições tributárias relevantes:
        • [Regulamentação de lei tributária]
        • [Criação/modificação de incentivo fiscal]
        • [Estabelecimento de procedimentos]

        Abrangência:
        - [Setores/atividades alcançados]
        - [Regimes tributários afetados]
        - [Condições para aplicação]

        Vigência e transição: [Datas e prazos]
        Revogações: [Normas substituídas]

        ORIENTAÇÕES:
        - Destaque se trata de regulamentação de lei
        - Mencione benefícios fiscais criados/alterados
        - Incluir prazos para adequação
        - Relacionar com leis específicas
        - Máximo 170 palavras

        SAÍDA:
        """
    
    @staticmethod
    def _generic_prompt(text: str, metadata: dict) -> str:
        """Prompt genérico para outros tipos de publicação."""
        tipo = metadata.get('tipo', 'Norma')
        numero = metadata.get('numero', '')
        orgao = metadata.get('orgao', '')
        
        return f"""
        ANALISE ESTA PUBLICAÇÃO DO DOU IDENTIFICANDO ASPECTOS FISCAIS/TRIBUTÁRIOS:

        {tipo} {numero} - {orgao}

        TEXTO:
        {text[:1800]}

        ---

        RESUMO TÉCNICO:

        {tipo} {numero}

        Conteúdo relevante para área fiscal:
        • [Pontos relacionados a tributos]
        • [Obrigações acessórias mencionadas]
        • [Prazos ou valores significativos]

        Aplicabilidade: [Para quem se destina]
        Base legal: [Referências normativas]
        Vigência: [Quando surte efeitos]

        INSTRUÇÕES:
        - Extrair apenas elementos fiscais/tributários
        - Se não houver conteúdo relevante, indicar
        - Manter linguagem profissional
        - Máximo 100 palavras

        RESPOSTA:
        """


class SummaryFormatter:
    """Formatador de resumos para consistência."""
    
    @staticmethod
    def format(summary: str, metadata: dict) -> str:
        """
        Formata o resumo para padrão consistente.
        
        Args:
            summary: Resumo bruto
            metadata: Metadados da publicação
        
        Returns:
            Resumo formatado
        """
        if not summary:
            return ""
        
        # Remover espaços extras
        summary = ' '.join(summary.split())
        
        # Garantir que começa com o tipo/número se disponível
        tipo = metadata.get('tipo', '')
        numero = metadata.get('numero', '')
        
        if tipo and numero and not summary.startswith(f"{tipo} {numero}"):
            summary = f"{tipo} {numero} - {summary}"
        elif tipo and not summary.startswith(tipo):
            summary = f"{tipo} - {summary}"
        
        # Garantir pontuação final
        if summary and not summary.endswith(('.', '!', '?')):
            summary = summary + '.'
        
        # Capitalizar primeira letra
        if summary and len(summary) > 1:
            summary = summary[0].upper() + summary[1:]
        
        # Limitar parágrafos
        paragraphs = summary.split('\n\n')
        if len(paragraphs) > 3:
            summary = '\n\n'.join(paragraphs[:3])
        
        return summary.strip()
    
    @staticmethod
    def add_metadata(summary: str, metadata: dict) -> str:
        """
        Adiciona metadados formatados ao resumo.
        
        Args:
            summary: Resumo base
            metadata: Metadados
        
        Returns:
            Resumo com metadados
        """
        if not summary:
            return ""
        
        lines = []
        
        # Adicionar resumo
        lines.append(summary)
        lines.append("")  # Linha em branco
        
        # Adicionar metadados se disponíveis
        orgao = metadata.get('orgao')
        data = metadata.get('data')
        
        if orgao or data:
            meta_line = []
            if orgao:
                meta_line.append(f"Órgão: {orgao}")
            if data:
                meta_line.append(f"Publicação: {data}")
            
            lines.append(" · ".join(meta_line))
        
        return '\n'.join(lines)
