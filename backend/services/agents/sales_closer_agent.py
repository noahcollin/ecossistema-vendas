from typing import List, Optional, Any
from core.logger import logger
from core.openai_client import openai_client
from core.config import settings
from core.utils import higienizar_nome_perfil
import models
from .prompts import PROMPT_BASE_VENDEDOR, ORIENTACOES_POR_ESTAGIO

async def gerar_resposta_vendedor(
    nome_cliente_bruto: str,
    ficha_resumo: Optional[str],
    etapa_funil: Optional[models.EtapaFunil] = None,
    historico_recente: List[models.Interacao] = [],
    status_funil: Optional[Any] = None  # fallback retrocompatível
) -> str:
    """
    Gera a resposta humanizada do Vendedor ('Seu Zé') via GPT-4o,
    alimentado pela Ficha do Lead, etapa atual da jornada e últimas mensagens imediatas.
    """
    try:
        nome_validado = higienizar_nome_perfil(nome_cliente_bruto)
        
        # Orientação contextual sobre o nome do cliente
        if nome_validado:
            primeiro_nome = nome_validado.split()[0]
            instrucao_nome = f"\n[TRATAMENTO]: O cliente se chama {nome_validado}. Chame-o pelo primeiro nome ({primeiro_nome}) com simpatia e naturalidade."
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

        # Pega a janela configurada de mensagens recentes para manter o custo baixo e o fio da meada imediato
        janela_tamanho = settings.JANELA_HISTORICO_RECENTE
        mensagens_janela = historico_recente[-janela_tamanho:] if len(historico_recente) > janela_tamanho else historico_recente

        for interacao in mensagens_janela:
            role = "user" if interacao.origem == models.InteracaoOrigem.CLIENTE else "assistant"
            mensagens.append({"role": role, "content": interacao.texto})

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
            f"Etapa: {etapa_atual.value} | Histórico: {len(mensagens_janela)} msgs imediatas"
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
