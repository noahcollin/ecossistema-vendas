"""
Módulo do Agente Auditor de Negócios (DealAuditorAgent).
Realiza a análise retrospectiva completa da conversa do cliente e produz
o Dossiê Executivo de Vendas (Win/Loss Analysis, O que agradou/desagradou,
dica de ouro para o atendimento humano e feedback para a empresa).
Inclui guarda de janela máxima de contexto para blindagem FinOps e prevenção de ContextOverflow.
"""

import json
from typing import List
from core.openai_client import openai_client, is_openai_quota_error
from core.logger import logger
from core.config import settings
import models
import schemas
from .prompts import PROMPT_SISTEMA_AUDITOR


def _recortar_historico_auditoria(
    historico_completo: List[models.Interacao],
    limite_maximo: int
) -> tuple[List[models.Interacao], int]:
    """
    Preserva as primeiras 4 interações (abertura/canal de aquisição) e as últimas
    (limite_maximo - 4) interações quando a conversa excede o teto FinOps de tokens.
    """
    total = len(historico_completo)
    if total <= limite_maximo or limite_maximo <= 8:
        return list(historico_completo), 0

    abertura = list(historico_completo[:4])
    recentes = list(historico_completo[-(limite_maximo - 4):])
    omitidas = total - len(abertura) - len(recentes)
    return abertura + recentes, omitidas


async def auditar_jornada_lead(
    lead: models.Lead,
    historico_completo: List[models.Interacao]
) -> schemas.DossieComercialOutput:
    """
    Executa a auditoria completa da jornada do lead através do GPT-4o-mini
    com Structured Outputs (garantia 100% de tipagem Pydantic V2).
    """
    try:
        limite_auditoria = max(int(settings.JANELA_HISTORICO_MAX) * 3, 60)
        historico_recortado, omitidas = _recortar_historico_auditoria(historico_completo, limite_auditoria)

        mensagens_formatadas: list[str] = []
        for idx, interacao in enumerate(historico_recortado):
            if omitidas > 0 and idx == 4:
                mensagens_formatadas.append(
                    f"[... {omitidas} interações intermediárias omitidas pela guarda FinOps; contexto consolidado na Ficha do Lead ...]"
                )
            if interacao.origem == models.InteracaoOrigem.CLIENTE:
                remetente = "Cliente"
            elif interacao.origem == models.InteracaoOrigem.HUMANO:
                remetente = "Consultor Humano (Equipe)"
            elif interacao.origem == models.InteracaoOrigem.SISTEMA:
                remetente = "Nota de Sistema"
            else:
                remetente = "Vendedor (IA)"
            mensagens_formatadas.append(f"{remetente}: {interacao.texto}")

        dialogo_completo = "\n".join(mensagens_formatadas) if mensagens_formatadas else "Nenhuma mensagem registrada."

        dados_qualif = lead.dados_qualificacao or {}
        resumo_atual = lead.resumo_perfil or "Sem resumo prévio."
        valor_fmt = f"R$ {lead.valor_estimado:,.2f}" if (hasattr(lead, "valor_estimado") and lead.valor_estimado is not None) else "Não informado"

        prompt_usuario = f"""
[DADOS ATUAIS DO CLIENTE NO BANCO]
Nome: {lead.nome or 'Não identificado'}
Telefone: {lead.telefone}
Tipo de Entrada: {lead.tipo_entrada.value if hasattr(lead, 'tipo_entrada') and lead.tipo_entrada else 'INBOUND'}
Canal de Origem: {lead.origem_canal if hasattr(lead, 'origem_canal') and lead.origem_canal else 'WHATSAPP_DIRETO'}
Etapa do Funil Atual: {lead.etapa_funil.value if hasattr(lead, 'etapa_funil') and lead.etapa_funil else 'N/A'}
Desfecho Atual: {lead.desfecho.value if hasattr(lead, 'desfecho') and lead.desfecho else 'N/A'}
Controle Atual: {lead.controle.value if hasattr(lead, 'controle') and lead.controle else 'N/A'}
Temperatura Atual: {lead.temperatura.value if hasattr(lead, 'temperatura') and lead.temperatura else 'N/A'}
Motivo de Perda Atual: {lead.motivo_perda or 'Nenhum'}
Valor Estimado do Deal: {valor_fmt}
Tags Registradas: {lead.tags or []}

[FICHA DO LEAD / MEMÓRIA ACUMULADA]
{resumo_atual}

[DADOS ESTRUTURADOS DE QUALIFICAÇÃO]
{json.dumps(dados_qualif, ensure_ascii=False)}

[HISTÓRICO DA CONVERSA ({len(historico_completo)} mensagens totais)]
{dialogo_completo}
"""

        resposta = await openai_client.beta.chat.completions.parse(
            model=settings.MODEL_AUDITOR,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA_AUDITOR},
                {"role": "user", "content": prompt_usuario}
            ],
            response_format=schemas.DossieComercialOutput,
            temperature=0.2
        )

        dossie = resposta.choices[0].message.parsed
        if dossie is None:
            raise ValueError("OpenAI retornou dossiê nulo no parsing.")

        if not dossie.tipo_entrada:
            dossie.tipo_entrada = lead.tipo_entrada.value if hasattr(lead, 'tipo_entrada') and lead.tipo_entrada else "INBOUND"
        if not dossie.origem_canal:
            dossie.origem_canal = lead.origem_canal if hasattr(lead, 'origem_canal') and lead.origem_canal else "WHATSAPP_DIRETO"

        logger.info(
            f"[AUDITOR COMERCIAL] 📋 Dossiê gerado para {lead.telefone} ({lead.nome or 'Anônimo'}) | "
            f"Desfecho: {dossie.resultado_final.desfecho.value} | Canal: {dossie.origem_canal} | "
            f"Nota IA: {dossie.nota_atendimento_ia}/10 | Reativação: {dossie.potencial_reativacao}"
        )
        return dossie

    except Exception as e:
        if is_openai_quota_error(e):
            logger.critical(f"[AUDITOR COMERCIAL - COTA ESGOTADA] 🚨 Falha por esgotamento de créditos da OpenAI para {lead.telefone}: {e}")
        else:
            logger.error(f"[AUDITOR COMERCIAL ERRO] ❌ Falha ao auditar lead {lead.telefone}: {e}", exc_info=True)

        desfecho_padrao = lead.desfecho if hasattr(lead, "desfecho") and lead.desfecho else models.DesfechoLead.EM_ANDAMENTO
        tipo_entrada_padrao = lead.tipo_entrada.value if hasattr(lead, "tipo_entrada") and lead.tipo_entrada else "INBOUND"
        origem_padrao = lead.origem_canal if hasattr(lead, "origem_canal") and lead.origem_canal else "WHATSAPP_DIRETO"
        return schemas.DossieComercialOutput(
            historia_do_lead=lead.resumo_perfil or f"Cliente {lead.telefone} em atendimento.",
            o_que_agradou=["Atendimento automatizado inicial"],
            pontos_de_atrito_e_queixas=[],
            resultado_final=schemas.DossieResultado(
                desfecho=desfecho_padrao,
                motivo_raiz=lead.motivo_perda,
                concorrente_citado=None,
                diferencial_decisivo=None
            ),
            estrategia_utilizada="Atendimento comercial padrão",
            nota_atendimento_ia=7.0,
            feedback_para_o_negocio="Manter acompanhamento com a equipe comercial.",
            proximo_passo=schemas.DossieProximoPasso(
                acao_sugerida="Verificar histórico diretamente no WhatsApp",
                quando_retomar="Em horário comercial",
                dica_de_ouro="Acolha o cliente pelo nome e entenda se restou alguma dúvida."
            ),
            potencial_reativacao="MEDIO",
            tipo_entrada=tipo_entrada_padrao,
            origem_canal=origem_padrao
        )
