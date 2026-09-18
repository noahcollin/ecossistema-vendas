"""
Módulo de Utilitários Centrais do Ecossistema de Vendas.
Contém funções auxiliares de tratamento de dados, higienização e validação de strings.
"""

import re
from core.logger import logger

# Termos que denunciam frases, slogans ou perfis comerciais/institucionais no WhatsApp
PALAVRAS_BLOQUEADAS_NOME = {
    "deus", "jesus", "senhor", "fiel", "amor", "paz", "fe", "fé",
    "loja", "lojinha", "advocacia", "advogado", "advogada",
    "suporte", "atendimento", "comercial", "vendas", "oficial",
    "adm", "contato", "delivery", "distribuidora", "mercado",
    "consultoria", "assessoria"
}

def higienizar_nome_perfil(nome_bruto: str | None) -> str | None:
    """
    Higieniza e valida se o texto do perfil do WhatsApp é realmente um nome de pessoa.
    Permite nomes compostos de até 6 a 7 palavras,
    mas descarta frases religiosas, slogans, números puros ou emojis.
    """
    if not nome_bruto or not nome_bruto.strip():
        return None
        
    # Remove pontuações e emojis, mantendo letras acentuadas e espaços
    texto_limpo = re.sub(r'[^\w\s]', '', nome_bruto, flags=re.UNICODE).strip()
    
    # Se sobrar menos de 2 letras alfabéticas (ex: '.', '123', emojis)
    letras_apenas = re.sub(r'[^a-zA-ZÀ-ÿ]', '', texto_limpo)
    if len(letras_apenas) < 2:
        return None
        
    palavras = texto_limpo.split()
    
    # Se tiver mais de 7 palavras, com certeza é uma frase/slogan e não um nome próprio
    if len(palavras) > 7:
        logger.info(f"[NOME HIGIENE] Nome '{nome_bruto}' descartado (mais de 7 palavras - provável frase).")
        return None
        
    # Checa se alguma palavra está na lista de termos institucionais/slogans
    palavras_lower = [p.lower() for p in palavras]
    if any(termo in palavras_lower for termo in PALAVRAS_BLOQUEADAS_NOME):
        logger.info(f"[NOME HIGIENE] Nome '{nome_bruto}' descartado (termo institucional/religioso detectado).")
        return None
        
    # Formata com iniciais maiúsculas limpas
    nome_formatado = " ".join(p.capitalize() for p in palavras)
    return nome_formatado

def normalizar_telefone(telefone_bruto: str | None) -> str:
    """
    Normaliza o identificador do WhatsApp para um padrão consistente:
    - Remove sufixos como '@s.whatsapp.net', '@c.us' ou identificadores de sessão.
    - Remove caracteres não-numéricos (espaços, hífens, parênteses).
    - Retorna a string com '+' seguido apenas dos dígitos numéricos.
    """
    if not telefone_bruto:
        return ""
    # Remove sufixos de JID do WhatsApp
    limpo = str(telefone_bruto).split("@")[0].split(":")[0].strip()
    digitos = "".join(ch for ch in limpo if ch.isdigit())
    if digitos:
        return f"+{digitos}"
    return ""

