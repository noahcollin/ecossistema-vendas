"""
Módulo de Utilitários Centrais do Ecossistema de Vendas.
Contém funções auxiliares de tratamento de dados, higienização e validação de strings.
"""

import re

def higienizar_nome_perfil(nome_bruto: str | None) -> str | None:
    """
    Higieniza caracteres e formata a capitalização do nome de perfil do WhatsApp.
    Remove pontuações e emojis residuais, mantendo letras acentuadas e espaços.
    A distinção semântica entre nomes reais e nomes de empresas/slogans é tratada pelo Agente de IA.
    """
    if not nome_bruto or not nome_bruto.strip():
        return None
        
    # Remove pontuações e emojis, mantendo letras acentuadas e espaços
    texto_limpo = re.sub(r'[^\w\s]', '', nome_bruto, flags=re.UNICODE).strip()
    
    # Se sobrar menos de 2 letras alfabéticas (ex: '.', '123', emojis puros)
    letras_apenas = re.sub(r'[^a-zA-ZÀ-ÿ]', '', texto_limpo)
    if len(letras_apenas) < 2:
        return None
        
    palavras = texto_limpo.split()
    return " ".join(p.capitalize() for p in palavras)

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


def mascarar_telefone(telefone_bruto: str | None) -> str:
    """
    Mascara número de telefone para logs seguros em conformidade com a LGPD (ex: +5583****3098).
    """
    if not telefone_bruto:
        return ""
    tel = str(telefone_bruto).strip()
    if len(tel) <= 6:
        return tel
    return f"{tel[:5]}****{tel[-4:]}"


def mascarar_nome(nome_bruto: str | None) -> str:
    """
    Mascara nome de cliente para logs em conformidade com a LGPD (ex: João S***).
    """
    if not nome_bruto or not nome_bruto.strip():
        return "Anônimo"
    partes = nome_bruto.strip().split()
    if len(partes) == 1:
        p = partes[0]
        return f"{p[:2]}***" if len(p) > 2 else p
    return f"{partes[0]} {partes[-1][:1]}***"


def dividir_mensagens_whatsapp(
    texto: str | None,
    max_baloes: int = 5
) -> list[str]:
    """
    Divide uma resposta comercial em múltiplos balões para o WhatsApp.
    A fragmentação é delimitada exclusivamente pela IA através de:
    - Marcador explícito '|||'
    - Quebras de parágrafo duplas (\\n\\n ou \\r\\n\\r\\n)
    
    Não realiza quebras semânticas artificiais por palavras, saudações ou títulos.
    """
    if not texto or not texto.strip():
        return []

    # 1. Normaliza quebras de linha Windows e Unix (\r\n -> \n, \r -> \n)
    texto_limpo = texto.strip().replace("\r\n", "\n").replace("\r", "\n")

    # 2. Divide exclusivamente pelos delimitadores definidos pela IA (||| ou \n\n)
    partes_brutas = re.split(r"\|\|\|+|\n\s*\n+", texto_limpo)

    # 3. Higieniza cada balão, expurga pipes residuais e filtra vazios
    baloes: list[str] = []
    for parte in partes_brutas:
        item = parte.replace("|||", "").strip()
        if item:
            baloes.append(item)

    return baloes[:max_baloes]



