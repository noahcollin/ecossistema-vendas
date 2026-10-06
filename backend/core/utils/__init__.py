"""
Módulo Centralizador de Utilitários Técnicos e Auxiliares do Ecossistema.
Re-exporta funções de LGPD, normalização telefônica e formatação.
"""

from .lgpd import mascarar_telefone, mascarar_nome
from .phone import normalizar_telefone
from .formatting import higienizar_nome_perfil, dividir_mensagens_whatsapp

__all__ = [
    "mascarar_telefone",
    "mascarar_nome",
    "normalizar_telefone",
    "higienizar_nome_perfil",
    "dividir_mensagens_whatsapp",
]
