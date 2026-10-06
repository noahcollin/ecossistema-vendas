"""
Utilitários de Higienização de Strings e Segmentação Orgânica de Mensagens no WhatsApp.
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
