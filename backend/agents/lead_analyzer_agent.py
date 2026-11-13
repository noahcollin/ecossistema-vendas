import json
from typing import List, Optional
from core.openai_client import openai_client, is_openai_quota_error
from core.logger import logger
from core.config import settings
from core.temporal import TemporalContextProvider
import models
import schemas
from .prompts import PROMPT_SISTEMA_ANALISTA


async def analisar_lead_e_fsm(
    lead: models.Lead,
    historico_recente: List[models.Interacao],
    nova_mensagem: Optional[str] = None
) -> schemas.LeadAnalysisOutput:
    """
    Executa a análise do perfil do lead e decide a transição das 4 Dimensões de Vendas
    utilizando gpt-4o-mini com Structured Outputs (garantia 100% de tipagem Pydantic V2).
    """
    try:
        ficha_anterior = lead.resumo_perfil or "Primeiro contato. Nenhum dado prévio registrado."
        dados_anteriores = lead.dados_qualificacao or {}

        etapa_atual = lead.etapa_funil.value if (hasattr(lead, "etapa_funil") and lead.etapa_funil) else models.EtapaFunil.NOVO_CONTATO.value
        desfecho_atual = lead.desfecho.value if (hasattr(lead, "desfecho") and lead.desfecho) else models.DesfechoLead.EM_ANDAMENTO.value
        temp_atual = lead.temperatura.value if (hasattr(lead, "temperatura") and lead.temperatura) else models.TemperaturaLead.FRIO.value
        tags_atuais = lead.tags if (hasattr(lead, "tags") and lead.tags) else []

        # Formata o contexto imediato da conversa conforme janela configurada
        janela_tamanho = settings.JANELA_HISTORICO_RECENTE
        mensagens_formatadas = []
        for interacao in historico_recente[-janela_tamanho:]:
            if interacao.origem == models.InteracaoOrigem.CLIENTE:
                remetente = "Cliente"
            elif interacao.origem == models.InteracaoOrigem.HUMANO:
                remetente = "Consultor Humano (Equipe)"
            elif interacao.origem == models.InteracaoOrigem.SISTEMA:
                remetente = "Nota de Sistema"
            else:
                remetente = "Vendedor (IA)"
            ts = TemporalContextProvider.formatar_timestamp_local(getattr(interacao, "criado_em", None))
            prefixo_ts = f"[{ts}] " if ts else ""
            mensagens_formatadas.append(f"{prefixo_ts}{remetente}: {interacao.texto}")

        # Se nova_mensagem foi informada e ainda não está no histórico salvo
        if nova_mensagem and nova_mensagem.strip():
            msg_limpa = nova_mensagem.strip()
            ja_esta_no_historico = any(msg_limpa in mf for mf in mensagens_formatadas[-2:]) if mensagens_formatadas else False
            if not ja_esta_no_historico:
                mensagens_formatadas.append(f"Cliente: {msg_limpa}")

        contexto_dialogo = "\n".join(mensagens_formatadas) if mensagens_formatadas else f"Cliente: {(nova_mensagem or '').strip() or 'Iniciou conversa'}"
        bloco_data_hora = TemporalContextProvider.gerar_bloco_referencia_temporal()

        prompt_usuario = f"""
{bloco_data_hora}

[ESTADO ATUAL NO BANCO DE DADOS]
Nome Registrado: {lead.nome or 'Desconhecido'}
Telefone: {lead.telefone}
Etapa do Funil Atual: {etapa_atual}
Desfecho Atual: {desfecho_atual}
Temperatura Atual: {temp_atual}
Tags Atuais: {tags_atuais}

[FICHA DO LEAD ACUMULADA ATÉ O MOMENTO]
{ficha_anterior}

[DADOS ESTRUTURADOS ATUAIS]
{json.dumps(dados_anteriores, ensure_ascii=False)}

[CONTEXTO RECENTE DO DIÁLOGO]
{contexto_dialogo}

Com base nas informações acima e na nova interação do cliente, atualize a Ficha do Lead (incluindo ramo, rede social principal, necessidade mapeada, solução nomeada e, se houver, o dia e horário agendados), os dados estruturados e classifique com precisão as dimensões de vendas (etapa_sugerida, desfecho_sugerido, transbordo_sugerido, pronto_fechamento, temperatura_sugerida, motivo_perda, valor_estimado, tags_sugeridas, opt_out_detectado) com sua justificativa analítica. Regra crítica: mantenha transbordo_sugerido=False e pronto_fechamento=False durante a abertura (NOVO_CONTATO), mapeamento de ramo/rede/necessidade (QUALIFICACAO), apresentação da solução e proposta inicial de turno ('Hoje à tarde ou amanhã de manhã?' em NEGOCIACAO). Defina etapa_sugerida=FECHAMENTO, pronto_fechamento=True e transbordo_sugerido=True SOMENTE quando o dia e horário da conversa de 20 min já estiverem confirmados com número pelo cliente (ou se o cliente pedir expressamente um atendente humano imediato).
"""

        resposta = await openai_client.beta.chat.completions.parse(
            model=settings.MODEL_ANALYZER,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA_ANALISTA},
                {"role": "user", "content": prompt_usuario}
            ],
            response_format=schemas.LeadAnalysisOutput,
            temperature=0.0
        )

        resultado = resposta.choices[0].message.parsed
        if not resultado:
            raise ValueError("O modelo não retornou o formato estruturado esperado.")

        # 🌟 GATILHO DINÂMICO DE TRANSBORDO: Lead VIP / Alto Valor
        if resultado.valor_estimado and resultado.valor_estimado >= settings.TRANSBORDO_VIP_VALOR_MIN:
            if not resultado.transbordo_sugerido:
                resultado.transbordo_sugerido = True
                resultado.justificativa = (
                    f"{resultado.justificativa} | [Gatilho VIP]: Negociação de alto valor "
                    f"(R$ {resultado.valor_estimado:,.2f}) encaminhada para consultor humano sênior."
                )
            if "VIP" not in resultado.tags_sugeridas:
                resultado.tags_sugeridas.append("VIP")

        logger.info(
            f"[ANALISTA LEAD] 🎯 Lead {lead.telefone} avaliado | "
            f"Etapa: {etapa_atual} -> {resultado.etapa_sugerida.value} | "
            f"Desfecho: {resultado.desfecho_sugerido.value} | "
            f"Temp: {resultado.temperatura_sugerida.value} | "
            f"Transbordo: {resultado.transbordo_sugerido} | "
            f"ProntoFechamento: {resultado.pronto_fechamento} | "
            f"Tags: {resultado.tags_sugeridas} | "
            f"Justificativa: {resultado.justificativa}"
        )
        return resultado

    except Exception as e:
        cota_esgotada = is_openai_quota_error(e)
        tags_fallback = list(getattr(lead, "tags", []) or [])
        if cota_esgotada:
            logger.critical(f"[ANALISTA LEAD - COTA ESGOTADA] 🚨 Falha por esgotamento de créditos da OpenAI para {lead.telefone}: {e}")
            if "SEM_CREDITO_OPENAI" not in tags_fallback:
                tags_fallback.append("SEM_CREDITO_OPENAI")
            if "REQUER_ATENCAO" not in tags_fallback:
                tags_fallback.append("REQUER_ATENCAO")
        else:
            logger.error(f"[ANALISTA LEAD ERRO] Falha ao analisar lead {lead.telefone}: {e}", exc_info=True)

        dados_fallback = schemas.DadosQualificacao(**(lead.dados_qualificacao or {})) if isinstance(lead.dados_qualificacao, dict) else schemas.DadosQualificacao()
        return schemas.LeadAnalysisOutput(
            resumo_perfil=lead.resumo_perfil or f"Lead em atendimento ({lead.nome or 'Contato'}).",
            etapa_sugerida=getattr(lead, "etapa_funil", models.EtapaFunil.QUALIFICACAO) or models.EtapaFunil.QUALIFICACAO,
            desfecho_sugerido=getattr(lead, "desfecho", models.DesfechoLead.EM_ANDAMENTO) or models.DesfechoLead.EM_ANDAMENTO,
            transbordo_sugerido=True if cota_esgotada else False,
            temperatura_sugerida=getattr(lead, "temperatura", models.TemperaturaLead.FRIO) or models.TemperaturaLead.FRIO,
            motivo_perda=getattr(lead, "motivo_perda", None),
            valor_estimado=getattr(lead, "valor_estimado", None),
            tags_sugeridas=tags_fallback,
            opt_out_detectado=getattr(lead, "opt_out", False) or False,
            pronto_fechamento=False,
            justificativa="Créditos da OpenAI esgotados. Transbordo acionado." if cota_esgotada else f"Fallback automático por falha técnica na análise: {str(e)}",
            dados_qualificacao=dados_fallback
        )
