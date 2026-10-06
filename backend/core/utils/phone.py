"""
Utilitários de Normalização de Números e Identificadores do WhatsApp.
"""

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
