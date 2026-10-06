"""
Utilitários de Anonimização e Mascaramento LGPD para Logs e Auditoria Segura.
"""

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
