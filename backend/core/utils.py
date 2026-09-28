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
    max_baloes: int = 5,
    limite_caracteres_balao: int = 200
) -> list[str]:
    """
    Divide uma resposta comercial em múltiplos balões curtos e humanizados para o WhatsApp.
    Aplica uma estratégia resiliente de 4 camadas:
    1. Normalização de quebras de linha (\\r\\n -> \\n, espaços residuais).
    2. Divisão prioritária pelo delimitador explícito '|||' (instrução nativa da persona).
    3. Divisão secundária por quebras de parágrafo (\\n\\n) ou linhas individuais (\\n).
    4. Divisão semântica anti-textão por sentenças (. , ! , ? ) se algum bloco exceder
       o limite confortável para leitura móvel (~3-4 linhas / ~180-200 caracteres).
    5. Higienização: expurga marcadores residuais, espaços em branco e limita a max_baloes.
    """
    if not texto or not texto.strip():
        return []

    texto_limpo = texto.strip()

    # 1. Normalização de quebras de linha
    texto_limpo = texto_limpo.replace("\r\n", "\n").replace("\r", "\n")
    texto_limpo = re.sub(r"\n[ \t]+\n", "\n\n", texto_limpo)

    # 2. Divisão primária por delimitador explícito '|||'
    if "|||" in texto_limpo:
        blocos_iniciais = [p.strip() for p in texto_limpo.split("|||") if p.strip()]
    else:
        blocos_iniciais = [texto_limpo]

    # 3. Divisão secundária por parágrafos e quebras de linha
    blocos_paragrafos: list[str] = []
    for bloco in blocos_iniciais:
        if "\n\n" in bloco:
            partes = [p.strip() for p in bloco.split("\n\n") if p.strip()]
            blocos_paragrafos.extend(partes)
        elif "\n" in bloco and len(bloco) > 100:
            partes = [p.strip() for p in bloco.split("\n") if p.strip()]
            blocos_paragrafos.extend(partes)
        else:
            blocos_paragrafos.append(bloco)

    # 4. Divisão semântica anti-textão por sentenças (frases completas)
    blocos_finais: list[str] = []
    padrao_pontuacao = re.compile(r"([.!?…]+(?:\s+|\n+|$))")

    for bloco in blocos_paragrafos:
        if len(bloco) <= limite_caracteres_balao:
            blocos_finais.append(bloco)
            continue

        # Decompõe em sentenças completas preservando a pontuação
        tokens = padrao_pontuacao.split(bloco)
        frases: list[str] = []
        idx = 0
        while idx < len(tokens):
            frase = tokens[idx].strip()
            if idx + 1 < len(tokens):
                pontuacao = tokens[idx + 1].strip()
                frase = f"{frase}{pontuacao}".strip()
                idx += 2
            else:
                idx += 1
            if frase:
                frases.append(frase)

        if len(frases) > 1:
            # Agrupa frases de forma harmônica respeitando o limite
            acumulador = ""
            for f in frases:
                if not acumulador:
                    acumulador = f
                elif len(acumulador) + len(f) + 1 <= limite_caracteres_balao:
                    acumulador += " " + f
                else:
                    blocos_finais.append(acumulador.strip())
                    acumulador = f
            if acumulador:
                blocos_finais.append(acumulador.strip())
        else:
            blocos_finais.append(bloco)

    # 5. Higienização final e Clamp
    resultado: list[str] = []
    for b in blocos_finais:
        b_limpo = b.replace("|||", "").strip()
        if b_limpo:
            resultado.append(b_limpo)

    return resultado[:max_baloes]


