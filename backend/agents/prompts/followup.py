"""
Diretrizes e Orientações Oficiais para a Cadência de Follow-Up do Eli Gentil.
Baseado no documento oficial 'PROMPT_ELI_v3.md' (Seção 3).
Objetivo: 1 balão, sem pedir desculpa, sem 'sumiu?', sempre com dois horários exatos da lista de horários livres.
"""

ORIENTACOES_FOLLOWUP = {
    1: (
        "TOQUE 1 (mesma tarde). 1 balão, sem pedir desculpa, sem 'sumiu?'. "
        "Se a conversa parou no mapeamento, retome a pergunta em aberto. "
        "Se parou no agendamento: '[Nome], amanhã 10h ou 15h para a conversa com o time?' "
        "(dois horários da lista de horários livres)."
    ),
    2: (
        "TOQUE 2 (manhã seguinte). 1 balão: "
        "'Oi, [nome]. Chegou a ver um horário para a nossa conversa?'"
    ),
    3: (
        "TOQUE 3 (dois dias depois). 1 balão: "
        "'Vou encerrar por aqui para não te encher. Se fizer sentido mais para frente, é só chamar.'"
    ),
}
