from typing import List, Optional
from core.logger import logger
from core.openai_client import openai_client
from core.config import settings
from core.utils import higienizar_nome_perfil
import models
from .prompts import (
    PROMPT_BASE_VENDEDOR,
    ORIENTACOES_POR_ESTAGIO,
    ORIENTACOES_FOLLOWUP,
)

def formatar_dialogo_para_chat(
    historico_recente: Optional[List[models.Interacao]],
    janela_tamanho: int = 6
) -> List[dict[str, str]]:
    """
    Formata o histórico recente em mensagens para o chat completion da OpenAI,
    distinguindo mensagens do cliente, do consultor humano e notas de sistema.
    """
    if not historico_recente:
        return []

    mensagens_janela = historico_recente[-janela_tamanho:] if len(historico_recente) > janela_tamanho else historico_recente
    chat_msgs = []
    for interacao in mensagens_janela:
        if interacao.origem == models.InteracaoOrigem.CLIENTE:
            chat_msgs.append({"role": "user", "content": interacao.texto})
        elif interacao.origem == models.InteracaoOrigem.HUMANO:
            chat_msgs.append({
                "role": "assistant",
                "content": f"[Mensagem do Consultor da nossa equipe]: {interacao.texto}"
            })
        elif interacao.origem == models.InteracaoOrigem.SISTEMA:
            chat_msgs.append({
                "role": "system",
                "content": f"[Diretriz Interna de Atendimento]: {interacao.texto}"
            })
        else:
            chat_msgs.append({"role": "assistant", "content": interacao.texto})
    return chat_msgs


async def gerar_resposta_vendedor(
    nome_cliente_bruto: str,
    ficha_resumo: Optional[str],
    etapa_funil: Optional[models.EtapaFunil] = None,
    historico_recente: Optional[List[models.Interacao]] = None,
    diretriz_proatividade: Optional[str] = None,
    **kwargs
) -> Optional[str]:
    """
    Gera a resposta humanizada do Vendedor ('Seu Zé') via GPT-4o,
    alimentado pela Ficha do Lead, etapa atual da jornada, últimas mensagens imediatas
    e diretrizes de proatividade comercial (Autonomous Closer Drive).
    """
    try:
        historico_lista = list(historico_recente) if historico_recente else []
        nome_validado = higienizar_nome_perfil(nome_cliente_bruto)
        
        # Identificação de nome de perfil do WhatsApp
        if nome_validado:
            instrucao_nome = f"\n[NOME_NO_PERFIL]: {nome_validado}"
        else:
            instrucao_nome = "\n[NOME_NO_PERFIL]: Não informado no perfil do WhatsApp."

        # Orientação conforme a etapa do funil (FSM)
        etapa_atual = etapa_funil or models.EtapaFunil.QUALIFICACAO

        orientacao_estagio = ORIENTACOES_POR_ESTAGIO.get(etapa_atual, "Conduza a conversa de forma consultiva e empática.")
        ficha_formatada = ficha_resumo.strip() if ficha_resumo else "Primeiro contato, ainda sem dados acumulados."

        bloco_proatividade = f"\n{diretriz_proatividade}\n" if diretriz_proatividade else ""

        bloco_contexto = f"""
{PROMPT_BASE_VENDEDOR}
{instrucao_nome}

[FICHA ATUALIZADA DO CLIENTE - MEMÓRIA DE LONGO PRAZO]
{ficha_formatada}

[ESTÁGIO ATUAL DA NEGOCIAÇÃO NO FUNIL]
Etapa: {etapa_atual.value}
Objetivo Desta Etapa: {orientacao_estagio}
{bloco_proatividade}"""

        mensagens = [{"role": "system", "content": bloco_contexto}]
        mensagens.extend(formatar_dialogo_para_chat(historico_lista, settings.JANELA_HISTORICO_RECENTE))

        # Roteamento Dinâmico de Modelos (FinOps):
        # Em NOVO_CONTATO e QUALIFICACAO, utiliza MODEL_CLOSER_FAST (gpt-4o-mini) para acolhimento e perguntas iniciais.
        # Em NEGOCIACAO e FECHAMENTO, utiliza MODEL_CLOSER_ADVANCED (gpt-4o) para persuasão e fechamento de alto valor.
        if settings.DYNAMIC_MODEL_ROUTING:
            if etapa_atual in [models.EtapaFunil.NOVO_CONTATO, models.EtapaFunil.QUALIFICACAO]:
                modelo_selecionado = settings.MODEL_CLOSER_FAST
            else:
                modelo_selecionado = settings.MODEL_CLOSER_ADVANCED
        else:
            modelo_selecionado = settings.MODEL_CLOSER

        logger.info(
            f"[VENDEDOR] 🧠 {modelo_selecionado} invocado para {nome_validado or 'Cliente'} | "
            f"Etapa: {etapa_atual.value} | Histórico: {len(historico_lista)} msgs imediatas"
        )

        resposta = await openai_client.chat.completions.create(
            model=modelo_selecionado,
            messages=mensagens,
            temperature=0.7,
            max_tokens=350
        )

        conteudo = resposta.choices[0].message.content.strip()
        logger.info(f"[VENDEDOR] 🤖 Resposta gerada com sucesso ({len(conteudo)} chars)")
        return conteudo

    except Exception as e:
        err_str = str(e).lower()
        termos_cota = [
            "insufficient_quota",
            "quota_exceeded",
            "exceeded your current quota",
            "credit_balance_exhausted",
            "no credits remaining",
            "billing_hard_limit_reached"
        ]
        if any(termo in err_str for termo in termos_cota):
            logger.critical(
                f"[OPENAI COTA ESGOTADA] 🚨 Créditos da OpenAI esgotados! Silenciando IA para evitar envio de mensagens confusas ao cliente: {e}"
            )
        else:
            logger.error(f"[VENDEDOR ERRO] ❌ Falha na geração da resposta comercial: {e}", exc_info=True)
        return None


async def gerar_mensagem_followup(
    nome_cliente_bruto: str,
    ficha_resumo: Optional[str],
    etapa_funil: models.EtapaFunil,
    tentativa: int,
    historico_recente: Optional[List[models.Interacao]] = None
) -> Optional[str]:
    """
    Gera mensagem de resgate/follow-up proativa e humanizada do Vendedor ('Seu Zé')
    conforme a tentativa na cadência (1, 2 ou 3) e o histórico prévio.
    Implementa o requisito RF11 do PRD (Motor de Follow-up Cronometrado).
    """
    try:
        historico_lista = list(historico_recente) if historico_recente else []
        nome_validado = higienizar_nome_perfil(nome_cliente_bruto)
        # Identificação de nome de perfil do WhatsApp
        if nome_validado:
            instrucao_nome = f"\n[NOME_NO_PERFIL]: {nome_validado}"
        else:
            instrucao_nome = "\n[NOME_NO_PERFIL]: Não informado no perfil do WhatsApp."

        diretriz_tentativa = ORIENTACOES_FOLLOWUP.get(
            tentativa,
            "Relembre o ponto em aberto com cordialidade e simpatia."
        )

        ficha_formatada = ficha_resumo.strip() if ficha_resumo else "Em processo de qualificação."

        bloco_contexto = f"""
{PROMPT_BASE_VENDEDOR}
{instrucao_nome}

[FICHA ATUALIZADA DO CLIENTE - MEMÓRIA DE LONGO PRAZO]
{ficha_formatada}

[CADÊNCIA DE RESGATE / FOLLOW-UP ATIVO - TOQUE {tentativa}/3]
Etapa do Funil Onde o Lead Parou: {etapa_funil.value}
Diretriz Deste Toque: {diretriz_tentativa}

INSTRUÇÕES CRÍTICAS DE CADÊNCIA:
1. Jamais seja agressivo ou pareça cobrador. Você é um parceiro comercial consultivo e atencioso.
2. Seja conciso (1 a 3 frases). Lembre que é WhatsApp.
3. Se for Toque 1 ou 2, termine com uma pergunta leve para estimular a resposta.
4. Se for Toque 3, NÃO force resposta: agradeça e encerre desejando sucesso, deixando claro que a porta continua aberta.
"""

        mensagens = [{"role": "system", "content": bloco_contexto}]
        mensagens.extend(formatar_dialogo_para_chat(historico_lista, settings.JANELA_HISTORICO_RECENTE))

        mensagens.append({
            "role": "system",
            "content": f"[INSTRUÇÃO FINAL]: O cliente parou de responder. Envie a mensagem proativa de Follow-up (Toque {tentativa}) seguindo o tom caloroso e natural do Seu Zé."
        })

        # Roteamento de Modelo para Follow-up (FinOps)
        if settings.DYNAMIC_MODEL_ROUTING:
            modelo = settings.MODEL_CLOSER_ADVANCED if (etapa_funil in [models.EtapaFunil.NEGOCIACAO, models.EtapaFunil.FECHAMENTO]) else settings.MODEL_CLOSER_FAST
        else:
            modelo = settings.MODEL_CLOSER

        logger.info(
            f"[FOLLOWUP VENDEDOR] ⏳ Gerando Toque {tentativa}/3 para {nome_validado or 'Cliente'} | "
            f"Modelo: {modelo} | Etapa: {etapa_funil.value}"
        )

        resposta = await openai_client.chat.completions.create(
            model=modelo,
            messages=mensagens,
            temperature=0.7,
            max_tokens=250
        )

        conteudo = resposta.choices[0].message.content.strip()
        logger.info(f"[FOLLOWUP VENDEDOR] ✉️ Mensagem gerada com sucesso ({len(conteudo)} chars)")
        return conteudo

    except Exception as e:
        err_str = str(e).lower()
        termos_cota = [
            "insufficient_quota",
            "quota_exceeded",
            "exceeded your current quota",
            "credit_balance_exhausted",
            "no credits remaining",
            "billing_hard_limit_reached"
        ]
        if any(termo in err_str for termo in termos_cota):
            logger.critical(
                f"[OPENAI COTA ESGOTADA - FOLLOWUP] 🚨 Créditos da OpenAI esgotados! Silenciando follow-up: {e}"
            )
        else:
            logger.error(f"[FOLLOWUP VENDEDOR ERRO] ❌ Falha ao gerar mensagem de follow-up: {e}", exc_info=True)
        return None
