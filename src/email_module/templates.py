# Templates HTML/texto
"""
Templates de email para o boletim DOU.
"""
import html
from datetime import datetime
from typing import List, Dict, Any
from .models.publication import Publication


class EmailTemplates:
    """Gerador de templates de email."""
    
    @staticmethod
    def create_daily_bulletin(
        publications: List[Publication],
        search_config: Dict[str, Any],
        email_config: Dict[str, Any],
        include_ai_summaries: bool = True
    ) -> Dict[str, str]:
        """
        Cria o boletim diário do DOU.
        
        Args:
            publications: Lista de publicações
            search_config: Configuração da busca
            email_config: Configuração de email
            include_ai_summaries: Incluir resumos de IA
        
        Returns:
            Dicionário com 'subject', 'html' e 'text'
        """
        # Assunto do email
        subject = EmailTemplates._create_subject(publications, email_config)
        
        # Conteúdo texto simples
        text_content = EmailTemplates._create_text_content(
            publications, search_config, include_ai_summaries
        )
        
        # Conteúdo HTML
        html_content = EmailTemplates._create_html_content(
            publications, search_config, include_ai_summaries
        )
        
        return {
            'subject': subject,
            'text': text_content,
            'html': html_content
        }
    
    @staticmethod
    def _create_subject(publications: List[Publication], email_config: Dict[str, Any]) -> str:
        """Cria o assunto do email."""
        prefix = email_config.get('subject_prefix', '[DOU Fiscal]')
        hoje = datetime.now().strftime('%d/%m/%Y')
        
        if publications:
            count = len(publications)
            return f"{prefix} {count} publicação(ões) relevante(s) - {hoje}"
        else:
            return f"{prefix} Nenhuma publicação relevante - {hoje}"
    
    @staticmethod
    def _create_text_content(
        publications: List[Publication],
        search_config: Dict[str, Any],
        include_ai_summaries: bool
    ) -> str:
        """Cria conteúdo em texto simples."""
        lines = []
        hoje = datetime.now().strftime('%d/%m/%Y')
        
        # Cabeçalho
        lines.append(f"BOLETIM DOU FISCAL/TRIBUTÁRIO - {hoje}")
        lines.append("=" * 50)
        lines.append("")
        
        if not publications:
            lines.append("Nenhuma publicação relevante encontrada para os critérios atuais.")
            lines.append("")
        else:
            lines.append(f"Total de publicações: {len(publications)}")
            lines.append("")
            
            for i, pub in enumerate(publications, 1):
                lines.append(f"{i}. {pub.headline}")
                
                if pub.orgao:
                    lines.append(f"   Órgão: {pub.orgao}")
                
                if pub.data:
                    lines.append(f"   Data: {pub.data}")
                
                if include_ai_summaries and pub.resumo_ia:
                    lines.append(f"   Resumo: {pub.resumo_ia}")
                
                lines.append(f"   URL: {pub.url}")
                lines.append("")
        
        # Informações da busca
        lines.append("-" * 50)
        lines.append("INFORMAÇÕES DA BUSCA:")
        lines.append(f"Período: {search_config.get('period', 'today')}")
        lines.append(f"Seções: {', '.join(search_config.get('sections', []))}")
        lines.append(f"Frases: {', '.join(search_config.get('phrases', []))[:100]}...")
        
        if include_ai_summaries:
            lines.append("")
            lines.append("Resumos gerados automaticamente por IA.")
            lines.append("Sempre confira o texto oficial no DOU.")
        
        lines.append("")
        lines.append("Este boletim foi gerado automaticamente pelo Robô DOU.")
        
        return '\n'.join(lines)
    
    @staticmethod
    def _create_html_content(
        publications: List[Publication],
        search_config: Dict[str, Any],
        include_ai_summaries: bool
    ) -> str:
        """Cria conteúdo HTML formatado."""
        hoje = datetime.now().strftime('%d/%m/%Y')
        
        html = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Boletim DOU Fiscal/Tributário - {hoje}</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .header {{
                    background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
                    color: white;
                    padding: 25px;
                    border-radius: 8px;
                    margin-bottom: 25px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                    font-weight: bold;
                }}
                .header .date {{
                    font-size: 14px;
                    opacity: 0.9;
                    margin-top: 5px;
                }}
                .stats {{
                    background: #e3f2fd;
                    padding: 15px;
                    border-radius: 6px;
                    margin: 20px 0;
                    text-align: center;
                    font-size: 14px;
                    color: #1565c0;
                }}
                .publication {{
                    background: white;
                    padding: 20px;
                    margin: 15px 0;
                    border-left: 4px solid #2196f3;
                    border-radius: 4px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .publication-title {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #1a237e;
                    margin-bottom: 10px;
                    line-height: 1.4;
                }}
                .publication-meta {{
                    font-size: 13px;
                    color: #666;
                    margin-bottom: 12px;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 15px;
                }}
                .badge {{
                    background: #e3f2fd;
                    color: #1565c0;
                    padding: 3px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                }}
                .summary {{
                    background: #f5f5f5;
                    padding: 12px;
                    border-radius: 4px;
                    margin: 12px 0;
                    border-left: 3px solid #4caf50;
                    font-style: italic;
                }}
                .summary::before {{
                    content: "📌 ";
                    font-weight: bold;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding: 20px;
                    color: #666;
                    font-size: 12px;
                    border-top: 1px solid #ddd;
                }}
                .btn {{
                    display: inline-block;
                    background: #2196f3;
                    color: white;
                    padding: 8px 16px;
                    text-decoration: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 14px;
                    margin: 10px 5px;
                }}
                .no-results {{
                    background: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 6px;
                    margin: 20px 0;
                }}
                .search-info {{
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 4px;
                    margin: 20px 0;
                    font-size: 13px;
                }}
                @media (max-width: 600px) {{
                    body {{ padding: 10px; }}
                    .publication {{ padding: 15px; }}
                    .publication-title {{ font-size: 16px; }}
                    .publication-meta {{ flex-direction: column; gap: 5px; }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📰 Boletim Fiscal DOU</h1>
                <div class="date">{hoje}</div>
            </div>
        """
        
        # Estatísticas
        if publications:
            html += f"""
            <div class="stats">
                📊 {len(publications)} publicação(ões) relevante(s) encontrada(s)
            </div>
            """
        else:
            html += """
            <div class="no-results">
                <h3>📭 Nenhuma publicação relevante</h3>
                <p>Não foram encontradas publicações relevantes para os critérios de busca atuais.</p>
            </div>
            """
        
        # Lista de publicações
        if publications:
            for pub in publications:
                html += EmailTemplates._create_publication_html(pub, include_ai_summaries)
        
        # Informações da busca
        html += EmailTemplates._create_search_info_html(search_config, include_ai_summaries)
        
        # Rodapé
        html += """
            <div class="footer">
                <p>
                    🤖 Boletim gerado automaticamente pelo Robô DOU<br>
                    <small>Próxima atualização: Amanhã às 07:00 BRT</small>
                </p>
                <p style="font-size: 11px; color: #999; margin-top: 15px;">
                    Para ajustar os critérios de busca ou destinatários, edite o config.yml no repositório.
                </p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def _create_publication_html(pub: Publication, include_ai_summaries: bool) -> str:
        """Cria HTML para uma publicação individual."""
        # Escape HTML para segurança
        titulo = html.escape(pub.titulo)
        headline = html.escape(pub.headline)
        orgao = html.escape(pub.orgao) if pub.orgao else ''
        url = html.escape(pub.url)
        
        html_content = f"""
        <div class="publication">
            <div class="publication-title">
                {headline}
            </div>
            
            <div class="publication-meta">
        """
        
        # Metadados
        if orgao:
            html_content += f'<span>🏛️ {orgao}</span>'
        
        if pub.tipo:
            html_content += f'<span class="badge">{pub.tipo}</span>'
        
        if pub.numero:
            html_content += f'<span class="badge">#{pub.numero}</span>'
        
        if pub.data:
            html_content += f'<span>📅 {pub.data}</span>'
        
        if pub.secao:
            html_content += f'<span>📄 Seção {pub.secao}</span>'
        
        html_content += """
            </div>
        """
        
        # Resumo IA
        if include_ai_summaries and pub.resumo_ia:
            resumo = html.escape(pub.resumo_ia)
            html_content += f"""
            <div class="summary">
                {resumo}
            </div>
            """
        
        # Botão de acesso
        html_content += f"""
            <div style="text-align: right; margin-top: 15px;">
                <a href="{url}" class="btn" target="_blank" rel="noopener noreferrer">
                    🔗 Acessar Publicação Oficial
                </a>
            </div>
        </div>
        """
        
        return html_content
    
    @staticmethod
    def _create_search_info_html(search_config: Dict[str, Any], include_ai_summaries: bool) -> str:
        """Cria HTML com informações da busca."""
        period = search_config.get('period', 'today')
        sections = ', '.join(search_config.get('sections', []))
        phrases = '; '.join(search_config.get('phrases', []))[:150]
        
        html_content = f"""
        <div class="search-info">
            <h4 style="margin-top: 0; color: #555;">🔍 Critérios da Busca</h4>
            <p><strong>Período:</strong> {period}</p>
            <p><strong>Seções:</strong> {sections}</p>
            <p><strong>Frases buscadas:</strong> {phrases}...</p>
        """
        
        if include_ai_summaries:
            html_content += """
            <p style="font-size: 12px; color: #666; margin-top: 10px;">
                <em>✨ Resumos gerados automaticamente por IA (Hugging Face/Gemini). 
                Sempre consulte o texto oficial no DOU para verificação.</em>
            </p>
            """
        
        html_content += "</div>"
        
        return html_content
    
    @staticmethod
    def create_test_email() -> Dict[str, str]:
        """Cria email de teste."""
        hoje = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        subject = "[DOU Bot] Email de Teste"
        
        text_content = f"""
        DOU BOT - EMAIL DE TESTE
        ========================
        
        Data: {hoje}
        
        Este é um email de teste enviado pelo Robô DOU para verificar 
        a configuração de email.
        
        Se você recebeu este email, a configuração de SMTP está funcionando 
        corretamente.
        
        Próxima execução do robô: Amanhã às 07:00 BRT.
        """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #1a237e; color: white; padding: 20px; text-align: center; border-radius: 8px; }}
                .content {{ background: white; padding: 20px; border-radius: 4px; margin: 20px 0; border-left: 4px solid #4caf50; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📧 DOU Bot - Email de Teste</h1>
                <p>{hoje}</p>
            </div>
            
            <div class="content">
                <p>Este é um <strong>email de teste</strong> enviado pelo Robô DOU para verificar a configuração de email.</p>
                
                <p>✅ Se você recebeu este email, a configuração de SMTP está funcionando corretamente.</p>
                
                <h3>Próximos passos:</h3>
                <ul>
                    <li>Próxima execução do robô: <strong>Amanhã às 07:00 BRT</strong></li>
                    <li>O robô buscará automaticamente publicações relevantes</li>
                    <li>Você receberá um email apenas se houver novidades</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>🤖 Robô DOU - Monitoramento Automático do Diário Oficial da União</p>
            </div>
        </body>
        </html>
        """
        
        return {
            'subject': subject,
            'text': text_content,
            'html': html_content
        }
