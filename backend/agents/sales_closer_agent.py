from typing import List, Optional, Any
from core.logger import logger
from core.openai_client import openai_client
from core.config import settings
from core.utils import higienizar_nome_perfil
import models
from .prompts import PROMPT_BASE_VENDEDOR, ORIENTACOES_POR_ESTAGIO

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
    status_funil: Optional[Any] = None  # fallback retrocompatível
) -> str:
    """
    Gera a resposta humanizada do Vendedor ('Seu Zé') via GPT-4o,
    alimentado pela Ficha do Lead, etapa atual da jornada e últimas mensagens imediatas.
    """
    try:
        historico_lista = list(historico_recente) if historico_recente else []
        nome_validado = higienizar_nome_perfil(nome_cliente_bruto)
        
        # Orientação contextual sobre o nome do cliente
        if nome_validado:
            primeiro_nome = nome_validado.split()[0]
            instrucao_nome = (
                f"\n[TRATAMENTO]: O nome informado no perfil é '{nome_validado}'. "
                f"Se parecer o nome real de uma pessoa, chame-o pelo primeiro nome ({primeiro_nome}) com simpatia. "
                "Se for o nome de uma loja, empresa, frase ou versículo, use saudações calorosas sem chamá-lo por esse termo, e pergunte como prefere ser chamado se for oportuno."
            )
        else:
            instrucao_nome = "\n[TRATAMENTO]: O nome exato não foi identificado no perfil. Use saudações neutras e acolhedoras e, se for início de conversa, pergunte o nome dele."

        # Orientação conforme a etapa do funil (FSM)
        etapa_atual = etapa_funil
        if not etapa_atual:
            if status_funil and hasattr(status_funil, "value"):
                # Conversão heurística do legado
                val = str(status_funil.value)
                if "NOVO" in val:
                    etapa_atual = models.EtapaFunil.NOVO_CONTATO
                elif "QUALIFICACAO" in val:
                    etapa_atual = models.EtapaFunil.QUALIFICACAO
                elif "FECHAMENTO" in val or "CONTRATO" in val:
                    etapa_atual = models.EtapaFunil.FECHAMENTO
                else:
                    etapa_atual = models.EtapaFunil.NEGOCIACAO
            else:
                etapa_atual = models.EtapaFunil.QUALIFICACAO

        orientacao_estagio = ORIENTACOES_POR_ESTAGIO.get(etapa_atual, "Conduza a conversa de forma consultiva e empática.")
        ficha_formatada = ficha_resumo.strip() if ficha_resumo else "Primeiro contato, ainda sem dados acumulados."

        bloco_contexto = f"""
{PROMPT_BASE_VENDEDOR}
{instrucao_nome}

[FICHA ATUALIZADA DO CLIENTE - MEMÓRIA DE LONGO PRAZO]
{ficha_formatada}

[ESTÁGIO ATUAL DA NEGOCIAÇÃO NO FUNIL]
Etapa: {etapa_atual.value}
Objetivo Desta Etapa: {orientacao_estagio}
"""

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
        logger.error(f"[VENDEDOR ERRO] ❌ Falha na geração da resposta comercial: {e}", exc_info=True)
        return "Opa, deu uma oscilação na conexão aqui comigo! Você poderia me mandar de novo, por gentileza?"


async def gerar_mensagem_followup(
    nome_cliente_bruto: str,
    ficha_resumo: Optional[str],
    etapa_funil: models.EtapaFunil,
    tentativa: int,
    historico_recente: Optional[List[models.Interacao]] = None
) -> str:
    """
    Gera mensagem de resgate/follow-up proativa e humanizada do Vendedor ('Seu Zé')
    conforme a tentativa na cadência (1, 2 ou 3) e o histórico prévio.
    Implementa o requisito RF11 do PRD (Motor de Follow-up Cronometrado).
    """
    from .prompts import ORIENTACOES_FOLLOWUP

    try:
        historico_lista = list(historico_recente) if historico_recente else []
        nome_validado = higienizar_nome_perfil(nome_cliente_bruto)
        if nome_validado:
            primeiro_nome = nome_validado.split()[0]
            instrucao_nome = (
                f"\n[TRATAMENTO]: O nome informado no perfil é '{nome_validado}'. "
                f"Se parecer o nome real de uma pessoa, chame-o pelo primeiro nome ({primeiro_nome}) com simpatia. "
                "Se for o nome de uma loja, empresa, frase ou versículo, use uma saudação acolhedora sem chamá-lo por esse termo."
            )
        else:
            instrucao_nome = "\n[TRATAMENTO]: O nome exato não foi identificado. Use saudação acolhedora e educada."

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

        # Em follow-up inicial usamos modelo rápido; em negociação avançada usamos gpt-4o
        modelo = settings.MODEL_CLOSER_ADVANCED if (etapa_funil in [models.EtapaFunil.NEGOCIACAO, models.EtapaFunil.FECHAMENTO]) else settings.MODEL_CLOSER_FAST

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
        logger.error(f"[FOLLOWUP VENDEDOR ERRO] ❌ Falha ao gerar mensagem de follow-up: {e}", exc_info=True)
        if tentativa == 1:
            return "Olá! Tudo bem por aí? Só passando para ver se você conseguiu ver a mensagem anterior e se posso ajudar em algo!"
        elif tentativa == 2:
            return "Olá! Espero que esteja tendo uma ótima semana. Conseguiu pensar naqueles pontos que conversamos? Qualquer dúvida, sigo por aqui!"
        else:
            return "Olá! Imagino que a rotina esteja corrida por aí. Vou deixar o contato pausado para não incomodar, mas sigo à sua inteira disposição quando quiser retomar! Um abraço."
